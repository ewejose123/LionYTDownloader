import re
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QColor, QTextCharFormat
from PyQt6.QtCore import Qt

class YtDlpLogger:
    """Interceptor para saber si yt-dlp se saltó un archivo por ya existir."""
    def __init__(self):
        self.already_exists = False
    def debug(self, msg): self._check(msg)
    def info(self, msg): self._check(msg)
    def warning(self, msg): self._check(msg)
    def error(self, msg): pass
    def _check(self, msg):
        if "has already been downloaded" in msg or "already exists" in msg:
            self.already_exists = True

class SmartTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        # caret-color arregla el problema del cursor invisible al hacer clic
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #cdd6f4;
                caret-color: #ffffff; 
                border: 2px dashed #555555;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }
        """)

    def keyPressEvent(self, event):
        # Evita que al editar a mano sigas escribiendo en rojo o verde
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#cdd6f4"))
        fmt.setFontUnderline(False)
        self.setCurrentCharFormat(fmt)
        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet(self.styleSheet() + "background-color: #242536; border-color: #89b4fa;")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self.styleSheet().replace("background-color: #242536; border-color: #89b4fa;", ""))

    def dropEvent(self, event):
        self.dragLeaveEvent(event)
        mime = event.mimeData()
        urls_to_add = []
        
        if mime.hasUrls():
            for url in mime.urls():
                if url.scheme() in ['http', 'https']:
                    urls_to_add.append(url.toString())
        elif mime.hasText():
            text = mime.text()
            extracted = re.findall(r'(https?://[^\s]+)', text)
            if extracted:
                urls_to_add.extend(extracted)
            else:
                urls_to_add.append(text)
                
        if urls_to_add:
            # Reseteamos el color antes de inyectar texto arrastrado
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#cdd6f4"))
            self.setCurrentCharFormat(fmt)
            
            current_text = self.toPlainText()
            new_text = "\n".join(urls_to_add)
            if current_text and not current_text.endswith('\n'):
                self.insertPlainText("\n" + new_text + "\n")
            else:
                self.insertPlainText(new_text + "\n")
                
        event.acceptProposedAction()