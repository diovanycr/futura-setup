# =============================================================================
# FUTURA SETUP — UI Components: Sidebar
# =============================================================================

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, pyqtSignal
from PyQt6.QtGui import QFont

from ui.theme import COLORS, FONT_SANS, FONT_MONO, set_theme, get_stylesheet
from ui.theme_manager import theme_manager
from ui.widgets import spacer
from config import APP_VERSION
from core.service_manager import is_admin

IS_ADMIN = is_admin()

# -- NAV ITEM ------------------------------------------------------------------

class NavItem(QWidget):
    def __init__(self, text: str, icon: str = "", parent=None):
        super().__init__(parent)
        self._active   = False
        self._enabled  = True
        self._busy     = False
        self._callback = None
        self._spin_frame = 0
        self._spin_frames = ["\\", "|", "/", "-"]
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


# -- NAV SECTION LABEL ---------------------------------------------------------

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


# -- THEME TOGGLE --------------------------------------------------------------

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
        self._icon.setText("*" if is_dark else "O")
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


class StyleToggleBtn(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(10)

        self._icon = QLabel()
        self._icon.setFont(QFont(FONT_SANS, 11))
        self._icon.setFixedWidth(18)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._lbl = QLabel()
        self._lbl.setFont(QFont(FONT_SANS, 11))

        lay.addWidget(self._icon)
        lay.addWidget(self._lbl, 1)

        self._upd()
        theme_manager.ui_theme_changed.connect(self._upd)

    def _upd(self, _theme: str = ""):
        is_modern = theme_manager.ui_theme == "modern"
        self._icon.setText("📜" if is_modern else "💎")
        self._lbl.setText("Tema Classico" if is_modern else "Tema Moderno")
        self._lbl.setStyleSheet(f"color: {COLORS['text_mid']}; background: transparent;")
        self.setStyleSheet("background: transparent; border-radius: 4px;")

    def enterEvent(self, e):
        self.setStyleSheet(f"background: {COLORS['panel_hover']}; border-radius: 4px;")

    def leaveEvent(self, e):
        self.setStyleSheet("background: transparent; border-radius: 4px;")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            # Emite sinal para o app mudar o stylesheet global
            new_theme = "classic" if theme_manager.ui_theme == "modern" else "modern"
            theme_manager.set_ui_theme(new_theme)


# -- FOOTER WIDGET -------------------------------------------------------------

class FooterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(3)

        dot_color  = COLORS["accent2"] if IS_ADMIN else COLORS["warn"]
        status_txt = "Administrador" if IS_ADMIN else "Usuario padrao"

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

        self._dev_lbl = QLabel("dev by Diovany C. Rodrigues")
        self._dev_lbl.setFont(QFont(FONT_SANS, 9))
        self._dev_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        lay.addWidget(row_w)
        lay.addWidget(self._ver_lbl)
        lay.addWidget(self._dev_lbl)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        dot_color = COLORS["accent2"] if IS_ADMIN else COLORS["warn"]
        self._admin_dot.setStyleSheet(f"background: {dot_color}; border-radius: 4px;")
        self._admin_st.setStyleSheet(f"color: {COLORS['text_mid']}; background: transparent;")
        self._ver_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
        self._dev_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")


# -- SIDEBAR -------------------------------------------------------------------

class Sidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setObjectName("Sidebar")

        self._active_bar = QWidget(self)
        self._active_bar.setFixedWidth(4)
        self._active_bar.setFixedHeight(24)
        self._active_bar.setObjectName("active_bar")
        self._active_bar.hide()

        self._active_anim = QPropertyAnimation(self._active_bar, b"pos")
        self._active_anim.setDuration(300)
        self._active_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._inner = QWidget()
        inner_lay = QVBoxLayout(self._inner)
        inner_lay.setContentsMargins(8, 0, 8, 12)
        inner_lay.setSpacing(1)

        # -- Header --
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        header_lay = QVBoxLayout(header)
        header_lay.setContentsMargins(12, 20, 12, 16)

        self._logo = QLabel("Futura Setup")
        self._logo.setFont(QFont(FONT_SANS, 15, QFont.Weight.Bold))

        self._logo_sub = QLabel("Configuracao de Terminal")
        self._logo_sub.setFont(QFont(FONT_SANS, 11))

        header_lay.addWidget(self._logo)
        header_lay.addWidget(self._logo_sub)
        inner_lay.addWidget(header)

        self._div_top = self._make_divider()
        inner_lay.addWidget(self._div_top)
        inner_lay.addWidget(spacer(h=4))

        # -- Navegação principal --
        self.nav_menu        = NavItem("Menu Principal",   ">")
        self.nav_utilitarios = NavItem("Utilitarios",      "#")
        inner_lay.addWidget(self.nav_menu)
        inner_lay.addWidget(self.nav_utilitarios)

        # -- Seção Operações --
        inner_lay.addWidget(NavSectionLabel("Operacoes"))
        self.nav_atalhos     = NavItem("Puxar via Rede",    "^")
        self.nav_terminal    = NavItem("Novo Terminal",     "+")
        self.nav_atualizacao = NavItem("Atualizar Sistema", "!")
        inner_lay.addWidget(self.nav_atalhos)
        inner_lay.addWidget(self.nav_terminal)
        inner_lay.addWidget(self.nav_atualizacao)

        self.nav_atalhos.set_enabled(False)
        self.nav_terminal.set_enabled(False)

        inner_lay.addStretch()

        # -- Rodapé --
        self._div_bot = self._make_divider()
        inner_lay.addWidget(self._div_bot)
        inner_lay.addWidget(spacer(h=4))
        inner_lay.addWidget(ThemeToggleBtn())
        inner_lay.addWidget(StyleToggleBtn())
        inner_lay.addWidget(spacer(h=4))
        inner_lay.addWidget(FooterWidget())

        self._border = QFrame()
        self._border.setFixedWidth(1)

        root.addWidget(self._inner, 1)
        root.addWidget(self._border)

        self._all = [
            self.nav_menu, self.nav_utilitarios,
            self.nav_atalhos, self.nav_terminal, self.nav_atualizacao,
        ]

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _make_divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        return line

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(f"""
            QWidget#Sidebar {{ background: {COLORS['surface2']}; }}
            QWidget#active_bar {{ background: {COLORS['accent']}; border-radius: 2px; }}
        """)
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

        if not self._active_bar.isVisible():
            self._active_bar.show()
            self._active_bar.move(0, nav.y() + 6)
        else:
            self._active_anim.stop()
            self._active_anim.setEndValue(nav.pos() + QPoint(0, 6))
            self._active_anim.start()

    def unlock_modes(self):
        self.nav_atalhos.set_enabled(True)
        self.nav_terminal.set_enabled(True)
