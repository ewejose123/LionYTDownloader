import re
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QColor, QTextCharFormat
from PyQt6.QtCore import Qt

class YtDlpLogger:
    def __init__(self):
        self.already_exists = False
        self.last_error = ""
        
    def debug(self, msg): self._check(msg)
    def info(self, msg): self._check(msg)
    def warning(self, msg): self._check(msg)
    
    def error(self, msg):
        self.last_error = msg
        self._check(msg)
        
    def _check(self, msg):
        # Solo marcamos como "already_exists" si salta el mensaje exacto de finalización
        if "has already been downloaded" in msg or "already exists" in msg:
            self.already_exists = True

class SmartTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
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

    def insertFromMimeData(self, source):
        # Esta función asegura que cualquier texto pegado (Ctrl+V o click derecho) entre sin formato
        if source.hasText():
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#cdd6f4"))
            fmt.setFontUnderline(False)
            self.setCurrentCharFormat(fmt)
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)

    def keyPressEvent(self, event):
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
        
        text_to_insert = ""
        if mime.hasText():
            text_to_insert = mime.text()
        elif mime.hasUrls():
            urls =[u.toString() for u in mime.urls() if u.scheme() in ['http', 'https']]
            text_to_insert = "\n".join(urls)
            
        if text_to_insert:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#cdd6f4"))
            self.setCurrentCharFormat(fmt)
            
            current_text = self.toPlainText()
            if current_text and not current_text.endswith('\n'):
                self.insertPlainText("\n" + text_to_insert + "\n")
            else:
                self.insertPlainText(text_to_insert + "\n")
                
        event.acceptProposedAction()