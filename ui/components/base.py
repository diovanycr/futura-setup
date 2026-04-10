# =============================================================================
# FUTURA SETUP — UI Components: Base & Utils
# =============================================================================

from PyQt6.QtWidgets import QWidget, QLabel, QFrame
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont

from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager

def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def card_style(state: str, selected: bool) -> tuple[str, str]:
    if selected:
        return COLORS["accent_dim"], COLORS["accent"]
    elif state == "hover":
        return COLORS["panel_hover"], COLORS["border_light"]
    return COLORS["surface"], COLORS["border"]

def label(text: str, color: str = None, size: int = 13,
          bold: bool = False, mono: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont(FONT_MONO if mono else FONT_SANS, size,
                      QFont.Weight.Bold if bold else QFont.Weight.Normal))
    lbl.setStyleSheet(f"color: {color or COLORS['text']}; background: transparent; border: none;")
    return lbl

class HLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(1)
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(f"background: {COLORS['border']}; border: none;")

def h_line() -> "HLine":
    return HLine()

def spacer(w: int = 0, h: int = 0) -> QWidget:
    sp = QWidget()
    sp.setFixedSize(max(w, 1), max(h, 1))
    sp.setStyleSheet("background: transparent;")
    return sp
