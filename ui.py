import os
import re
from pathlib import Path
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QPushButton, QComboBox, QLabel, 
                             QProgressBar, QFileDialog, QMessageBox, QListWidget, 
                             QSplitter)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QTextCharFormat, QDesktopServices, QTextCursor

from utils import SmartTextEdit
from workers import DownloadWorker, CheckExistsWorker, UpdateWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lion YT Downloader")
        self.resize(1050, 650)
        self.setup_ui()
        self.refresh_file_list()
        
    def setup_ui(self):
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
        self.combo_format.addItems(["Video (Mejor)", "Video (1080p)", "Video (720p)", "Audio (MP3)"])
        
        self.combo_codec = QComboBox()
        self.combo_codec.addItems(["MKV + ProRes", "MKV + H.265", "MP4 + H.264", "Original"])
        
        top_layout.addWidget(QLabel("Carpeta:"))
        top_layout.addWidget(self.txt_dir)
        top_layout.addWidget(btn_browse)
        top_layout.addWidget(btn_open_folder)
        top_layout.addWidget(QLabel("Calidad:"))
        top_layout.addWidget(self.combo_format)
        top_layout.addWidget(QLabel("Códec:"))
        top_layout.addWidget(self.combo_codec)
        main_layout.addLayout(top_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 10, 10, 0)
        
        self.text_input = SmartTextEdit()
        self.text_input.setPlaceholderText("⬇️ Arrastra enlaces aquí...\n\n🟢 Verde: Descargado\n🟡 Naranja: Ya existía\n🔴 Rojo: Error")
        
        btn_check_links = QPushButton("🔍 Verificar enlaces existentes")
        btn_check_links.setStyleSheet("background-color: #f9e2af; color: black; padding: 8px;")
        btn_check_links.clicked.connect(self.check_existing_links)
        
        self.lbl_status = QLabel("Esperando enlaces...")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #89b4fa;")
        stats_layout = QHBoxLayout()
        self.lbl_speed = QLabel("Velocidad: -")
        self.lbl_eta = QLabel("ETA: -")
        stats_layout.addWidget(self.lbl_speed)
        stats_layout.addWidget(self.lbl_eta)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("QProgressBar { border: 1px solid #45475a; border-radius: 5px; text-align: center; color: white; } QProgressBar::chunk { background-color: #89b4fa; border-radius: 4px; }")
        
        left_layout.addWidget(self.text_input)
        left_layout.addWidget(btn_check_links)
        left_layout.addWidget(self.lbl_status)
        left_layout.addLayout(stats_layout)
        left_layout.addWidget(self.progress_bar)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 0, 0)
        
        right_layout.addWidget(QLabel("📁 Archivos en destino:"))
        self.list_files = QListWidget()
        self.list_files.setStyleSheet("QListWidget { background-color: #181825; border: 1px solid #313244; border-radius: 8px; padding: 5px; font-size: 13px; }")
        right_layout.addWidget(self.list_files)
        
        btn_refresh_list = QPushButton("🔄 Actualizar Lista")
        btn_refresh_list.clicked.connect(self.refresh_file_list)
        right_layout.addWidget(btn_refresh_list)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([550, 450])
        main_layout.addWidget(splitter)

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 10, 0, 0)
        
        self.btn_update = QPushButton("Actualizar yt-dlp")
        self.btn_update.setStyleSheet("background-color: #313244; padding: 10px; color: white;")
        self.btn_update.clicked.connect(self.update_ytdlp)
        
        self.btn_clear = QPushButton("Limpiar Caja")
        self.btn_clear.setStyleSheet("background-color: #f38ba8; color: black; padding: 10px; font-weight: bold;")
        self.btn_clear.clicked.connect(self.clear_text_box)
        
        self.btn_download = QPushButton("DESCARGAR TODO")
        self.btn_download.setStyleSheet("QPushButton { background-color: #a6e3a1; color: black; font-weight: bold; font-size: 14px; padding: 12px; border-radius: 6px; } QPushButton:hover { background-color: #94e2d5; } QPushButton:disabled { background-color: #585b70; color: #bac2de; }")
        self.btn_download.clicked.connect(self.start_downloads)
        
        bottom_layout.addWidget(self.btn_update)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_clear)
        bottom_layout.addWidget(self.btn_download)
        main_layout.addLayout(bottom_layout)

    def get_format_type(self):
        idx = self.combo_format.currentIndex()
        if idx == 0: return 'best'
        elif idx == 1: return '1080'
        elif idx == 2: return '720'
        else: return 'audio'

    def get_codec_type(self):
        idx = self.combo_codec.currentIndex()
        if idx == 0: return 'prores'
        elif idx == 1: return 'h265'
        elif idx == 2: return 'h264'
        else: return 'original'

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta", self.txt_dir.text())
        if folder: self.txt_dir.setText(folder)

    def open_output_folder(self):
        if os.path.exists(self.txt_dir.text()): QDesktopServices.openUrl(QUrl.fromLocalFile(self.txt_dir.text()))

    def refresh_file_list(self):
        self.list_files.clear()
        folder = self.txt_dir.text()
        if not os.path.exists(folder): return
        v_exts = ('.mp4', '.mkv', '.webm', '.mov'); a_exts = ('.mp3', '.m4a', '.wav')
        try:
            archivos = sorted([f for f in os.listdir(folder) if f.lower().endswith(v_exts + a_exts)])
            for f in archivos:
                ext = os.path.splitext(f)[1].lower()
                self.list_files.addItem(f"🎵 {f}" if ext in a_exts else f"🎬 {f}")
        except: pass

    def clear_text_box(self):
        self.text_input.clear()
        self.reset_text_colors()

    def reset_text_colors(self):
        cursor = self.text_input.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#cdd6f4"))
        fmt.setFontUnderline(False)
        cursor.mergeCharFormat(fmt)

    def parse_input_text(self):
        raw_text = self.text_input.toPlainText()
        parsed_items =[]
        lines = raw_text.split('\n')
        current_title = None
        unique_urls = set()

        for line in lines:
            line = line.strip()
            if not line: continue

            url_match = re.search(r'((?:https?://|www\.)[^\s]+)', line)
            
            if url_match:
                url = url_match.group(1)
                if url.startswith('www.'): url = 'https://' + url

                if url not in unique_urls:
                    unique_urls.add(url)
                    parsed_items.append({'url': url, 'title': current_title})
                
                current_title = None
            else:
                current_title = line
                
        return parsed_items

    def check_existing_links(self):
        items = self.parse_input_text()
        if not items: return
        self.reset_text_colors()
        self.btn_download.setEnabled(False)
        self.lbl_status.setText("Verificando...")
        self.check_worker = CheckExistsWorker(items, self.txt_dir.text(), self.get_format_type(), self.get_codec_type())
        self.check_worker.progress.connect(self.update_progress_bar)
        self.check_worker.item_checked.connect(self.color_link_by_state)
        self.check_worker.finished.connect(lambda:[self.lbl_status.setText("Verificación completada."), self.btn_download.setEnabled(True)])
        self.check_worker.start()

    def update_progress_bar(self, value):
        # Si recibimos -1, ponemos la barra en modo indeterminado (animación de carga continua)
        if value == -1:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value)

    def start_downloads(self):
        items = self.parse_input_text()
        if not items: return
        self.reset_text_colors()
        self.btn_download.setEnabled(False)
        self.text_input.setReadOnly(True)
        self.stats = {'success': 0, 'exists': 0, 'error': 0}
        self.error_details =[] # Reiniciamos registro de errores
        
        self.worker = DownloadWorker(items, self.txt_dir.text(), self.get_format_type(), self.get_codec_type())
        
        self.worker.progress.connect(self.update_progress_bar)
        self.worker.status_update.connect(lambda t, s, e:[
            self.lbl_status.setText(f"Info: {t[:57]}"), 
            self.lbl_speed.setText(f"V: {s}"), 
            self.lbl_eta.setText(f"T: {e}")
        ])
        
        self.worker.item_finished.connect(self.color_link_by_state)
        self.worker.finished.connect(self.downloads_completed)
        self.worker.start()

    def color_link_by_state(self, url, state, error_msg=""):
        if hasattr(self, 'stats') and state in self.stats: self.stats[state] += 1
        
        if state == "success": color, underline = QColor("#a6e3a1"), False
        elif state == "exists": color, underline = QColor("#fab387"), False
        elif state == "error": 
            color, underline = QColor("#f38ba8"), True
            if error_msg:
                self.error_details.append(f"🔗 {url}\n❌ {error_msg.strip()}")
        else: return
        
        url_to_find = url.replace('https://', '') if url.startswith('https://www.') else url
        cursor = self.text_input.document().find(url_to_find)
        if not cursor.isNull():
            fmt = QTextCharFormat()
            fmt.setForeground(color); fmt.setFontUnderline(underline)
            cursor.mergeCharFormat(fmt)

    def downloads_completed(self):
        self.update_progress_bar(100) # Restauramos la barra a su estado normal
        self.lbl_status.setText("Completado.")
        self.btn_download.setEnabled(True)
        self.text_input.setReadOnly(False)
        self.refresh_file_list()
        
        msg = f"✅ Nuevos/Procesados: {self.stats['success']}\n⏭️ Saltados (Ya existían): {self.stats['exists']}\n❌ Errores: {self.stats['error']}"
        
        if hasattr(self, 'error_details') and self.error_details:
            msg += "\n\n⚠️ Detalles de Errores:\n" + "\n\n".join(self.error_details[:3])
            if len(self.error_details) > 3:
                msg += "\n\n... y más errores."
                
        QMessageBox.information(self, "Resumen", msg)

    def update_ytdlp(self):
        self.btn_update.setEnabled(False)
        self.upd_worker = UpdateWorker()
        self.upd_worker.finished.connect(lambda s, m:[self.btn_update.setEnabled(True), QMessageBox.information(self, "Info", m) if s else QMessageBox.critical(self, "Error", m)])
        self.upd_worker.start()