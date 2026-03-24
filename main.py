# =============================================================================
# FUTURA SETUP v4.3.0 -- Entry Point
# =============================================================================

import sys
import os
import subprocess

# -- Patch para evitar janelas de console no Windows (PyInstaller) --
if os.name == 'nt':
    _original_popen = subprocess.Popen
    def _patched_popen(*args, **kwargs):
        if 'creationflags' not in kwargs:
            kwargs['creationflags'] = 0x08000000  # CREATE_NO_WINDOW
        return _original_popen(*args, **kwargs)
    subprocess.Popen = _patched_popen  # type: ignore

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from ui.theme import get_stylesheet, set_theme
from ui.theme_manager import theme_manager
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow
from core.logger import log

# =============================================================================

def _app_icon() -> QIcon:
    candidates = []
    if getattr(sys, 'frozen', False):
        candidates.append(os.path.join(sys._MEIPASS, 'futura.ico'))
        candidates.append(os.path.join(os.path.dirname(sys.executable), 'futura.ico'))
    else:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'futura.ico'))
    for path in candidates:
        if os.path.isfile(path):
            return QIcon(path)
    return QIcon()


def _app_icon_path() -> str:
    if getattr(sys, 'frozen', False):
        candidates = [
            os.path.join(sys._MEIPASS, 'futura.ico'),
            os.path.join(os.path.dirname(sys.executable), 'futura.ico'),
        ]
    else:
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'futura.ico'),
        ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return ""


def _force_taskbar_icon(window):
    """Garante que o ícone apareça na barra de tarefas do Windows."""
    if sys.platform != "win32":
        return
    ico_path = _app_icon_path()
    if not ico_path:
        return
    try:
        import ctypes
        hwnd = int(window.winId())
        hicon_big = ctypes.windll.user32.LoadImageW(
            None, ico_path, 1, 256, 256, 0x00000010
        )
        hicon_small = ctypes.windll.user32.LoadImageW(
            None, ico_path, 1, 16, 16, 0x00000010
        )
        WM_SETICON = 0x0080
        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 1, hicon_big)
        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 0, hicon_small)
    except Exception:
        pass


def main():
    app = QApplication(sys.argv)
    
    icon = _app_icon()
    app.setWindowIcon(icon)
    app.setApplicationName("Futura Setup")
    app.setOrganizationName("Futura Sistemas")

    # Aplica tema inicial
    saved_mode = log.prefs.theme
    app.setStyleSheet(get_stylesheet(saved_mode))
    set_theme(saved_mode)

    # Conecta mudança de tema global
    theme_manager.theme_changed.connect(
        lambda mode: app.setStyleSheet(get_stylesheet(mode))
    )

    # -- Fluxo de Login --
    login = LoginDialog(app_icon_fn=_app_icon)
    login.exec()
    
    if not login.autenticado():
        sys.exit(0)

    # -- Janela Principal --
    window = MainWindow(app_icon_fn=_app_icon)
    window.show()

    _force_taskbar_icon(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    # Suporte para freezing (PyInstaller)
    if os.name == 'nt':
        import multiprocessing
        multiprocessing.freeze_support()
    
    main()