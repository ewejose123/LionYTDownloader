import ctypes
import os
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from ui import MainWindow


def resource_path(relative_path: str) -> str:
    """Obtiene la ruta absoluta a los recursos (necesario para PyInstaller)."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def apply_theme(app: QApplication) -> None:
    try:
        import qdarktheme

        app.setStyleSheet(qdarktheme.load_stylesheet("dark"))
    except (ImportError, AttributeError):
        app.setStyle("Fusion")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    myappid = "LionApps.YTDownloader.YTD.1"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app_icon = QIcon(resource_path("icon.ico"))
    app.setWindowIcon(app_icon)
    apply_theme(app)

    tray = QSystemTrayIcon(app_icon, app)
    tray.setToolTip("Lion YT Downloader")

    window = MainWindow(tray_icon=tray)
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray.show()

    window.show()
    sys.exit(app.exec())
