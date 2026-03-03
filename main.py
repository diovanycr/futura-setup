# =============================================================================
# FUTURA SETUP v4.3.0 -- Main Window
# =============================================================================

import sys
import os
import platform
import hashlib
import time

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QLabel, QFrame,
    QStackedWidget, QSizePolicy, QDialog,
    QLineEdit, QPushButton
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon

from ui.theme import COLORS, FONT_SANS, FONT_MONO, get_stylesheet, set_theme
from ui.theme_manager import theme_manager
from ui.widgets import spacer, h_line, WorkerGuardDialog
from ui.page_menu               import PageMenu
from ui.page_scan               import PageScan
from ui.page_atalhos            import PageAtalhos
from ui.page_terminal           import PageTerminal
from ui.page_restaurar          import PageRestaurar
from ui.page_log                import PageLog
from ui.page_atualizacao        import PageAtualizacao
from ui.page_backup_gbak        import PageBackupGbak
from ui.page_port_opener        import PagePortOpener
from ui.page_diagnostico        import PageDiagnostico
from ui.page_editar_funcionario import PageEditarFuncionario
from core.logger                import log
from config                     import APP_VERSION

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


def _force_taskbar_icon(window: QMainWindow):
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
# =============================================================================

_SENHA_HASH = "1cfafff6d51a03662b85b93dc3417f51687034ba9a46682f5328257eff7133ed"  # senha: 1313

_LOGIN_MAX_TENTATIVAS = 3
_LOGIN_BLOQUEIO_SEG   = 30


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Futura Setup — Acesso")
        self.setWindowIcon(_app_icon())
        self.setFixedSize(360, 260)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.MSWindowsFixedSizeDialogHint
        )

        self._tentativas  = 0
        self._bloqueado   = False
        self._autenticado = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(12)

        titulo = QLabel("🔒  Futura Setup")
        titulo.setFont(QFont(FONT_SANS, 15, QFont.Weight.Bold))
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitulo = QLabel("Digite a senha para continuar")
        subtitulo.setFont(QFont(FONT_SANS, 11))
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._campo = QLineEdit()
        self._campo.setEchoMode(QLineEdit.EchoMode.Password)
        self._campo.setPlaceholderText("Senha")
        self._campo.setFixedHeight(38)
        self._campo.setFont(QFont(FONT_SANS, 12))
        self._campo.returnPressed.connect(self._verificar)

        self._msg = QLabel("")
        self._msg.setFont(QFont(FONT_SANS, 11))
        self._msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg.setWordWrap(True)

        self._btn = QPushButton("Entrar")
        self._btn.setFixedHeight(38)
        self._btn.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._verificar)

        lay.addWidget(titulo)
        lay.addWidget(subtitulo)
        lay.addSpacing(8)
        lay.addWidget(self._campo)
        lay.addWidget(self._msg)
        lay.addWidget(self._btn)

        self._upd_style()

    def _upd_style(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {COLORS['surface']};
            }}
            QLineEdit {{
                background: {COLORS['bg']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 0 12px;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {COLORS['accent']};
            }}
            QPushButton {{
                background: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {COLORS['accent']};
                opacity: 0.9;
            }}
            QPushButton:disabled {{
                background: {COLORS['text_disabled']};
                color: {COLORS['text_dim']};
            }}
        """)

    def _verificar(self):
        if self._bloqueado:
            return
        senha = self._campo.text()
        hash_digitado = hashlib.sha256(senha.encode()).hexdigest()
        if hash_digitado == _SENHA_HASH:
            self._autenticado = True
            self.accept()
        else:
            self._tentativas += 1
            restam = _LOGIN_MAX_TENTATIVAS - self._tentativas
            self._campo.clear()
            if self._tentativas >= _LOGIN_MAX_TENTATIVAS:
                self._bloquear()
            else:
                self._msg.setStyleSheet(f"color: {COLORS['danger']};")
                self._msg.setText(
                    f"Senha incorreta. {restam} tentativa{'s' if restam > 1 else ''} restante{'s' if restam > 1 else ''}."
                )

    def _bloquear(self):
        self._bloqueado    = True
        self._campo.setEnabled(False)
        self._btn.setEnabled(False)
        self._tempo_restante = _LOGIN_BLOQUEIO_SEG
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick_bloqueio)
        self._timer.start()
        self._tick_bloqueio()

    def _tick_bloqueio(self):
        self._msg.setStyleSheet(f"color: {COLORS['warn']};")
        self._msg.setText(
            f"Muitas tentativas. Aguarde {self._tempo_restante}s para tentar novamente."
        )
        self._tempo_restante -= 1
        if self._tempo_restante < 0:
            self._timer.stop()
            self._bloqueado   = False
            self._tentativas  = 0
            self._campo.setEnabled(True)
            self._btn.setEnabled(True)
            self._msg.setStyleSheet(f"color: {COLORS['text_mid']};")
            self._msg.setText("Você pode tentar novamente.")
            self._campo.setFocus()

    def autenticado(self) -> bool:
        return self._autenticado


import ctypes as _ctypes
try:
    IS_ADMIN: bool = bool(_ctypes.windll.shell32.IsUserAnAdmin())
except Exception:
    IS_ADMIN = False


# ── NAV ITEM ──────────────────────────────────────────────────────────────────

class NavItem(QWidget):
    def __init__(self, text: str, icon: str = "", parent=None):
        super().__init__(parent)
        self._active   = False
        self._enabled  = True
        self._busy     = False
        self._callback = None
        self._spin_frame = 0
        self._spin_frames = ["◐", "◓", "◑", "◒"]
        self._orig_icon  = icon
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(10)

        self._indicator = QWidget()
        self._indicator.setFixedSize(3, 16)

        if icon:
            self._icon_lbl = QLabel(icon)
            self._icon_lbl.setFont(QFont(FONT_SANS, 13))
            self._icon_lbl.setFixedWidth(18)
            self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(self._icon_lbl)

        self._lbl = QLabel(text)
        self._lbl.setFont(QFont(FONT_SANS, 13))

        lay.addWidget(self._indicator)
        lay.addWidget(self._lbl, 1)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _set_styles(self, bg: str, indicator: str, text_color: str, weight: str = ""):
        self.setStyleSheet(f"background: {bg}; border-radius: 4px;")
        self._indicator.setStyleSheet(f"background: {indicator};")
        style = f"color: {text_color}; background: transparent;"
        if weight:
            style += f" font-weight: {weight};"
        self._lbl.setStyleSheet(style)
        if hasattr(self, "_icon_lbl"):
            self._icon_lbl.setStyleSheet(f"color: {text_color}; background: transparent;")

    def _upd(self, _mode: str = ""):
        if self._busy:
            self._set_styles(COLORS["accent_dim"], COLORS["warn"], COLORS["warn"], "600")
        elif self._active:
            self._set_styles(COLORS["accent_dim"], COLORS["accent"], COLORS["accent"], "600")
        elif not self._enabled:
            self._set_styles("transparent", "transparent", COLORS["text_disabled"])
        else:
            self._set_styles("transparent", "transparent", COLORS["text_mid"])

    def set_active(self, v: bool):
        self._active = v
        self._upd()

    def set_enabled(self, v: bool):
        self._enabled = v
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if v else Qt.CursorShape.ArrowCursor
        )
        self._upd()

    def set_busy(self, v: bool):
        self._busy = v
        if hasattr(self, "_icon_lbl"):
            if v:
                self._spin_frame = 0
                self._icon_lbl.setText(self._spin_frames[0])
            else:
                self._icon_lbl.setText(self._orig_icon)
        self._upd()

    def _spin_tick(self):
        if self._busy and hasattr(self, "_icon_lbl"):
            self._spin_frame = (self._spin_frame + 1) % len(self._spin_frames)
            self._icon_lbl.setText(self._spin_frames[self._spin_frame])

    def on_click(self, fn):
        self._callback = fn

    def mousePressEvent(self, e):
        if self._enabled and e.button() == Qt.MouseButton.LeftButton:
            if self._callback:
                self._callback()

    def enterEvent(self, e):
        if self._enabled and not self._active:
            self.setStyleSheet(f"background: {COLORS['panel_hover']}; border-radius: 4px;")

    def leaveEvent(self, e):
        self._upd()


# ── NAV SECTION LABEL ─────────────────────────────────────────────────────────

class NavSectionLabel(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont(FONT_SANS, 11))
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(
            f"color: {COLORS['text_dim']}; background: transparent;"
            f"padding: 12px 12px 4px 12px;"
        )


# ── THEME TOGGLE ──────────────────────────────────────────────────────────────

class ThemeToggleBtn(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(10)

        self._icon = QLabel()
        self._icon.setFont(QFont(FONT_SANS, 13))
        self._icon.setFixedWidth(18)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._lbl = QLabel()
        self._lbl.setFont(QFont(FONT_SANS, 13))

        ind = QWidget()
        ind.setFixedSize(3, 16)
        ind.setStyleSheet("background: transparent;")

        lay.addWidget(self._icon)
        lay.addWidget(ind)
        lay.addWidget(self._lbl, 1)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        is_dark = theme_manager.mode == "dark"
        self._icon.setText("🌙" if is_dark else "☀️")
        self._lbl.setText("Modo escuro" if is_dark else "Modo claro")
        self._icon.setStyleSheet("background: transparent;")
        self._lbl.setStyleSheet(f"color: {COLORS['text_mid']}; background: transparent;")
        self.setStyleSheet("background: transparent; border-radius: 4px;")

    def enterEvent(self, e):
        self.setStyleSheet(f"background: {COLORS['panel_hover']}; border-radius: 4px;")

    def leaveEvent(self, e):
        self.setStyleSheet("background: transparent; border-radius: 4px;")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            theme_manager.toggle()


# ── FOOTER WIDGET ─────────────────────────────────────────────────────────────

class FooterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(3)

        dot_color  = COLORS["accent2"] if IS_ADMIN else COLORS["warn"]
        status_txt = "Administrador" if IS_ADMIN else "Usuário padrão"

        row = QHBoxLayout()
        row.setSpacing(7)
        self._admin_dot = QWidget()
        self._admin_dot.setFixedSize(7, 7)
        self._admin_dot.setStyleSheet(f"background: {dot_color}; border-radius: 4px;")
        self._admin_st = QLabel(status_txt)
        self._admin_st.setFont(QFont(FONT_SANS, 11))
        row.addWidget(self._admin_dot)
        row.addWidget(self._admin_st, 1)
        row_w = QWidget()
        row_w.setLayout(row)
        row_w.setStyleSheet("background: transparent;")

        self._ver_lbl = QLabel(f"v{APP_VERSION}")
        self._ver_lbl.setFont(QFont(FONT_SANS, 10))

        lay.addWidget(row_w)
        lay.addWidget(self._ver_lbl)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        dot_color = COLORS["accent2"] if IS_ADMIN else COLORS["warn"]
        self._admin_dot.setStyleSheet(f"background: {dot_color}; border-radius: 4px;")
        self._admin_st.setStyleSheet(f"color: {COLORS['text_mid']}; background: transparent;")
        self._ver_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")


# ── SIDEBAR ───────────────────────────────────────────────────────────────────

class Sidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._inner = QWidget()
        inner_lay = QVBoxLayout(self._inner)
        inner_lay.setContentsMargins(8, 0, 8, 12)
        inner_lay.setSpacing(1)

        header = QWidget()
        header.setStyleSheet("background: transparent;")
        header_lay = QVBoxLayout(header)
        header_lay.setContentsMargins(12, 20, 12, 16)

        self._logo = QLabel("Futura Setup")
        self._logo.setFont(QFont(FONT_SANS, 15, QFont.Weight.Bold))

        self._logo_sub = QLabel("Configuração de Terminal")
        self._logo_sub.setFont(QFont(FONT_SANS, 11))

        header_lay.addWidget(self._logo)
        header_lay.addWidget(self._logo_sub)
        inner_lay.addWidget(header)

        self._div_top = self._make_divider()
        inner_lay.addWidget(self._div_top)
        inner_lay.addWidget(spacer(h=4))

        self.nav_menu = NavItem("Menu Principal", "⊞")
        inner_lay.addWidget(self.nav_menu)

        inner_lay.addWidget(NavSectionLabel("Operações"))
        self.nav_atalhos     = NavItem("Puxar via Rede",    "↓")
        self.nav_terminal    = NavItem("Novo Terminal",     "□")
        self.nav_atualizacao = NavItem("Atualizar Sistema", "↑")
        inner_lay.addWidget(self.nav_atalhos)
        inner_lay.addWidget(self.nav_terminal)
        inner_lay.addWidget(self.nav_atualizacao)

        inner_lay.addWidget(NavSectionLabel("Utilitários"))
        self.nav_log          = NavItem("Ver Log",             "≡")
        self.nav_backup_gbak  = NavItem("Backup/Restaure DB", "💾")
        self.nav_port_opener  = NavItem("Firewall — Portas",  "🔓")
        self.nav_diagnostico  = NavItem("Diagnóstico",        "🔍")
        self.nav_editar_func  = NavItem("Editar Funcionário", "✏️")
        inner_lay.addWidget(self.nav_log)
        inner_lay.addWidget(self.nav_backup_gbak)
        inner_lay.addWidget(self.nav_port_opener)
        inner_lay.addWidget(self.nav_diagnostico)
        inner_lay.addWidget(self.nav_editar_func)

        self.nav_atalhos.set_enabled(False)
        self.nav_terminal.set_enabled(False)

        inner_lay.addStretch()

        self._div_bot = self._make_divider()
        inner_lay.addWidget(self._div_bot)
        inner_lay.addWidget(spacer(h=4))
        inner_lay.addWidget(ThemeToggleBtn())
        inner_lay.addWidget(spacer(h=4))
        inner_lay.addWidget(FooterWidget())

        self._border = QFrame()
        self._border.setFixedWidth(1)

        root.addWidget(self._inner, 1)
        root.addWidget(self._border)

        self._all = [
            self.nav_menu, self.nav_atalhos, self.nav_terminal,
            self.nav_atualizacao, self.nav_log,
            self.nav_backup_gbak, self.nav_port_opener, self.nav_diagnostico,
            self.nav_editar_func,
        ]

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _make_divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        return line

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(f"background: {COLORS['surface2']};")
        self._inner.setStyleSheet(f"background: {COLORS['surface2']};")
        self._border.setStyleSheet(f"background: {COLORS['border']}; border: none;")
        self._div_top.setStyleSheet(f"background: {COLORS['border']}; border: none;")
        self._div_bot.setStyleSheet(f"background: {COLORS['border']}; border: none;")
        self._logo.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        self._logo_sub.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")

    def set_active(self, nav: NavItem):
        for n in self._all:
            n.set_active(False)
        nav.set_active(True)

    def unlock_modes(self):
        self.nav_atalhos.set_enabled(True)
        self.nav_terminal.set_enabled(True)


# ── MAIN WINDOW ───────────────────────────────────────────────────────────────

_IDX_MENU        = 0
_IDX_SCAN        = 1
_IDX_ATALHOS     = 2
_IDX_TERMINAL    = 3
_IDX_RESTAURAR   = 4
_IDX_LOG         = 5
_IDX_ATUALIZACAO = 6
_IDX_BACKUP_GBAK = 7
_IDX_PORT_OPENER = 8
_IDX_DIAGNOSTICO = 9
_IDX_EDITAR_FUNC = 10


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Futura Setup v{APP_VERSION}")
        self.setWindowIcon(_app_icon())
        self.setMinimumSize(960, 620)
        self.resize(1100, 680)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = Sidebar()
        root.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        self._page_menu         = PageMenu()
        self._page_scan         = PageScan()
        self._page_atalhos      = PageAtalhos()
        self._page_terminal     = PageTerminal()
        self._page_restaurar    = PageRestaurar()
        self._page_log          = PageLog()
        self._page_atualizacao  = PageAtualizacao()
        self._page_backup_gbak  = PageBackupGbak()
        self._page_port_opener  = PagePortOpener()
        self._page_diagnostico  = PageDiagnostico()
        self._page_editar_func  = PageEditarFuncionario()

        for p in [
            self._page_menu,         # 0
            self._page_scan,         # 1
            self._page_atalhos,      # 2
            self._page_terminal,     # 3
            self._page_restaurar,    # 4
            self._page_log,          # 5
            self._page_atualizacao,  # 6
            self._page_backup_gbak,  # 7
            self._page_port_opener,  # 8
            self._page_diagnostico,  # 9
            self._page_editar_func,  # 10
        ]:
            self._stack.addWidget(p)

        # ── Sinais do menu ──
        self._page_menu.go_atalhos.connect(self._start_atalhos)
        self._page_menu.go_terminal.connect(self._start_terminal)
        self._page_menu.go_atualizacao.connect(self._go_atualizacao)
        self._page_menu.go_restaurar.connect(self._go_restaurar)
        self._page_menu.go_log.connect(self._go_log)
        self._page_menu.go_diagnostico.connect(self._go_diagnostico)

        # ── Sinais do scan ──
        self._page_scan.servidor_selecionado.connect(self._on_servidor)
        self._page_scan.cancelado.connect(self._go_menu)

        # ── Sinais de retorno ──
        self._page_atalhos.go_menu.connect(self._go_menu)
        self._page_terminal.go_menu.connect(self._go_menu)
        self._page_restaurar.go_menu.connect(self._go_menu)
        self._page_log.go_menu.connect(self._go_menu)
        self._page_atualizacao.go_menu.connect(self._go_menu)
        self._page_backup_gbak.go_menu.connect(self._go_menu)
        self._page_port_opener.go_menu.connect(self._go_menu)
        self._page_diagnostico.go_menu.connect(self._go_menu)
        self._page_editar_func.go_menu.connect(self._go_menu)

        # ── Sidebar clicks ──
        self._sidebar.nav_menu.on_click(lambda: self._navigate(self._go_menu))
        self._sidebar.nav_log.on_click(lambda: self._navigate(self._go_log))
        self._sidebar.nav_atualizacao.on_click(lambda: self._navigate(self._go_atualizacao))
        self._sidebar.nav_backup_gbak.on_click(lambda: self._navigate(self._go_backup_gbak))
        self._sidebar.nav_port_opener.on_click(lambda: self._navigate(self._go_port_opener))
        self._sidebar.nav_diagnostico.on_click(lambda: self._navigate(self._go_diagnostico))
        self._sidebar.nav_editar_func.on_click(lambda: self._navigate(self._go_editar_func))
        self._sidebar.nav_atalhos.on_click(
            lambda: self._navigate(
                lambda: self._show(_IDX_ATALHOS, self._sidebar.nav_atalhos)
            )
        )
        self._sidebar.nav_terminal.on_click(
            lambda: self._navigate(
                lambda: self._show(_IDX_TERMINAL, self._sidebar.nav_terminal)
            )
        )

        theme_manager.theme_changed.connect(
            lambda _: self._stack.setStyleSheet(f"background: {COLORS['bg']};")
        )

        self._flow_mode   = None
        self._close_guard = False

        self._busy_timer = QTimer(self)
        self._busy_timer.setInterval(200)
        self._busy_timer.timeout.connect(self._spin_tick)
        self._busy_timer.start()

        self._page_nav_map: dict = {}

        self._go_menu()

        log.section(
            f"FUTURA SETUP v{APP_VERSION} INICIADO — "
            f"Windows {platform.version()} — "
            f"Python {sys.version.split()[0]} — "
            f"Admin: {IS_ADMIN}"
        )

    # ── CLOSE EVENT ───────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self._close_guard:
            event.accept()
            return
        if self._get_active_workers():
            event.ignore()
            def _confirmar():
                self._close_guard = True
                self._stop_workers()
                self.close()
            self._show_guard(_confirmar)
        else:
            event.accept()

    # ── WORKERS ───────────────────────────────────────────────────────────────

    @property
    def _worker_pages(self):
        return [
            self._page_atalhos,
            self._page_terminal,
            self._page_atualizacao,
            self._page_restaurar,
            self._page_backup_gbak,
            self._page_port_opener,
            self._page_editar_func,
        ]

    def _get_active_workers(self) -> list:
        result = []
        for page in self._worker_pages:
            worker = getattr(page, "_worker", None)
            if worker and hasattr(worker, "isRunning") and worker.isRunning():
                result.append(worker)
        return result

    def _worker_rodando(self) -> bool:
        return bool(self._get_active_workers())

    def _stop_workers(self):
        for worker in self._get_active_workers():
            if hasattr(worker, "stop"):
                worker.stop()
            worker.wait(2000)

    # ── SIDEBAR BUSY INDICATORS ───────────────────────────────────────────────

    def _get_page_nav_map(self) -> dict:
        if not self._page_nav_map:
            self._page_nav_map = {
                self._page_atalhos:     self._sidebar.nav_atalhos,
                self._page_terminal:    self._sidebar.nav_terminal,
                self._page_atualizacao: self._sidebar.nav_atualizacao,
                self._page_backup_gbak: self._sidebar.nav_backup_gbak,
                self._page_port_opener: self._sidebar.nav_port_opener,
                self._page_editar_func: self._sidebar.nav_editar_func,
            }
        return self._page_nav_map

    def _spin_tick(self):
        nav_map = self._get_page_nav_map()
        for page, nav in nav_map.items():
            worker = getattr(page, "_worker", None)
            is_running = bool(worker and hasattr(worker, "isRunning") and worker.isRunning())
            if nav._busy != is_running:
                nav.set_busy(is_running)
            elif is_running:
                nav._spin_tick()

    # ── GUARD DIALOG ──────────────────────────────────────────────────────────

    def _show_guard(self, on_confirm):
        dlg = WorkerGuardDialog(self)
        dlg.move(
            self.x() + (self.width()  - dlg.width())  // 2,
            self.y() + (self.height() - dlg.height()) // 2,
        )
        dlg.confirmed.connect(on_confirm)
        dlg.show()

    def _navigate(self, fn):
        if self._worker_rodando():
            self._show_guard(fn)
        else:
            fn()

    # ── NAVEGAÇÃO ─────────────────────────────────────────────────────────────

    def _go_menu(self):
        self._show(_IDX_MENU, self._sidebar.nav_menu)

    def _go_log(self):
        self._page_log.load_log()
        self._show(_IDX_LOG, self._sidebar.nav_log)

    def _go_restaurar(self):
        self._page_restaurar.load_backups()
        self._show(_IDX_RESTAURAR, self._sidebar.nav_menu)

    def _go_atualizacao(self):
        self._page_atualizacao.reset()
        self._show(_IDX_ATUALIZACAO, self._sidebar.nav_atualizacao)

    def _go_backup_gbak(self):
        self._page_backup_gbak.reset()
        self._show(_IDX_BACKUP_GBAK, self._sidebar.nav_backup_gbak)

    def _go_port_opener(self):
        self._page_port_opener.reset()
        self._show(_IDX_PORT_OPENER, self._sidebar.nav_port_opener)

    def _go_diagnostico(self):
        self._page_diagnostico.reset()
        self._show(_IDX_DIAGNOSTICO, self._sidebar.nav_diagnostico)

    def _go_editar_func(self):
        self._page_editar_func.reset()
        self._show(_IDX_EDITAR_FUNC, self._sidebar.nav_editar_func)

    def _start_atalhos(self):
        self._flow_mode = "atalhos"
        self._page_scan.reset()
        self._show(_IDX_SCAN, self._sidebar.nav_menu)

    def _start_terminal(self):
        self._flow_mode = "terminal"
        self._page_scan.reset()
        self._show(_IDX_SCAN, self._sidebar.nav_menu)

    def _on_servidor(self, servidor):
        log.prefs.add_servidor(servidor.ip, servidor.hostname, servidor.path)
        self._sidebar.unlock_modes()
        if self._flow_mode == "atalhos":
            self._page_atalhos.set_servidor(servidor)
            self._show(_IDX_ATALHOS, self._sidebar.nav_atalhos)
        else:
            self._page_terminal.set_servidor(servidor)
            self._show(_IDX_TERMINAL, self._sidebar.nav_terminal)

    def _show(self, idx: int, nav: NavItem):
        self._stack.setCurrentIndex(idx)
        self._sidebar.set_active(nav)


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)

    icon = _app_icon()
    app.setWindowIcon(icon)
    app.setApplicationName("Futura Setup")
    app.setOrganizationName("Futura Sistemas")

    saved_mode = log.prefs.theme
    app.setStyleSheet(get_stylesheet(saved_mode))
    set_theme(saved_mode)

    theme_manager.theme_changed.connect(
        lambda mode: app.setStyleSheet(get_stylesheet(mode))
    )

    login = LoginDialog()
    login.setWindowIcon(icon)
    login.exec()
    if not login.autenticado():
        sys.exit(0)

    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()

    _force_taskbar_icon(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()