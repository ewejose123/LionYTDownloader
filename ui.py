import os
import re
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config import (
    AUDIO_BITRATE_OPTIONS,
    CODEC_OPTIONS,
    DEFAULT_PARALLEL_DOWNLOADS,
    PARALLEL_DOWNLOAD_OPTIONS,
    QUALITY_OPTIONS,
)
from history import add_entry, clear_history, load_history
from utils import SmartTextEdit, format_duration, list_media_files, media_icon
from workers import CheckExistsWorker, DownloadWorker, TitleFetchWorker, UpdateWorker

URL_PATTERN = re.compile(r"((?:https?://|www\.)[^\s]+)")

PROGRESS_STYLE = """
    QProgressBar {
        border: 1px solid #45475a;
        border-radius: 5px;
        text-align: center;
        color: white;
        min-height: 22px;
    }
    QProgressBar::chunk {
        background-color: #89b4fa;
        border-radius: 4px;
    }
"""


class MainWindow(QMainWindow):
    def __init__(self, tray_icon: QSystemTrayIcon | None = None) -> None:
        super().__init__()
        self.tray_icon = tray_icon
        self.worker: DownloadWorker | None = None
        self.title_worker: TitleFetchWorker | None = None
        self.stats = {"success": 0, "exists": 0, "error": 0}
        self.error_details: list[str] = []
        self._title_map: dict[str, str] = {}

        self.setWindowTitle("Lion YT Downloader")
        self.resize(1150, 750)
        self.setup_ui()
        self.refresh_file_list()
        self.refresh_history_list()

    def setup_ui(self) -> None:
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        top_layout = QHBoxLayout()
        self.txt_dir = QLineEdit(str(Path.home() / "Downloads"))
        self.txt_dir.setReadOnly(True)
        self.txt_dir.textChanged.connect(self.refresh_file_list)

        btn_browse = QPushButton("Examinar...")
        btn_browse.clicked.connect(self.browse_folder)

        btn_open_folder = QPushButton("📂 Abrir")
        btn_open_folder.setStyleSheet("background-color: #89dceb; color: black; font-weight: bold;")
        btn_open_folder.clicked.connect(self.open_output_folder)

        self.combo_format = QComboBox()
        for _, label in QUALITY_OPTIONS:
            self.combo_format.addItem(label)
        self.combo_format.currentIndexChanged.connect(self._on_format_changed)

        self.combo_codec = QComboBox()
        for _, label in CODEC_OPTIONS:
            self.combo_codec.addItem(label)

        top_layout.addWidget(QLabel("Carpeta:"))
        top_layout.addWidget(self.txt_dir, stretch=2)
        top_layout.addWidget(btn_browse)
        top_layout.addWidget(btn_open_folder)
        top_layout.addWidget(QLabel("Calidad:"))
        top_layout.addWidget(self.combo_format)
        top_layout.addWidget(QLabel("Códec:"))
        top_layout.addWidget(self.combo_codec)
        main_layout.addLayout(top_layout)

        opts_layout = QHBoxLayout()
        self.combo_audio_bitrate = QComboBox()
        for key, label in AUDIO_BITRATE_OPTIONS:
            self.combo_audio_bitrate.addItem(label, key)

        self.combo_parallel = QComboBox()
        for key, label in PARALLEL_DOWNLOAD_OPTIONS:
            self.combo_parallel.addItem(label, key)
        default_idx = next(
            (i for i, (k, _) in enumerate(PARALLEL_DOWNLOAD_OPTIONS) if k == DEFAULT_PARALLEL_DOWNLOADS),
            1,
        )
        self.combo_parallel.setCurrentIndex(default_idx)

        self.chk_subtitles = QCheckBox("Subtítulos (ES/EN)")
        self.chk_auto_titles = QCheckBox("Auto-títulos")
        self.chk_auto_titles.setChecked(True)
        self.chk_auto_titles.setToolTip("Obtiene el título del video automáticamente al pegar enlaces.")

        self.chk_notify = QCheckBox("Notificar al terminar")
        self.chk_notify.setChecked(True)

        btn_paste = QPushButton("📋 Pegar enlaces")
        btn_paste.clicked.connect(self.paste_from_clipboard)

        btn_fetch_titles = QPushButton("🏷 Obtener títulos")
        btn_fetch_titles.clicked.connect(self.fetch_titles)

        opts_layout.addWidget(QLabel("MP3:"))
        opts_layout.addWidget(self.combo_audio_bitrate)
        opts_layout.addWidget(QLabel("Paralelo:"))
        opts_layout.addWidget(self.combo_parallel)
        opts_layout.addWidget(self.chk_subtitles)
        opts_layout.addWidget(self.chk_auto_titles)
        opts_layout.addWidget(self.chk_notify)
        opts_layout.addStretch()
        opts_layout.addWidget(btn_fetch_titles)
        opts_layout.addWidget(btn_paste)
        main_layout.addLayout(opts_layout)
        self._on_format_changed()

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 10, 10, 0)

        self.text_input = SmartTextEdit()
        self.text_input.setPlaceholderText(
            "⬇️ Arrastra enlaces aquí o pega una lista...\n\n"
            "🟢 Verde: Descargado\n"
            "🟡 Naranja: Ya existía\n"
            "🔴 Rojo: Error\n\n"
            "Con Auto-títulos activo, se añade el nombre del video encima de cada enlace."
        )
        self.text_input.urls_dropped.connect(self._on_urls_inserted)

        btn_check_links = QPushButton("🔍 Verificar enlaces existentes")
        btn_check_links.setStyleSheet("background-color: #f9e2af; color: black; padding: 8px;")
        btn_check_links.clicked.connect(self.check_existing_links)

        self.lbl_status = QLabel("Esperando enlaces...")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #89b4fa;")
        self.lbl_status.setWordWrap(True)

        stats_layout = QHBoxLayout()
        self.lbl_queue = QLabel("Cola: -")
        self.lbl_speed = QLabel("Velocidad: -")
        self.lbl_eta = QLabel("ETA: -")
        self.lbl_elapsed = QLabel("Tiempo: -")
        stats_layout.addWidget(self.lbl_queue)
        stats_layout.addWidget(self.lbl_speed)
        stats_layout.addWidget(self.lbl_eta)
        stats_layout.addWidget(self.lbl_elapsed)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setStyleSheet(PROGRESS_STYLE)

        left_layout.addWidget(self.text_input)
        left_layout.addWidget(btn_check_links)
        left_layout.addWidget(self.lbl_status)
        left_layout.addLayout(stats_layout)
        left_layout.addWidget(self.progress_bar)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 0, 0)

        self.tabs_right = QTabWidget()

        files_tab = QWidget()
        files_layout = QVBoxLayout(files_tab)
        self.list_files = QListWidget()
        self.list_files.setStyleSheet(
            "QListWidget { background-color: #181825; border: 1px solid #313244; "
            "border-radius: 8px; padding: 5px; font-size: 13px; }"
        )
        files_layout.addWidget(self.list_files)
        btn_refresh_list = QPushButton("🔄 Actualizar archivos")
        btn_refresh_list.clicked.connect(self.refresh_file_list)
        files_layout.addWidget(btn_refresh_list)

        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        self.list_history = QListWidget()
        self.list_history.setStyleSheet(
            "QListWidget { background-color: #181825; border: 1px solid #313244; "
            "border-radius: 8px; padding: 5px; font-size: 12px; }"
        )
        self.list_history.itemDoubleClicked.connect(self._redownload_from_history)
        history_layout.addWidget(self.list_history)

        history_btns = QHBoxLayout()
        btn_redownload = QPushButton("↻ Re-descargar")
        btn_redownload.clicked.connect(self._redownload_selected_history)
        btn_clear_history = QPushButton("🗑 Limpiar historial")
        btn_clear_history.clicked.connect(self._clear_history)
        history_btns.addWidget(btn_redownload)
        history_btns.addWidget(btn_clear_history)
        history_layout.addLayout(history_btns)

        self.tabs_right.addTab(files_tab, "📁 Archivos")
        self.tabs_right.addTab(history_tab, "📜 Historial")
        right_layout.addWidget(self.tabs_right)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([600, 500])
        main_layout.addWidget(splitter)

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 10, 0, 0)

        self.btn_update = QPushButton("Actualizar yt-dlp")
        self.btn_update.setStyleSheet("background-color: #313244; padding: 10px; color: white;")
        self.btn_update.clicked.connect(self.update_ytdlp)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setStyleSheet("background-color: #fab387; color: black; padding: 10px; font-weight: bold;")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_downloads)

        self.btn_clear = QPushButton("Limpiar Caja")
        self.btn_clear.setStyleSheet(
            "background-color: #f38ba8; color: black; padding: 10px; font-weight: bold;"
        )
        self.btn_clear.clicked.connect(self.clear_text_box)

        self.btn_download = QPushButton("DESCARGAR TODO")
        self.btn_download.setStyleSheet(
            "QPushButton { background-color: #a6e3a1; color: black; font-weight: bold; "
            "font-size: 14px; padding: 12px; border-radius: 6px; } "
            "QPushButton:hover { background-color: #94e2d5; } "
            "QPushButton:disabled { background-color: #585b70; color: #bac2de; }"
        )
        self.btn_download.clicked.connect(self.start_downloads)

        bottom_layout.addWidget(self.btn_update)
        bottom_layout.addWidget(self.btn_cancel)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_clear)
        bottom_layout.addWidget(self.btn_download)
        main_layout.addLayout(bottom_layout)

    def _on_format_changed(self) -> None:
        is_audio = self.get_format_type() == "audio"
        self.combo_codec.setEnabled(not is_audio)
        self.chk_subtitles.setEnabled(not is_audio)
        self.combo_audio_bitrate.setEnabled(is_audio)

    def get_format_type(self) -> str:
        return QUALITY_OPTIONS[self.combo_format.currentIndex()][0]

    def get_codec_type(self) -> str:
        return CODEC_OPTIONS[self.combo_codec.currentIndex()][0]

    def get_audio_bitrate(self) -> str:
        return self.combo_audio_bitrate.currentData() or "192"

    def get_parallel_workers(self) -> int:
        return int(self.combo_parallel.currentData() or DEFAULT_PARALLEL_DOWNLOADS)

    def browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta", self.txt_dir.text())
        if folder:
            self.txt_dir.setText(folder)

    def open_output_folder(self) -> None:
        path = self.txt_dir.text()
        if os.path.isdir(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def paste_from_clipboard(self) -> None:
        from PyQt6.QtWidgets import QApplication

        text = QApplication.clipboard().text().strip()
        if not text:
            return
        current = self.text_input.toPlainText()
        if current and not current.endswith("\n"):
            self.text_input.insertPlainText("\n" + text + "\n")
        else:
            self.text_input.insertPlainText(text + "\n")
        self._maybe_fetch_titles()

    def _on_urls_inserted(self) -> None:
        self._maybe_fetch_titles()

    def _urls_without_titles(self) -> list[str]:
        items = self.parse_input_text()
        return [item["url"] for item in items if not item.get("title")]

    def _maybe_fetch_titles(self) -> None:
        if not self.chk_auto_titles.isChecked():
            return
        urls = self._urls_without_titles()
        if urls:
            self.fetch_titles(urls)

    def fetch_titles(self, urls: list[str] | None = None) -> None:
        if urls is None:
            urls = self._urls_without_titles()
        if not urls:
            QMessageBox.information(self, "Títulos", "No hay enlaces sin título.")
            return
        if self.title_worker and self.title_worker.isRunning():
            return

        self.lbl_status.setText(f"Obteniendo títulos ({len(urls)})...")
        self.title_worker = TitleFetchWorker(urls)
        self.title_worker.title_fetched.connect(self._on_title_fetched)
        self.title_worker.progress.connect(lambda v: self.update_progress_bar(v, False))
        self.title_worker.finished.connect(lambda: self.lbl_status.setText("Títulos actualizados."))
        self.title_worker.start()

    def _on_title_fetched(self, url: str, title: str) -> None:
        self._title_map[url] = title
        self._insert_title_for_url(url, title)

    def _insert_title_for_url(self, url: str, title: str) -> None:
        text = self.text_input.toPlainText()
        lines = text.split("\n")
        result: list[str] = []

        for i, line in enumerate(lines):
            if url not in line and url.replace("https://", "") not in line:
                result.append(line)
                continue

            has_title_above = False
            j = len(result) - 1
            while j >= 0 and not result[j].strip():
                j -= 1
            if j >= 0 and not URL_PATTERN.search(result[j]):
                has_title_above = True

            if not has_title_above:
                result.append(title)
            result.append(line)

        self.text_input.setPlainText("\n".join(result))

    def refresh_file_list(self) -> None:
        self.list_files.clear()
        for filename in list_media_files(self.txt_dir.text()):
            self.list_files.addItem(f"{media_icon(filename)} {filename}")

    def refresh_history_list(self) -> None:
        self.list_history.clear()
        for entry in load_history():
            ts = entry.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                date_str = dt.strftime("%d/%m/%Y %H:%M")
            except ValueError:
                date_str = "—"
            status_icon = {"success": "✅", "exists": "⏭", "error": "❌"}.get(entry.get("status", ""), "•")
            title = entry.get("title", entry.get("url", ""))[:50]
            self.list_history.addItem(f"{status_icon} [{date_str}] {title}")
            item = self.list_history.item(self.list_history.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, entry)

    def _clear_history(self) -> None:
        reply = QMessageBox.question(
            self, "Limpiar historial", "¿Borrar todo el historial de descargas?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            clear_history()
            self.refresh_history_list()

    def _redownload_from_history(self, item) -> None:
        entry = item.data(Qt.ItemDataRole.UserRole)
        if not entry:
            return
        self._append_url_to_input(entry.get("url", ""), entry.get("title"))

    def _redownload_selected_history(self) -> None:
        item = self.list_history.currentItem()
        if item:
            self._redownload_from_history(item)

    def _append_url_to_input(self, url: str, title: str | None = None) -> None:
        if not url:
            return
        block = f"{title}\n{url}" if title else url
        current = self.text_input.toPlainText()
        if current and not current.endswith("\n"):
            self.text_input.insertPlainText("\n\n" + block + "\n")
        else:
            self.text_input.insertPlainText(block + "\n")

    def clear_text_box(self) -> None:
        self.text_input.clear()
        self.reset_text_colors()

    def reset_text_colors(self) -> None:
        cursor = self.text_input.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#cdd6f4"))
        fmt.setFontUnderline(False)
        cursor.mergeCharFormat(fmt)

    def parse_input_text(self) -> list[dict]:
        raw_text = self.text_input.toPlainText()
        parsed_items: list[dict] = []
        current_title: str | None = None
        unique_urls: set[str] = set()

        for line in raw_text.split("\n"):
            line = line.strip()
            if not line:
                continue

            url_match = URL_PATTERN.search(line)
            if url_match:
                url = url_match.group(1)
                if url.startswith("www."):
                    url = "https://" + url

                if url not in unique_urls:
                    unique_urls.add(url)
                    parsed_items.append({"url": url, "title": current_title})
                current_title = None
            else:
                current_title = line

        return parsed_items

    def _set_busy(self, busy: bool) -> None:
        self.btn_download.setEnabled(not busy)
        self.btn_cancel.setEnabled(busy)
        self.text_input.setReadOnly(busy)

    def update_progress_bar(self, value: int, indeterminate: bool = False) -> None:
        if indeterminate:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value)

    def check_existing_links(self) -> None:
        items = self.parse_input_text()
        if not items:
            QMessageBox.information(self, "Sin enlaces", "No se detectaron URLs válidas.")
            return

        self.reset_text_colors()
        self._set_busy(True)
        self.lbl_status.setText("Verificando enlaces en carpeta de destino...")

        self.check_worker = CheckExistsWorker(
            items, self.txt_dir.text(), self.get_format_type(), self.get_codec_type()
        )
        self.check_worker.progress.connect(lambda v: self.update_progress_bar(v, False))
        self.check_worker.item_checked.connect(self._on_item_checked)
        self.check_worker.finished.connect(self._on_check_finished)
        self.check_worker.start()

    def _on_check_finished(self) -> None:
        self.lbl_status.setText("Verificación completada.")
        self._set_busy(False)

    def start_downloads(self) -> None:
        items = self.parse_input_text()
        if not items:
            QMessageBox.information(self, "Sin enlaces", "No se detectaron URLs válidas.")
            return

        self.reset_text_colors()
        self._set_busy(True)
        self.stats = {"success": 0, "exists": 0, "error": 0}
        self.error_details = []

        self.worker = DownloadWorker(
            items,
            self.txt_dir.text(),
            self.get_format_type(),
            self.get_codec_type(),
            audio_bitrate=self.get_audio_bitrate(),
            download_subtitles=self.chk_subtitles.isChecked(),
            parallel_workers=self.get_parallel_workers(),
        )
        self.worker.progress.connect(self.update_progress_bar)
        self.worker.status_update.connect(self._on_status_update)
        self.worker.item_finished.connect(self._on_download_item_finished)
        self.worker.finished.connect(self.downloads_completed)
        self.worker.start()

    def cancel_downloads(self) -> None:
        if self.worker and self.worker.isRunning():
            self.lbl_status.setText("Cancelando descargas activas...")
            self.worker.cancel()

    def _on_status_update(self, status: str, speed: str, eta: str, queue: str, elapsed: str) -> None:
        self.lbl_status.setText(status)
        self.lbl_speed.setText(f"Velocidad: {speed}")
        self.lbl_eta.setText(f"ETA: {eta}")
        self.lbl_queue.setText(f"Cola: {queue}")
        self.lbl_elapsed.setText(f"Tiempo: {elapsed}")

    def _on_item_checked(self, url: str, state: str, error_msg: str = "") -> None:
        self._color_url(url, state, error_msg)
        if state in self.stats:
            self.stats[state] += 1
        if state == "error" and error_msg:
            self.error_details.append(f"🔗 {url}\n❌ {error_msg.strip()}")

    def _on_download_item_finished(self, url: str, state: str, error_msg: str, title: str) -> None:
        self._on_item_checked(url, state, error_msg)
        add_entry(
            url=url,
            title=title or self._title_map.get(url, ""),
            status=state,
            download_dir=self.txt_dir.text(),
            format_type=self.get_format_type(),
            codec_type=self.get_codec_type(),
        )

    def _color_url(self, url: str, state: str, error_msg: str = "") -> None:
        if state == "success":
            color, underline = QColor("#a6e3a1"), False
        elif state == "exists":
            color, underline = QColor("#fab387"), False
        elif state == "missing":
            return
        elif state == "error":
            color, underline = QColor("#f38ba8"), True
        else:
            return

        url_to_find = url.replace("https://", "") if url.startswith("https://www.") else url
        cursor = self.text_input.document().find(url_to_find)
        if not cursor.isNull():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            fmt.setFontUnderline(underline)
            cursor.mergeCharFormat(fmt)

    def _show_notification(self, title: str, message: str) -> None:
        if not self.chk_notify.isChecked():
            return
        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )

    def downloads_completed(self) -> None:
        cancelled = self.worker is not None and self.worker.was_cancelled
        total_time = format_duration(self.worker.elapsed_seconds) if self.worker else "0s"
        self.update_progress_bar(100 if not cancelled else self.progress_bar.value(), False)
        status = "Cancelado." if cancelled else "Completado."
        self.lbl_status.setText(f"{status} Tiempo total: {total_time}")
        self.lbl_elapsed.setText(f"Tiempo: {total_time}")
        self._set_busy(False)
        self.refresh_file_list()
        self.refresh_history_list()

        msg = (
            f"⏱ Tiempo total: {total_time}\n\n"
            f"✅ Nuevos/Procesados: {self.stats['success']}\n"
            f"⏭️ Saltados (Ya existían): {self.stats['exists']}\n"
            f"❌ Errores: {self.stats['error']}"
        )
        if cancelled:
            msg = "⚠️ Descarga cancelada por el usuario.\n\n" + msg

        if self.error_details:
            msg += "\n\n⚠️ Detalles de Errores:\n" + "\n\n".join(self.error_details[:3])
            if len(self.error_details) > 3:
                msg += "\n\n... y más errores."

        notify_title = "Descarga cancelada" if cancelled else "Descargas completadas"
        notify_body = (
            f"Tiempo: {total_time} · {self.stats['success']} OK · "
            f"{self.stats['exists']} omitidos · {self.stats['error']} errores"
        )
        self._show_notification(notify_title, notify_body)

        if not self.isActiveWindow():
            self.tray_icon and self.tray_icon.show()

        QMessageBox.information(self, "Resumen", msg)

    def update_ytdlp(self) -> None:
        self.btn_update.setEnabled(False)
        self.lbl_status.setText("Actualizando yt-dlp...")
        self.upd_worker = UpdateWorker()
        self.upd_worker.progress.connect(lambda t: self.lbl_status.setText(t))
        self.upd_worker.finished.connect(self._on_update_finished)
        self.upd_worker.start()

    def _on_update_finished(self, success: bool, message: str) -> None:
        self.btn_update.setEnabled(True)
        self.lbl_status.setText("Esperando enlaces...")
        if success:
            QMessageBox.information(self, "Actualización", message)
        else:
            QMessageBox.critical(self, "Error", message)
