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
    
    def __init__(self, items, download_dir, format_type):
        super().__init__()
        self.items = items # Lista de diccionarios [{'url': url, 'title': custom_title}]
        self.download_dir = download_dir
        self.format_type = format_type 

    def run(self):
        for item in self.items:
            url = item['url']
            custom_title = item['title']
            logger = YtDlpLogger()
            success = True
            
            ydl_opts = {
                'progress_hooks': [self.hook],
                'logger': logger,
                'nocolor': True, 'ignoreerrors': True, 'quiet': True, 'no_warnings': True,
                'nooverwrites': True,
                'writethumbnail': False, 
            }

            # --- ASIGNACIÓN DE NOMBRE ---
            if custom_title:
                # Limpia caracteres prohibidos en nombres de archivo de Windows
                safe_title = re.sub(r'[\\/*?:"<>|]', '', custom_title).strip()
                if safe_title:
                    ydl_opts['outtmpl'] = os.path.join(self.download_dir, f"{safe_title}.%(ext)s")
                else:
                    ydl_opts['outtmpl'] = os.path.join(self.download_dir, '%(title)s.%(ext)s')
            else:
                ydl_opts['outtmpl'] = os.path.join(self.download_dir, '%(title)s.%(ext)s')

            # --- FORMATOS ---
            if self.format_type == 'audio':
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
                })
            else:
                if self.format_type == '1080':
                    vid_f = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best'
                elif self.format_type == '720':
                    vid_f = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best'
                else: 
                    vid_f = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'
                
                ydl_opts.update({
                    'format': vid_f,
                    'merge_output_format': 'mp4',
                    'recodevideo': 'mp4'
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
            self.status_update.emit("Finalizando...", "-", "-")

class CheckExistsWorker(QThread):
    progress = pyqtSignal(int)
    item_checked = pyqtSignal(str, str)
    finished = pyqtSignal()

    def __init__(self, items, download_dir, format_type):
        super().__init__()
        self.items = items
        self.download_dir = download_dir
        self.format_type = format_type

    def run(self):
        total = len(self.items)
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True} 
        try: archivos = os.listdir(self.download_dir) if os.path.exists(self.download_dir) else []
        except: archivos = []
        valid_exts = ['.mp3', '.m4a'] if self.format_type == 'audio' else ['.mp4', '.mkv', '.webm']

        for i, item in enumerate(self.items):
            url = item['url']
            custom_title = item['title']
            safe_title = None

            if custom_title:
                safe_title = re.sub(r'[\\/*?:"<>|]', '', custom_title).strip()

            try:
                # Si no hay titulo custom, preguntamos a Youtube por el nombre
                if not safe_title:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        title = info.get('title', '')
                        if title:
                            safe_title = re.sub(r'[\\/*?:"<>|]', '', title)
                        else:
                            self.item_checked.emit(url, "error")
                            continue

                # Chequear coincidencia
                exists = any(arch.startswith(safe_title[:15]) and any(arch.endswith(ext) for ext in valid_exts) for arch in archivos)
                self.item_checked.emit(url, "exists" if exists else "missing")
            except:
                self.item_checked.emit(url, "error")
                
            self.progress.emit(int((i+1)/total * 100))
        self.finished.emit()

class UpdateWorker(QThread):
    finished = pyqtSignal(bool, str)
    def run(self):
        try:
            res = subprocess.run("yt-dlp -U", shell=True, capture_output=True, text=True)
            if res.returncode == 0: self.finished.emit(True, "¡yt-dlp actualizado!\n" + res.stdout)
            else:
                res2 = subprocess.run("pip install --upgrade yt-dlp", shell=True, capture_output=True, text=True)
                self.finished.emit(True, "Actualizado vía pip.") if res2.returncode == 0 else self.finished.emit(False, f"Error:\n{res2.stderr}")
        except Exception as e: self.finished.emit(False, str(e))