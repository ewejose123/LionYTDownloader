import re
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QTextCharFormat
from PyQt6.QtWidgets import QTextEdit

from config import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
INVALID_FILENAME_CHARS = re.compile(r'[\\/*?:"<>|]')


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text or "")


def sanitize_title(title: str) -> str:
    return INVALID_FILENAME_CHARS.sub("", title).strip()


def format_duration(seconds: float) -> str:
    """Formatea segundos como '45s', '3m 12s' o '1h 05m 30s'."""
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


ENCODE_DURATION_FACTORS = {
    "h264": 1.5,
    "h265": 2.5,
    "prores": 4.0,
    "original": 0.4,
    "audio": 0.3,
}


class YtDlpLogger:
    """Captura errores y detección de archivos ya existentes desde yt-dlp."""

    def __init__(self) -> None:
        self.already_exists = False
        self.last_error = ""

    def debug(self, msg: str) -> None:
        self._check(msg)

    def info(self, msg: str) -> None:
        self._check(msg)

    def warning(self, msg: str) -> None:
        self._check(msg)

    def error(self, msg: str) -> None:
        self.last_error = msg
        self._check(msg)

    def _check(self, msg: str) -> None:
        lower = msg.lower()
        if "has already been downloaded" in lower or "already exists" in lower:
            self.already_exists = True


class ProgressTracker:
    """Calcula progreso global de cola y etiquetas de fase."""

    def __init__(self, total_items: int) -> None:
        self.total_items = max(total_items, 1)
        self.current_index = 0
        self.item_percent = 0.0
        self.indeterminate_phase = False
        self.phase_label = "Preparando..."
        self.speed = "-"
        self.eta = "-"
        self.filename = ""

    def start_item(self, index: int, filename: str = "") -> None:
        self.current_index = index
        self.item_percent = 0.0
        self.indeterminate_phase = False
        self.phase_label = "Iniciando descarga..."
        self.speed = "-"
        self.eta = "-"
        self.filename = filename

    def set_download_progress(self, percent: float, speed: str, eta: str, filename: str) -> None:
        self.indeterminate_phase = False
        self.item_percent = max(0.0, min(100.0, percent))
        self.phase_label = "Descargando"
        self.speed = speed
        self.eta = eta
        self.filename = filename

    def set_processing(self, label: str, percent: float | None = None) -> None:
        self.phase_label = label
        self.speed = "-"
        self.eta = "-"
        if percent is None:
            self.indeterminate_phase = True
        else:
            self.indeterminate_phase = False
            self.item_percent = max(0.0, min(100.0, percent))

    def overall_percent(self) -> int:
        completed = self.current_index / self.total_items * 100
        current = (self.item_percent / 100) * (100 / self.total_items)
        return min(100, int(completed + current))

    def is_indeterminate(self) -> bool:
        return self.indeterminate_phase

    def queue_label(self) -> str:
        return f"{self.current_index + 1} / {self.total_items}"

    def status_text(self) -> str:
        name = Path(self.filename).name if self.filename else ""
        if name:
            return f"{self.phase_label}: {name[:45]}"
        return self.phase_label


class SmartTextEdit(QTextEdit):
    urls_dropped = pyqtSignal()

    _BASE_STYLE = """
        QTextEdit {
            background-color: #1e1e2e;
            color: #cdd6f4;
            caret-color: #ffffff;
            border: 2px dashed #555555;
            border-radius: 8px;
            padding: 10px;
            font-size: 14px;
        }
    """
    _DRAG_STYLE = """
        QTextEdit {
            background-color: #242536;
            color: #cdd6f4;
            caret-color: #ffffff;
            border: 2px dashed #89b4fa;
            border-radius: 8px;
            padding: 10px;
            font-size: 14px;
        }
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet(self._BASE_STYLE)

    def _reset_char_format(self) -> None:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#cdd6f4"))
        fmt.setFontUnderline(False)
        self.setCurrentCharFormat(fmt)

    def insertFromMimeData(self, source) -> None:
        if source.hasText():
            self._reset_char_format()
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)

    def keyPressEvent(self, event) -> None:
        self._reset_char_format()
        super().keyPressEvent(event)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet(self._DRAG_STYLE)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self.setStyleSheet(self._BASE_STYLE)

    def dropEvent(self, event) -> None:
        self.setStyleSheet(self._BASE_STYLE)
        mime = event.mimeData()

        text_to_insert = ""
        if mime.hasText():
            text_to_insert = mime.text()
        elif mime.hasUrls():
            urls = [u.toString() for u in mime.urls() if u.scheme() in ("http", "https")]
            text_to_insert = "\n".join(urls)

        if text_to_insert:
            self._reset_char_format()
            current_text = self.toPlainText()
            if current_text and not current_text.endswith("\n"):
                self.insertPlainText("\n" + text_to_insert + "\n")
            else:
                self.insertPlainText(text_to_insert + "\n")
            self.urls_dropped.emit()

        event.acceptProposedAction()


def list_media_files(folder: str) -> list[str]:
    """Lista archivos multimedia en la carpeta de destino."""
    path = Path(folder)
    if not path.is_dir():
        return []
    exts = VIDEO_EXTENSIONS + AUDIO_EXTENSIONS
    try:
        return sorted(f.name for f in path.iterdir() if f.suffix.lower() in exts)
    except OSError:
        return []


def media_icon(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return "🎵" if ext in AUDIO_EXTENSIONS else "🎬"
