import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import yt_dlp
from PyQt6.QtCore import QThread, pyqtSignal

from config import (
    CONCURRENT_FRAGMENTS,
    ENCODE_CODECS,
    FRAGMENT_RETRIES,
    POSTPROCESSOR_LABELS,
    SOCKET_TIMEOUT,
    YTDLP_RETRIES,
    build_video_format,
    extensions_for_format,
    get_codec_ffmpeg_args,
)
from utils import ENCODE_DURATION_FACTORS, YtDlpLogger, format_duration, sanitize_title, strip_ansi


class ParallelProgressTracker:
    """Agrega progreso de descargas paralelas."""

    def __init__(self, total_items: int, codec_type: str = "original", format_type: str = "best") -> None:
        self.total_items = max(total_items, 1)
        self.codec_type = codec_type
        self.format_type = format_type
        self._lock = threading.Lock()
        self._active: dict[int, dict[str, Any]] = {}
        self._completed = 0
        self.indeterminate_phase = False

    def start_item(self, index: int, label: str) -> None:
        with self._lock:
            self._active[index] = {
                "percent": 0.0,
                "phase": "Iniciando descarga...",
                "speed": "-",
                "eta": "-",
                "filename": label,
                "indeterminate": False,
                "is_processing": False,
                "processing_started": 0.0,
                "video_duration": 0.0,
            }

    def set_download(self, index: int, percent: float, speed: str, eta: str, filename: str) -> None:
        with self._lock:
            if index not in self._active:
                return
            self._active[index].update(
                {
                    "percent": max(0.0, min(100.0, percent)),
                    "phase": "Descargando",
                    "speed": speed,
                    "eta": eta,
                    "filename": filename,
                    "indeterminate": False,
                    "is_processing": False,
                }
            )

    def set_processing(
        self,
        index: int,
        label: str,
        percent: float | None = None,
        video_duration: float | None = None,
    ) -> None:
        with self._lock:
            if index not in self._active:
                return
            item = self._active[index]
            if not item.get("is_processing"):
                item["processing_started"] = time.monotonic()
                item["is_processing"] = True
            if video_duration and video_duration > 0:
                item["video_duration"] = video_duration
            item["phase"] = label
            if percent is None:
                item["indeterminate"] = True
                est = self._estimate_processing_percent(item)
                if est is not None:
                    item["percent"] = est
                    item["indeterminate"] = False
            else:
                item["indeterminate"] = False
                item["percent"] = max(0.0, min(100.0, percent))

    def _encode_factor(self) -> float:
        if self.format_type == "audio":
            return ENCODE_DURATION_FACTORS["audio"]
        return ENCODE_DURATION_FACTORS.get(self.codec_type, 2.0)

    def _estimate_processing_percent(self, item: dict[str, Any]) -> float | None:
        duration = item.get("video_duration") or 0.0
        started = item.get("processing_started") or 0.0
        if duration <= 0 or started <= 0:
            return None
        elapsed = time.monotonic() - started
        estimated_total = duration * self._encode_factor()
        if estimated_total <= 0:
            return None
        return min(95.0, (elapsed / estimated_total) * 100)

    def _processing_metrics(self, item: dict[str, Any]) -> tuple[str, str]:
        started = item.get("processing_started") or 0.0
        elapsed = time.monotonic() - started if started else 0.0
        speed_text = f"Codificando · {format_duration(elapsed)}"

        duration = item.get("video_duration") or 0.0
        if duration > 0 and elapsed > 0:
            estimated_total = duration * self._encode_factor()
            remaining = max(0.0, estimated_total - elapsed)
            avg_speed = duration / elapsed if elapsed else 0.0
            speed_text = f"Codificando · {avg_speed:.2f}x · {format_duration(elapsed)}"
            eta_text = f"~{format_duration(remaining)}"
            return speed_text, eta_text

        return speed_text, "Calculando..."

    def finish_item(self, index: int) -> None:
        with self._lock:
            self._active.pop(index, None)
            self._completed += 1

    def overall_percent(self) -> int:
        with self._lock:
            done = self._completed * 100
            active = sum(item["percent"] for item in self._active.values())
            return min(100, int((done + active) / self.total_items))

    def is_indeterminate(self) -> bool:
        with self._lock:
            if not self._active:
                return False
            return any(item["indeterminate"] for item in self._active.values())

    def queue_label(self) -> str:
        with self._lock:
            active_count = len(self._active)
            return f"{self._completed + active_count} / {self.total_items} ({active_count} activos)"

    def status_text(self) -> str:
        with self._lock:
            if not self._active:
                return "Esperando..."
            primary = next(iter(self._active.values()))
            name = os.path.basename(primary["filename"]) if primary["filename"] else ""
            if len(self._active) > 1:
                prefix = f"{primary['phase']} (+{len(self._active) - 1} más)"
            else:
                prefix = primary["phase"]
            if name:
                return f"{prefix}: {name[:40]}"
            return prefix

    def combined_speed(self) -> str:
        with self._lock:
            download_speeds = []
            processing_speeds = []
            for item in self._active.values():
                if item.get("is_processing"):
                    proc_speed, _ = self._processing_metrics(item)
                    processing_speeds.append(proc_speed)
                else:
                    s = item.get("speed", "-")
                    if s and s not in ("-", "...", "N/A"):
                        download_speeds.append(s)
            parts = download_speeds[:2] + processing_speeds[:2]
            return " | ".join(parts) if parts else "-"

    def combined_eta(self) -> str:
        with self._lock:
            etas = []
            processing_etas = []
            for item in self._active.values():
                if item.get("is_processing"):
                    _, proc_eta = self._processing_metrics(item)
                    processing_etas.append(proc_eta)
                else:
                    e = item.get("eta", "-")
                    if e and e not in ("-", "...", "N/A"):
                        etas.append(e)
            parts = etas[:1] + processing_etas[:2]
            return " | ".join(parts) if parts else "-"

    def has_active(self) -> bool:
        with self._lock:
            return bool(self._active)


def _build_ydl_opts(
    download_dir: str,
    format_type: str,
    codec_type: str,
    audio_bitrate: str,
    download_subtitles: bool,
    custom_title: str | None,
    logger: YtDlpLogger,
    download_hook,
    postprocessor_hook,
) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "progress_hooks": [download_hook],
        "postprocessor_hooks": [postprocessor_hook],
        "logger": logger,
        "nocolor": True,
        "quiet": True,
        "no_warnings": True,
        "nooverwrites": True,
        "writethumbnail": False,
        "concurrent_fragment_downloads": CONCURRENT_FRAGMENTS,
        "retries": YTDLP_RETRIES,
        "fragment_retries": FRAGMENT_RETRIES,
        "socket_timeout": SOCKET_TIMEOUT,
    }

    if custom_title:
        safe = sanitize_title(custom_title)
        template = f"{safe}.%(ext)s" if safe else "%(title)s.%(ext)s"
    else:
        template = "%(title)s.%(ext)s"
    opts["outtmpl"] = os.path.join(download_dir, template)

    if format_type == "audio":
        opts.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": audio_bitrate,
                    }
                ],
            }
        )
    else:
        opts["format"] = build_video_format(format_type, codec_type)
        if codec_type != "original":
            codec_args, target_ext = get_codec_ffmpeg_args(codec_type)
            opts.update(
                {
                    "merge_output_format": target_ext,
                    "recodevideo": target_ext,
                    "postprocessor_args": {
                        "merger": codec_args,
                        "video_convert": codec_args,
                    },
                }
            )
        else:
            opts.update({"merge_output_format": "mp4", "recodevideo": "mp4"})

    if download_subtitles:
        opts.update(
            {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": ["es", "en", "es-orig", "en-orig"],
                "subtitlesformat": "srt/best",
                "embedsubtitles": codec_type != "original",
            }
        )

    return opts


class DownloadWorker(QThread):
    progress = pyqtSignal(int, bool)
    status_update = pyqtSignal(str, str, str, str, str)  # status, speed, eta, queue, elapsed
    item_finished = pyqtSignal(str, str, str, str)  # url, state, error, title
    finished = pyqtSignal()

    def __init__(
        self,
        items: list[dict],
        download_dir: str,
        format_type: str,
        codec_type: str,
        audio_bitrate: str = "192",
        download_subtitles: bool = False,
        parallel_workers: int = 2,
    ) -> None:
        super().__init__()
        self.items = items
        self.download_dir = download_dir
        self.format_type = format_type
        self.codec_type = codec_type
        self.audio_bitrate = audio_bitrate
        self.download_subtitles = download_subtitles
        self.parallel_workers = max(1, min(parallel_workers, 3))
        self._cancelled = False
        self._run_started_at = 0.0
        self._tracker = ParallelProgressTracker(len(items), codec_type, format_type)
        self._tick_stop = threading.Event()

    def cancel(self) -> None:
        self._cancelled = True
        self._tick_stop.set()

    @property
    def was_cancelled(self) -> bool:
        return self._cancelled

    @property
    def elapsed_seconds(self) -> float:
        if self._run_started_at <= 0:
            return 0.0
        return time.monotonic() - self._run_started_at

    def _emit_progress(self) -> None:
        elapsed = format_duration(self.elapsed_seconds)
        self.progress.emit(self._tracker.overall_percent(), self._tracker.is_indeterminate())
        self.status_update.emit(
            self._tracker.status_text(),
            self._tracker.combined_speed(),
            self._tracker.combined_eta(),
            self._tracker.queue_label(),
            elapsed,
        )

    def _progress_ticker(self) -> None:
        while not self._tick_stop.wait(1.0):
            if self._tracker.has_active():
                self._emit_progress()

    def _download_one(self, index: int, item: dict) -> tuple[str, str, str, str]:
        url = item["url"]
        custom_title = item.get("title")
        logger = YtDlpLogger()
        resolved_title = custom_title or ""
        video_duration = 0.0

        def download_hook(data: dict[str, Any]) -> None:
            nonlocal video_duration
            if self._cancelled:
                raise yt_dlp.utils.DownloadCancelled("Descarga cancelada")
            status = data.get("status")
            if status == "downloading":
                percent_str = strip_ansi(data.get("_percent_str", "0%").replace("%", "").strip())
                try:
                    percent = float(percent_str)
                except ValueError:
                    percent = 0.0
                speed = strip_ansi(data.get("_speed_str", "-") or "-")
                eta = strip_ansi(data.get("_eta_str", "-") or "-")
                filename = data.get("filename") or data.get("info_dict", {}).get("title", url)
                info_duration = float(data.get("info_dict", {}).get("duration") or 0)
                if info_duration > 0:
                    video_duration = info_duration
                self._tracker.set_download(index, percent, speed, eta, filename)
                self._emit_progress()
            elif status == "finished":
                info_duration = float(data.get("info_dict", {}).get("duration") or 0)
                if info_duration > 0:
                    video_duration = info_duration
                self._tracker.set_processing(
                    index, "Descarga completada, procesando...", 100, video_duration
                )
                self._emit_progress()

        def postprocessor_hook(data: dict[str, Any]) -> None:
            if self._cancelled:
                raise yt_dlp.utils.DownloadCancelled("Procesamiento cancelado")
            pp_name = data.get("postprocessor", "")
            label = POSTPROCESSOR_LABELS.get(pp_name, f"Procesando ({pp_name or 'archivo'})")
            if self.codec_type in ENCODE_CODECS and pp_name in ("FFmpegVideoConvertor", "FFmpegMerger"):
                label = f"Recodificando a {self.codec_type.upper()}"
            info = data.get("info_dict") or {}
            video_duration = float(info.get("duration") or 0)
            status = data.get("status")
            if status == "started":
                logger.already_exists = False
                self._tracker.set_processing(index, label, None, video_duration)
                self._emit_progress()
            elif status == "processing":
                pp_progress = data.get("progress")
                self._tracker.set_processing(
                    index,
                    label,
                    float(pp_progress) if isinstance(pp_progress, (int, float)) else None,
                    video_duration,
                )
                self._emit_progress()
            elif status == "finished":
                self._tracker.set_processing(index, f"{label} — listo", 100, video_duration)
                self._emit_progress()

        self._tracker.start_item(index, url)
        self._emit_progress()

        ydl_opts = _build_ydl_opts(
            self.download_dir,
            self.format_type,
            self.codec_type,
            self.audio_bitrate,
            self.download_subtitles,
            custom_title,
            logger,
            download_hook,
            postprocessor_hook,
        )

        success = True
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info and not resolved_title:
                    resolved_title = sanitize_title(info.get("title", ""))
                if info:
                    video_duration = float(info.get("duration") or 0)
                if ydl.download([url]) != 0:
                    success = False
        except yt_dlp.utils.DownloadCancelled:
            self._tracker.finish_item(index)
            raise
        except Exception as exc:
            success = False
            logger.last_error = str(exc)

        self._tracker.finish_item(index)
        self._emit_progress()

        if not success:
            raw_err = logger.last_error
            clean_err = strip_ansi(raw_err) if raw_err else "Error interno de descarga o FFmpeg."
            return url, "error", clean_err, resolved_title
        if logger.already_exists:
            return url, "exists", "", resolved_title
        return url, "success", "", resolved_title

    def run(self) -> None:
        if not self.items:
            self.finished.emit()
            return

        self._run_started_at = time.monotonic()
        self._tick_stop.clear()
        ticker = threading.Thread(target=self._progress_ticker, daemon=True)
        ticker.start()

        try:
            with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                futures = {
                    executor.submit(self._download_one, i, item): item
                    for i, item in enumerate(self.items)
                }
                for future in as_completed(futures):
                    if self._cancelled:
                        break
                    try:
                        url, estado, clean_err, title = future.result()
                        self.item_finished.emit(url, estado, clean_err, title)
                    except yt_dlp.utils.DownloadCancelled:
                        break
                    except Exception as exc:
                        item = futures[future]
                        self.item_finished.emit(item["url"], "error", str(exc), item.get("title") or "")
        except Exception:
            pass
        finally:
            self._tick_stop.set()
            ticker.join(timeout=2.0)

        self.progress.emit(100 if not self._cancelled else self._tracker.overall_percent(), False)
        self._emit_progress()
        self.finished.emit()


class TitleFetchWorker(QThread):
    title_fetched = pyqtSignal(str, str)
    progress = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, urls: list[str]) -> None:
        super().__init__()
        self.urls = urls

    def run(self) -> None:
        total = len(self.urls)
        if total == 0:
            self.finished.emit()
            return

        ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": False}
        for i, url in enumerate(self.urls):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get("title", "") if info else ""
                    if title:
                        self.title_fetched.emit(url, sanitize_title(title))
            except Exception:
                pass
            self.progress.emit(int((i + 1) / total * 100))
        self.finished.emit()


class CheckExistsWorker(QThread):
    progress = pyqtSignal(int)
    item_checked = pyqtSignal(str, str, str)
    finished = pyqtSignal()

    def __init__(
        self,
        items: list[dict],
        download_dir: str,
        format_type: str,
        codec_type: str,
    ) -> None:
        super().__init__()
        self.items = items
        self.download_dir = download_dir
        self.format_type = format_type
        self.codec_type = codec_type

    def run(self) -> None:
        total = len(self.items)
        ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
        valid_exts = extensions_for_format(self.format_type)

        try:
            archivos = os.listdir(self.download_dir) if os.path.isdir(self.download_dir) else []
        except OSError:
            archivos = []

        for i, item in enumerate(self.items):
            url = item["url"]
            custom_title = item.get("title")
            safe_title = sanitize_title(custom_title) if custom_title else None

            try:
                if not safe_title:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        title = info.get("title", "")
                        if title:
                            safe_title = sanitize_title(title)
                        else:
                            self.item_checked.emit(url, "error", "No se pudo extraer el título del enlace.")
                            self.progress.emit(int((i + 1) / total * 100))
                            continue

                prefix = safe_title[:20].lower()
                exists = any(
                    arch.lower().startswith(prefix) and arch.lower().endswith(valid_exts)
                    for arch in archivos
                )
                self.item_checked.emit(url, "exists" if exists else "missing", "")
            except Exception as exc:
                self.item_checked.emit(url, "error", str(exc))

            self.progress.emit(int((i + 1) / total * 100))

        self.finished.emit()


class UpdateWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def run(self) -> None:
        try:
            self.progress.emit("Completando yt-dlp -U...")
            res = subprocess.run(
                ["yt-dlp", "-U"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if res.returncode == 0:
                self.finished.emit(True, "¡yt-dlp actualizado!\n" + (res.stdout or res.stderr))
                return

            self.progress.emit("Reintentando vía pip...")
            res2 = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if res2.returncode == 0:
                self.finished.emit(True, "Actualizado vía pip.\n" + (res2.stdout or ""))
            else:
                self.finished.emit(False, f"Error:\n{res2.stderr or res2.stdout}")
        except subprocess.TimeoutExpired:
            self.finished.emit(False, "La actualización tardó demasiado. Inténtalo de nuevo.")
        except Exception as exc:
            self.finished.emit(False, str(exc))
