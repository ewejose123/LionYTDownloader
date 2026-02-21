import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui import MainWindow

def resource_path(relative_path):
    """Obtiene la ruta absoluta a los recursos (necesario para PyInstaller)"""
    try:
        # PyInstaller crea una carpeta temporal _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # --- AÑADE ESTO PARA QUE EL ICONO SE VEA EN LA BARRA DE TAREAS ---
    import ctypes
    myappid = 'LionApps.YTDownloader.YTD.1' # Una cadena única
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    # -----------------------------------------------------------------

    app_icon = QIcon(resource_path("icon.ico"))
    app.setWindowIcon(app_icon)
    
    try:
        import qdarktheme
        qdarktheme.setup_theme("dark", custom_colors={"primary": "#89b4fa"})
    except Exception as e:
        print("Tema oscuro no cargado:", e)
        app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())