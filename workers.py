import os
import re
import subprocess
import yt_dlp
from PyQt6.QtCore import QThread, pyqtSignal
from utils import YtDlpLogger

class DownloadWorker(QThread):
    progress = pyqtSignal(int)
    status_update = pyqtSignal(str, str, str)
    item_finished = pyqtSignal(str, str)
    finished = pyqtSignal()
    
    def __init__(self, urls, download_dir, format_type):
        super().__init__()
        self.urls = urls
        self.download_dir = download_dir
        self.format_type = format_type 

    def run(self):
        for url in self.urls:
            logger = YtDlpLogger()
            success = True
            
            ydl_opts = {
                'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
                'progress_hooks': [self.hook],
                'logger': logger,
                'nocolor': True, 'ignoreerrors': True, 'quiet': True, 'no_warnings': True,
                'nooverwrites': True,
                'writethumbnail': True, 
            }

            thumb_pp = {'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'}

            if self.format_type == 'audio':
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [
                        {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
                        thumb_pp
                    ]
                })
            else:
                # Lógica para forzar MP4
                if self.format_type == '1080':
                    vid_f = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best'
                elif self.format_type == '720':
                    vid_f = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best'
                else: 
                    vid_f = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'
                
                ydl_opts.update({
                    'format': vid_f,
                    'merge_output_format': 'mp4',
                    'recodevideo': 'mp4', # FORZAR CONVERSIÓN A MP4
                    'postprocessors': [thumb_pp]
                })

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    error_code = ydl.download([url])
                    if error_code != 0: success = False
            except Exception:
                success = False

            estado = "error" if not success else ("exists" if logger.already_exists else "success")
            self.item_finished.emit(url, estado)
            
        self.finished.emit()

    def hook(self, d):
        if d['status'] == 'downloading':
            p = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_percent_str', '0%').replace('%', '').strip()) 
            try: self.progress.emit(int(float(p)))
            except: pass
            s = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_speed_str', '...'))
            e = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_eta_str', '...'))
            f = os.path.basename(d.get('filename', 'Descargando...'))
            self.status_update.emit(f, s, e)
        elif d['status'] == 'finished':
            self.progress.emit(100)
            self.status_update.emit("Finalizando/Convirtiendo a MP4...", "-", "-")

class CheckExistsWorker(QThread):
    progress = pyqtSignal(int)
    item_checked = pyqtSignal(str, str)
    finished = pyqtSignal()

    def __init__(self, urls, download_dir, format_type):
        super().__init__()
        self.urls = urls
        self.download_dir = download_dir
        self.format_type = format_type

    def run(self):
        total = len(self.urls)
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True} 
        
        try: archivos = os.listdir(self.download_dir) if os.path.exists(self.download_dir) else []
        except: archivos = []

        valid_exts = ['.mp3', '.m4a'] if self.format_type == 'audio' else ['.mp4', '.mkv', '.webm']

        for i, url in enumerate(self.urls):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', '')
                    if not title:
                        self.item_checked.emit(url, "error")
                        continue

                    safe_title = re.sub(r'[\\/*?:"<>|]', '', title)
                    exists = any(safe_title[:15] in arch and any(arch.endswith(ext) for ext in valid_exts) for arch in archivos)
                    
                    self.item_checked.emit(url, "exists" if exists else "missing")
            except:
                self.item_checked.emit(url, "error")
                
            self.progress.emit(int((i+1)/total * 100))
        self.finished.emit()

class ThumbnailLoaderWorker(QThread):
    thumbnail_loaded = pyqtSignal(int, str)

    def __init__(self, folder, files):
        super().__init__()
        self.folder = folder
        self.files = files

    def run(self):
        thumb_exts = ['.jpg', '.png', '.webp'] # Ahora el JPG es la prioridad
        for row, filename in self.files:
            base_name = os.path.splitext(filename)[0]
            for ext in thumb_exts:
                potential_path = os.path.join(self.folder, base_name + ext)
                if os.path.exists(potential_path):
                    self.thumbnail_loaded.emit(row, potential_path)
                    break

class UpdateWorker(QThread):
    finished = pyqtSignal(bool, str)
    def run(self):
        try:
            res = subprocess.run("yt-dlp -U", shell=True, capture_output=True, text=True)
            if res.returncode == 0: self.finished.emit(True, "¡yt-dlp actualizado!\n" + res.stdout)
            else:
                res2 = subprocess.run("pip install --upgrade yt-dlp", shell=True, capture_output=True, text=True)
                self.finished.emit(True, "Actualizado vía pip.") if res2.returncode == 0 else self.finished.emit(False, f"Error:\n{res2.stderr}")
        except Exception as e:
            self.finished.emit(False, str(e))