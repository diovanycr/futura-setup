# =============================================================================
# FUTURA SETUP — UI Components: Cards & Selection
# =============================================================================

from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QRadioButton, QLineEdit
from PyQt6.QtCore import Qt, pyqtSignal, pyqtProperty, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPainter, QColor

from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.components.base import card_style, label
from ui.components.buttons import make_folder_btn

class ServerItem(QWidget):
    selected = pyqtSignal(object)

    def __init__(self, hostname: str, ip: str, path: str, version: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("ServerItem")
        self.hostname, self.ip, self.path, self.version = hostname, ip, path, version
        self._selected, self._state, self._offset_y = False, "normal", 0
        self.setFixedHeight(64); self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._lift_anim = QPropertyAnimation(self, b"offset_y")
        self._lift_anim.setDuration(150); self._lift_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        lay = QHBoxLayout(self); lay.setContentsMargins(16, 0, 16, 0); lay.setSpacing(16)
        
        # Indicador lateral (ponto)
        self._dot_container = QWidget()
        self._dot_container.setFixedWidth(12)
        dot_lay = QVBoxLayout(self._dot_container); dot_lay.setContentsMargins(0, 0, 0, 0)
        self._dot = QWidget(); self._dot.setFixedSize(8, 8)
        dot_lay.addStretch(); dot_lay.addWidget(self._dot); dot_lay.addStretch()
        
        # Bloco de Informações
        info_lay = QVBoxLayout(); info_lay.setSpacing(1); info_lay.setContentsMargins(0, 0, 0, 0)
        self._name_lbl = QLabel(hostname)
        self._name_lbl.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        
        self._path_lbl = QLabel(path)
        self._path_lbl.setFont(QFont(FONT_MONO, 9))
        
        self._ver_lbl = QLabel(f"v{version}" if version else "")
        self._ver_lbl.setFont(QFont(FONT_MONO, 8))
        self._ver_lbl.setFixedWidth(50)
        
        info_lay.addStretch()
        info_lay.addWidget(self._name_lbl)
        info_lay.addWidget(self._path_lbl)
        info_lay.addStretch()
        
        # Badge de IP
        self._ip_badge = QLabel(ip)
        self._ip_badge.setFont(QFont(FONT_MONO, 10, QFont.Weight.Bold))
        self._ip_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ip_badge.setContentsMargins(10, 4, 10, 4)
        self._ip_badge.setFixedHeight(24)
        self._ip_badge.setMinimumWidth(100)

        lay.addWidget(self._dot_container)
        lay.addLayout(info_lay, 1)
        if version: lay.addWidget(self._ver_lbl)
        lay.addWidget(self._ip_badge)
        
        self._upd(); theme_manager.theme_changed.connect(self._upd)

    @pyqtProperty(int)
    def offset_y(self): return self._offset_y
    @offset_y.setter
    def offset_y(self, v): self._offset_y = v; self.update()

    def set_selected(self, v: bool):
        self._selected = v
        self._upd()

    def enterEvent(self, e):
        self._state = "hover"
        self._upd()
        self._lift_anim.stop()
        self._lift_anim.setEndValue(-2)
        self._lift_anim.start()

    def leaveEvent(self, e):
        self._state = "normal"
        self._upd()
        self._lift_anim.stop()
        self._lift_anim.setEndValue(0)
        self._lift_anim.start()

    def _upd(self, _mode: str = ""):
        bg, border = card_style(self._state, self._selected)
        accent = COLORS["accent"] if self._selected else COLORS["border"]
        dot_c = COLORS["accent"] if self._selected else COLORS["text_dim"]
        ip_bg = COLORS["accent"] if self._selected else COLORS["surface2"]
        ip_txt = "#ffffff" if self._selected else COLORS["text_mid"]
        
        self.setStyleSheet(f"""
            #ServerItem {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 10px;
            }}
            QLabel {{ background: transparent; border: none; }}
            #ServerItem QLabel {{ color: {COLORS['text']}; }}
            #ServerItem QLabel[path="true"] {{ color: {COLORS['text_dim']}; }}
        """)
        
        # Estilo manual para labels específicos
        self._name_lbl.setStyleSheet(f"color: {COLORS['text']};")
        self._path_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        self._ver_lbl.setStyleSheet(f"color: {COLORS['accent2']};")
        self._dot.setStyleSheet(f"background: {dot_c}; border-radius: 4px;")
        self._ip_badge.setStyleSheet(f"""
            background: {ip_bg};
            color: {ip_txt};
            border-radius: 12px;
            border: 1px solid {COLORS['border'] if not self._selected else 'transparent'};
        """)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.selected.emit(self)

    def paintEvent(self, event):
        p = QPainter(self)
        if self._offset_y != 0: p.translate(0, self._offset_y)
        super().paintEvent(event)

class RadioRow(QWidget):
    def __init__(self, text: str, desc: str, checked: bool = False, parent=None):
        super().__init__(parent)
        self._state, self._offset_y = "normal", 0
        self.setFixedHeight(60); self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lift_anim = QPropertyAnimation(self, b"offset_y")
        self._lift_anim.setDuration(150)
        lay = QHBoxLayout(self); txt_lay = QVBoxLayout()
        self._name_lbl = QLabel(text); self._name_lbl.setFont(QFont(FONT_MONO, 12, QFont.Weight.Bold))
        self._desc_lbl = QLabel(desc); txt_lay.addStretch(); txt_lay.addWidget(self._name_lbl); txt_lay.addWidget(self._desc_lbl); txt_lay.addStretch()
        self._radio = QRadioButton(); self._radio.setChecked(checked)
        lay.addLayout(txt_lay, 1); lay.addWidget(self._radio)
        self._upd(); theme_manager.theme_changed.connect(self._upd)

    def radio(self): return self._radio

    def enterEvent(self, e):
        self._state = "hover"
        self._upd()
        self._lift_anim.stop()
        self._lift_anim.setEndValue(-2)
        self._lift_anim.start()

    def leaveEvent(self, e):
        self._state = "normal"
        self._upd()
        self._lift_anim.stop()
        self._lift_anim.setEndValue(0)
        self._lift_anim.start()

    @pyqtProperty(int)
    def offset_y(self): return self._offset_y
    @offset_y.setter
    def offset_y(self, v): self._offset_y = v; self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        if self._offset_y != 0: p.translate(0, self._offset_y)
        super().paintEvent(event)


    def _upd(self, _mode=None):
        bg, border = card_style(self._state, self._radio.isChecked())
        self.setStyleSheet(f"""
            RadioRow {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 8px;
            }}
            QLabel {{ background: transparent; border: none; color: {COLORS['text']}; }}
        """)

class MiniFileItem(QWidget):
    toggled = pyqtSignal(bool)
    
    def __init__(self, name: str, size_str: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("MiniFileItem")
        self.name, self._checked, self._state, self._offset_y = name, False, "normal", 0
        self.setFixedHeight(38); self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._lift_anim = QPropertyAnimation(self, b"offset_y")
        self._lift_anim.setDuration(150)
        
        lay = QHBoxLayout(self); lay.setContentsMargins(10, 0, 10, 0); lay.setSpacing(10)
        
        self._check = QWidget(); self._check.setFixedSize(16, 16)
        
        self._name_lbl = QLabel(name)
        self._name_lbl.setFont(QFont(FONT_MONO, 10))
        
        self._size_lbl = QLabel(size_str)
        self._size_lbl.setFont(QFont(FONT_MONO, 8))
        self._size_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        
        lay.addWidget(self._check)
        lay.addWidget(self._name_lbl, 1)
        lay.addWidget(self._size_lbl)
        
        self._upd(); theme_manager.theme_changed.connect(self._upd)

    @pyqtProperty(int)
    def offset_y(self): return self._offset_y
    @offset_y.setter
    def offset_y(self, v): self._offset_y = v; self.update()

    def set_checked(self, v: bool):
        self._checked = v
        self._upd()

    def is_checked(self) -> bool:
        return self._checked

    def enterEvent(self, e):
        self._state = "hover"
        self._upd()
        self._lift_anim.stop()
        self._lift_anim.setEndValue(-1)
        self._lift_anim.start()

    def leaveEvent(self, e):
        self._state = "normal"
        self._upd()
        self._lift_anim.stop()
        self._lift_anim.setEndValue(0)
        self._lift_anim.start()

    def _upd(self, _mode: str = ""):
        bg, border = card_style(self._state, self._checked)
        chk_color = COLORS["accent"] if self._checked else COLORS["border"]
        
        self.setStyleSheet(f"""
            #MiniFileItem {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            QLabel {{ background: transparent; border: none; color: {COLORS['text']}; }}
        """)
        
        inner_check = f"background: {COLORS['accent']};" if self._checked else ""
        self._check.setStyleSheet(f"""
            border: 1.5px solid {chk_color};
            border-radius: 4px;
            {inner_check}
        """)

    def mousePressEvent(self, e):
        self._checked = not self._checked; self._upd(); self.toggled.emit(self._checked)

    def paintEvent(self, event):
        p = QPainter(self)
        if self._offset_y != 0: p.translate(0, self._offset_y)
        super().paintEvent(event)

class DestPanel(QWidget):
    changed = pyqtSignal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected = 1; self.setFixedHeight(42)
        lay = QHBoxLayout(self)
        for rid, text in [(1, "Desktop"), (2, "Menu"), (0, "Ambos")]:
            btn = QRadioButton(text)
            if rid == 1: btn.setChecked(True)
            btn.toggled.connect(lambda v, r=rid: self._on_toggled(v, r))
            lay.addWidget(btn)
        self.setStyleSheet(f"background: {COLORS['surface']}; border: 1px solid {COLORS['border']}; border-radius: 6px;")

    def _on_toggled(self, checked, rid):
        if checked:
            self._selected = rid
            self.changed.emit(rid)

    def selected_id(self):
        return self._selected


class ProcessCard(QWidget):
    def __init__(self, pid: str, name: str, exe: str = "", parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self._state = "normal"
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 16, 0)
        
        icon = QLabel("⚙")
        icon.setFont(QFont(FONT_SANS, 14))
        icon.setFixedWidth(24)
        
        info = QVBoxLayout()
        self._name_lbl = QLabel(name)
        self._name_lbl.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
        self._pid_lbl = QLabel(f"PID: {pid}  |  {exe}")
        self._pid_lbl.setFont(QFont(FONT_MONO, 9))
        info.addStretch(); info.addWidget(self._name_lbl); info.addWidget(self._pid_lbl); info.addStretch()
        
        lay.addWidget(icon)
        lay.addLayout(info, 1)
        
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        bg, border = card_style(self._state, False)
        self.setStyleSheet(f"background: {bg}; border: 1px solid {border}; border-radius: 6px;")
        self._name_lbl.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        self._pid_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")

class CustomPathCard(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self._state = "normal"
        
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(10)
        
        self._rb = QRadioButton()
        self._title_lbl = QLabel(title)
        self._title_lbl.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
        
        self._input = QLineEdit()
        self._input.setPlaceholderText("Selecione uma pasta...")
        self._input.setReadOnly(True)
        self._input.setStyleSheet(f"background: {COLORS['surface']}; border: 1px solid {COLORS['border']}; padding: 4px;")
        
        self._btn = make_folder_btn()
        
        lay.addWidget(self._rb)
        lay.addWidget(self._title_lbl)
        lay.addWidget(self._input, 1)
        lay.addWidget(self._btn)
        
        self._upd()
        theme_manager.theme_changed.connect(self._upd)
        self._rb.toggled.connect(self._upd)

    def radio(self): return self._rb
    def btn_folder(self): return self._btn
    def input_field(self): return self._input
    def path(self): return self._input.text()
    def set_path(self, p): self._input.setText(p)

    def _upd(self, _mode: str = ""):
        bg, border = card_style(self._state, self._rb.isChecked())
        self.setStyleSheet(f"""
            CustomPathCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            QLabel {{ background: transparent; border: none; color: {COLORS['text']}; }}
        """)

class PathSelectorCard(QWidget):
    """Card reutilizável para seleção de arquivos ou diretórios com estética v5.0."""
    def __init__(self, label_text: str, placeholder: str = "", is_dir: bool = True, parent=None):
        super().__init__(parent)
        self.is_dir = is_dir
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        
        self.lbl = label(label_text, COLORS["text"], 9, bold=True)
        lay.addWidget(self.lbl)
        
        row = QHBoxLayout()
        row.setSpacing(8)
        
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setFixedHeight(34)
        
        self.btn = make_folder_btn(self)
        self.btn.clicked.connect(self._browse)
        
        row.addWidget(self.edit, 1)
        row.addWidget(self.btn)
        lay.addLayout(row)
        
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode=""):
        self.edit.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
            }}
            QLineEdit:focus {{ border-color: {COLORS['accent']}; }}
        """)

    def _browse(self):
        from PyQt6.QtWidgets import QFileDialog
        curr = self.edit.text() or "C:\\"
        if self.is_dir:
            p = QFileDialog.getExistingDirectory(self, "Selecionar Pasta", curr)
        else:
            p, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo", curr, "Todos (*.*)")
        if p: self.edit.setText(p.replace("/", "\\"))

    @property
    def value(self) -> str: return self.edit.text().strip()
    @value.setter
    def value(self, v: str): self.edit.setText(v)
