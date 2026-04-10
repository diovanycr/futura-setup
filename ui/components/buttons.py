# =============================================================================
# FUTURA SETUP — UI Components: Buttons
# =============================================================================

from PyQt6.QtWidgets import QPushButton, QHBoxLayout, QWidget, QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import COLORS, FONT_SANS
from ui.theme_manager import theme_manager

def _apply_btn_base(btn: QPushButton, min_width: int):
    btn.setMinimumWidth(min_width)
    btn.setMinimumHeight(40)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)

def _apply_primary_style(btn: QPushButton, font_size: int = 11, padding: str = "4px 12px"):
    text_color = "#ffffff" if theme_manager.mode == "light" else "#001826"
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {COLORS["accent"]};
            color: {text_color};
            border: none;
            border-radius: 8px;
            padding: {padding};
            font-weight: 700;
            font-size: {font_size}px;
        }}
        QPushButton:hover {{ background-color: {COLORS["accent_hover"]}; }}
        QPushButton:pressed {{ background-color: {COLORS["accent_press"]}; }}
        QPushButton:disabled {{
            background-color: {COLORS['panel_hover']};
            color: {COLORS['text_disabled']};
        }}
    """)

def _apply_secondary_style(btn: QPushButton, font_size: int = 11, padding: str = "4px 12px"):
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: transparent;
            color: {COLORS["text"]};
            border: 1.5px solid {COLORS["btn_border"]};
            border-radius: 8px;
            padding: {padding};
            font-size: {font_size}px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {COLORS["panel_hover"]};
            border-color: {COLORS["text_dim"]};
        }}
        QPushButton:pressed {{ background-color: {COLORS["panel_press"]}; }}
    """)

def _apply_danger_style(btn: QPushButton, font_size: int = 11, padding: str = "4px 12px"):
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {COLORS["danger"]};
            color: #ffffff;
            border: none;
            border-radius: 8px;
            padding: {padding};
            font-weight: 700;
            font-size: {font_size}px;
        }}
        QPushButton:hover {{ background-color: {COLORS["danger"]}; opacity: 0.9; }}
        QPushButton:pressed {{ background-color: {COLORS["danger"]}; opacity: 0.8; }}
        QPushButton:disabled {{
            background-color: {COLORS['panel_hover']};
            color: {COLORS['text_disabled']};
        }}
    """)

def make_primary_btn(text: str, min_width: int = 140, font_size: int = 11, padding: str = "4px 12px") -> QPushButton:
    btn = QPushButton(text)
    _apply_btn_base(btn, min_width)
    btn.setFont(QFont(FONT_SANS, font_size, QFont.Weight.Bold))
    _apply_primary_style(btn, font_size, padding)
    theme_manager.theme_changed.connect(lambda _: _apply_primary_style(btn, font_size, padding))
    return btn

def make_secondary_btn(text: str, min_width: int = 100, font_size: int = 11, padding: str = "4px 12px") -> QPushButton:
    btn = QPushButton(text)
    _apply_btn_base(btn, min_width)
    btn.setFont(QFont(FONT_SANS, font_size))
    _apply_secondary_style(btn, font_size, padding)
    theme_manager.theme_changed.connect(lambda _: _apply_secondary_style(btn, font_size, padding))
    return btn

def make_danger_btn(text: str, min_width: int = 140, font_size: int = 11, padding: str = "4px 12px") -> QPushButton:
    btn = QPushButton(text)
    _apply_btn_base(btn, min_width)
    btn.setFont(QFont(FONT_SANS, font_size, QFont.Weight.Bold))
    _apply_danger_style(btn, font_size, padding)
    theme_manager.theme_changed.connect(lambda _: _apply_danger_style(btn, font_size, padding))
    return btn

def make_folder_btn(parent: QWidget = None) -> QPushButton:
    btn = make_secondary_btn("", 40)
    btn.setIcon(QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_DirOpenIcon))
    btn.setMaximumWidth(40)
    btn.setMinimumHeight(28)
    btn.setToolTip("Selecionar pasta")
    return btn

def btn_row(*btns, centered: bool = True) -> QWidget:
    row = QHBoxLayout()
    row.setSpacing(12)
    if centered: row.addStretch()
    for btn in btns:
        row.addWidget(btn)
    row.addStretch()
    w = QWidget()
    w.setContentsMargins(0, 0, 0, 0)
    w.setLayout(row)
    w.setStyleSheet("background: transparent;")
    return w
