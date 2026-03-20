import os
import re
import subprocess
import yt_dlp
from PyQt6.QtCore import QThread, pyqtSignal
from utils import YtDlpLogger

class DownloadWorker(QThread):
    progress = pyqtSignal(int)
    status_update = pyqtSignal(str, str, str)
    item_finished = pyqtSignal(str, str, str) # Añadido parámetro string extra para el mensaje de error
    finished = pyqtSignal()
    
    def __init__(self, items, download_dir, format_type, codec_type):
        super().__init__()
        self.items = items 
        self.download_dir = download_dir
        self.format_type = format_type 
        self.codec_type = codec_type

    def run(self):
        for item in self.items:
            url = item['url']
            custom_title = item['title']
            self.current_logger = YtDlpLogger()
            success = True
            
            ydl_opts = {
                'progress_hooks': [self.hook],
                'postprocessor_hooks':[self.pp_hook],
                'logger': self.current_logger,
                'nocolor': True, 'quiet': True, 'no_warnings': True,
                'nooverwrites': True,
                'writethumbnail': False, 
            }

            if custom_title:
                safe_title = re.sub(r'[\\/*?:"<>|]', '', custom_title).strip()
                if safe_title:
                    ydl_opts['outtmpl'] = os.path.join(self.download_dir, f"{safe_title}.%(ext)s")
                else:
                    ydl_opts['outtmpl'] = os.path.join(self.download_dir, '%(title)s.%(ext)s')
            else:
                ydl_opts['outtmpl'] = os.path.join(self.download_dir, '%(title)s.%(ext)s')

            # --- FORMATOS Y CÓDECS ---
            if self.format_type == 'audio':
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors':[{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
                })
            else:
                if self.codec_type == 'original':
                    if self.format_type == '1080':
                        vid_f = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best'
                    elif self.format_type == '720':
                        vid_f = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best'
                    else: 
                        vid_f = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'
                else:
                    if self.format_type == '1080':
                        vid_f = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best'
                    elif self.format_type == '720':
                        vid_f = 'bestvideo[height<=720]+bestaudio/best[height<=720]/best'
                    else: 
                        vid_f = 'bestvideo+bestaudio/best'
                
                ydl_opts['format'] = vid_f

                # --- LÓGICA DE RECODIFICADO SEGURA (DICCIONARIOS) ---
                # Pasamos los parámetros de FFmpeg EXCLUSIVAMENTE a las fases que lo necesitan (merger o convert).
                # Si lo pasamos de forma global, provocará crasheos al intentar recodificar audios o portadas.
                codec_args =[]
                target_ext = 'mkv'

                if self.codec_type == 'prores':
                    codec_args =['-c:v', 'prores_ks', '-profile:v', '1', '-pix_fmt', 'yuv422p10le', '-c:a', 'copy']
                    target_ext = 'mkv'
                elif self.codec_type == 'h265':
                    codec_args =['-c:v', 'libx265', '-crf', '26', '-preset', 'fast', '-c:a', 'copy']
                    target_ext = 'mkv'
                elif self.codec_type == 'h264':
                    codec_args =['-c:v', 'libx264', '-crf', '23', '-preset', 'fast', '-c:a', 'copy']
                    target_ext = 'mp4'

                if self.codec_type != 'original':
                    ydl_opts.update({
                        'merge_output_format': target_ext,
                        'recodevideo': target_ext,
                        'postprocessor_args': {
                            'merger': codec_args,        # Se aplica al unir las pistas (si bajaron separadas)
                            'video_convert': codec_args  # Se aplica si ya bajaron unidas y toca recodificar
                        }
                    })
                else: 
                    ydl_opts.update({
                        'merge_output_format': 'mp4',
                        'recodevideo': 'mp4'
                    })

            # Ejecutamos la descarga capturando la excepción directa
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    error_code = ydl.download([url])
                    if error_code != 0: 
                        success = False
            except Exception as e:
                success = False
                self.current_logger.last_error = str(e)

            # Control final de estados
            clean_err = ""
            if not success:
                estado = "error"
                # Limpiamos los códigos de color ANSI de la consola para que la UI lo lea en texto plano limpio
                raw_err = self.current_logger.last_error
                clean_err = re.sub(r'\x1b\[[0-9;]*m', '', raw_err) if raw_err else "Error interno de descarga o FFmpeg."
            elif self.current_logger.already_exists:
                estado = "exists"
            else:
                estado = "success"
                
            self.item_finished.emit(url, estado, clean_err)
            
        self.finished.emit()

    def hook(self, d):
        if d['status'] == 'downloading':
            p = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_percent_str', '0%').replace('%', '').strip()) 
            try: self.progress.emit(int(float(p)))
            except: pass
            s = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_speed_str', '...'))
            e = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_eta_str', '...'))
            f = os.path.basename(d.get('filename', 'Descargando...'))
            self.status_update.emit(f"Descargando temp: {f[:25]}...", s, e)
            
        elif d['status'] == 'finished':
            self.progress.emit(100)
            self.status_update.emit("Descarga completada. Preparando datos...", "-", "-")

    def pp_hook(self, d):
        """ Este hook intercepta la fase de procesamiento (unión de video/audio y recodificación) """
        if d['status'] == 'started':
            self.progress.emit(-1)
            
            # ¡CLAVE AQUÍ! Si está en esta fase, está haciendo trabajo real de procesamiento.
            # Quitamos la marca de "already_exists" por si intentó reanudar algo de antes y lo logró.
            self.current_logger.already_exists = False
            
            if self.codec_type in['prores', 'h265']:
                self.status_update.emit(f"Codificando a {self.codec_type.upper()}... (Esto tardará minutos)", "-", "-")
            else:
                self.status_update.emit("Procesando códec / Uniendo video y audio...", "-", "-")
                
        elif d['status'] == 'finished':
            self.status_update.emit("Procesado de archivo finalizado.", "-", "-")

class CheckExistsWorker(QThread):
    progress = pyqtSignal(int)
    item_checked = pyqtSignal(str, str, str) # Añadido el tercer parámetro string para matchear con la UI
    finished = pyqtSignal()

    def __init__(self, items, download_dir, format_type, codec_type):
        super().__init__()
        self.items = items
        self.download_dir = download_dir
        self.format_type = format_type
        self.codec_type = codec_type

    def run(self):
        total = len(self.items)
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True} 
        try: archivos = os.listdir(self.download_dir) if os.path.exists(self.download_dir) else []
        except: archivos =[]
        
        valid_exts = ['.mp3', '.m4a', '.wav'] if self.format_type == 'audio' else ['.mp4', '.mkv', '.webm', '.mov']

        for i, item in enumerate(self.items):
            url = item['url']
            custom_title = item['title']
            safe_title = None

            if custom_title:
                safe_title = re.sub(r'[\\/*?:"<>|]', '', custom_title).strip()

            try:
                if not safe_title:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        title = info.get('title', '')
                        if title:
                            safe_title = re.sub(r'[\\/*?:"<>|]', '', title)
                        else:
                            self.item_checked.emit(url, "error", "No se pudo extraer el título del enlace.")
                            continue

                exists = any(arch.startswith(safe_title[:15]) and any(arch.endswith(ext) for ext in valid_exts) for arch in archivos)
                self.item_checked.emit(url, "exists" if exists else "missing", "")
            except Exception as e:
                self.item_checked.emit(url, "error", str(e))
                
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