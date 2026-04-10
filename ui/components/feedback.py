# =============================================================================
# FUTURA SETUP — UI Components: Feedback, Headers & Indicators
# =============================================================================

from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QProgressBar, QSizePolicy, QGridLayout
from PyQt6.QtCore import Qt, pyqtSignal, pyqtProperty, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPainter, QColor, QPen

from ui.theme import COLORS, FONT_SANS
from ui.theme_manager import theme_manager
from ui.components.base import spacer
from ui.components.buttons import make_secondary_btn

class SectionHeader(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 8)
        self._lbl = QLabel(text)
        self._lbl.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
        lay.addWidget(self._lbl)
        lay.addStretch()
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        self._lbl.setStyleSheet(f"color: {COLORS['text']}; background: transparent; border: none;")

class PageHeader(QWidget):
    back_clicked = pyqtSignal()

    def __init__(self, title: str, subtitle: str = "", back_visible: bool = True, parent=None):
        super().__init__(parent)
        self.setObjectName("page_header")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(20)

        title_block = QWidget()
        tb_lay = QVBoxLayout(title_block)
        tb_lay.setContentsMargins(0, 0, 0, 0)
        tb_lay.setSpacing(2)

        self._lbl_title = QLabel(title.upper())
        self._lbl_title.setFont(QFont(FONT_SANS, 15, QFont.Weight.Bold))
        self._lbl_sub = QLabel(subtitle)
        self._lbl_sub.setFont(QFont(FONT_SANS, 10))
        self._lbl_sub.setWordWrap(True)

        tb_lay.addWidget(self._lbl_title)
        tb_lay.addWidget(self._lbl_sub)
        lay.addWidget(title_block, 1)

        self._btn_back = make_secondary_btn("VOLTAR", 80)
        self._btn_back.clicked.connect(self.back_clicked.emit)
        if not back_visible:
            self._btn_back.hide()
        lay.addWidget(self._btn_back, 0, Qt.AlignmentFlag.AlignVCenter)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def set_title(self, text: str):
        self._lbl_title.setText(text.upper())

    def set_subtitle(self, text: str):
        self._lbl_sub.setText(text)

    def _upd(self, _mode: str = ""):
        bg = COLORS.get("surface", "#ffffff")
        border = COLORS.get("border", "#dddddd")
        self.setStyleSheet(f"QWidget#page_header {{ background: {bg}; border-bottom: 1.5px solid {border}; }} QLabel {{ background: transparent; border: none; }}")
        self._lbl_title.setStyleSheet(f"color: {COLORS['text']};")
        self._lbl_sub.setStyleSheet(f"color: {COLORS['text_dim']};")

class AlertBox(QWidget):
    _KINDS = {
        "info":    ("accent",  "ℹ"),
        "warn":    ("warn",    "⚠"),
        "danger":  ("danger",  "✕"),
        "success": ("accent2", "✓"),
    }

    def __init__(self, text: str, kind: str = "info", parent=None):
        super().__init__(parent)
        self._kind = kind
        self.setObjectName("AlertBox")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        color_key, icon_ch = self._KINDS.get(kind, self._KINDS["info"])
        self._icon_w = QLabel(icon_ch)
        self._icon_w.setFixedSize(20, 20)
        self._icon_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_w.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))

        self._msg = QLabel(text)
        self._msg.setFont(QFont(FONT_SANS, 12))
        self._msg.setWordWrap(True)

        lay.addWidget(self._icon_w)
        lay.addWidget(self._msg, 1)
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def set_text(self, text: str):
        self._msg.setText(text)

    def set_kind(self, kind: str):
        if kind in self._KINDS:
            self._kind = kind
            _, icon_ch = self._KINDS[kind]
            self._icon_w.setText(icon_ch)
            self._upd()

    def _upd(self, _mode: str = ""):
        color_key, _ = self._KINDS.get(self._kind, self._KINDS["info"])
        color = COLORS[color_key]
        dim = COLORS.get(f"{color_key}_dim", COLORS["accent_dim"])
        self.setStyleSheet(f"QWidget#AlertBox {{ background: {dim}; border-left: 3px solid {color}; border-radius: 4px; }} "
                           f"QLabel {{ color: {color}; background: transparent; border: none; }}")

class ProgressBlock(QWidget):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("ProgressBlock")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        header = QHBoxLayout()
        self.name_lbl = QLabel(title)
        self.pct_lbl = QLabel("0%")
        self.pct_lbl.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
        header.addWidget(self.name_lbl, 1)
        header.addWidget(self.pct_lbl)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setFixedHeight(3)
        self.bar.setTextVisible(False)

        self.sub_lbl = QLabel("Aguardando...")
        self.sub_lbl.setFont(QFont(FONT_SANS, 11))

        lay.addLayout(header)
        lay.addWidget(self.bar)
        lay.addWidget(self.sub_lbl)
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def update(self, value: int, name: str = None, sub: str = None):
        self.bar.setValue(value)
        self.pct_lbl.setText(f"{value}%")
        if name: self.name_lbl.setText(name)
        if sub: self.sub_lbl.setText(sub)

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(f"QWidget#ProgressBlock {{ background: {COLORS['surface']}; border: 1px solid {COLORS['border']}; border-radius: 4px; }} "
                           f"QLabel {{ color: {COLORS['text']}; background: transparent; border: none; }}")

class StepIndicator(QWidget):
    def __init__(self, steps: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("StepIndicator")
        self._steps, self._current = steps, 0
        self.setFixedHeight(64)
        
        main_lay = QHBoxLayout(self)
        main_lay.setContentsMargins(10, 0, 10, 0)
        main_lay.setSpacing(0)

        self._circles, self._labels, self._lines = [], [], []
        
        for i, name in enumerate(steps):
            # Step block (circle + label)
            sw = QWidget()
            sw.setStyleSheet("background: transparent;")
            sl = QVBoxLayout(sw)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(4)
            
            circle = QLabel(str(i + 1))
            circle.setFixedSize(24, 24)
            circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            circle.setFont(QFont(FONT_SANS, 9, QFont.Weight.Bold))
            self._circles.append(circle)
            
            lbl = QLabel(name.upper())
            lbl.setFont(QFont(FONT_SANS, 7, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._labels.append(lbl)
            
            sl.addStretch()
            sl.addWidget(circle, 0, Qt.AlignmentFlag.AlignHCenter)
            sl.addWidget(lbl, 0, Qt.AlignmentFlag.AlignHCenter)
            sl.addStretch()
            
            main_lay.addWidget(sw)
            
            # Line between steps
            if i < len(steps) - 1:
                line_container = QWidget()
                line_container.setFixedHeight(24) # Align with circle center
                line_lay = QVBoxLayout(line_container)
                line_lay.setContentsMargins(4, 0, 4, 0)
                
                line = QWidget()
                line.setFixedHeight(2)
                line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                self._lines.append(line)
                
                line_lay.addStretch()
                line_lay.addWidget(line)
                line_lay.addStretch()
                
                main_lay.addWidget(line_container, 1)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def set_step(self, current: int):
        self._current = current
        self._upd()

    def _upd(self, _mode: str = ""):
        for i, (circle, lbl) in enumerate(zip(self._circles, self._labels)):
            is_done = i < self._current
            is_active = i == self._current
            
            if is_done:
                circle.setStyleSheet(f"background: {COLORS['accent2']}; color: #fff; border-radius: 12px;")
                lbl.setStyleSheet(f"color: {COLORS['accent2']};")
            elif is_active:
                circle.setStyleSheet(f"background: {COLORS['accent']}; color: #fff; border-radius: 12px;")
                lbl.setStyleSheet(f"color: {COLORS['accent']};")
            else:
                circle.setStyleSheet(f"background: {COLORS['border']}; color: {COLORS['text_dim']}; border-radius: 12px;")
                lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        
        for i, line in enumerate(self._lines):
            color = COLORS['accent2'] if i < self._current else COLORS['border']
            line.setStyleSheet(f"background: {color}; border-radius: 1px;")

class LoadingSpinner(QWidget):
    def __init__(self, size: int = 40, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size); self._angle = 0
        self._anim = QPropertyAnimation(self, b"angle")
        self._anim.setDuration(1000); self._anim.setStartValue(0); self._anim.setEndValue(360)
        self._anim.setLoopCount(-1); self._anim.setEasingCurve(QEasingCurve.Type.Linear)

    @pyqtProperty(int)
    def angle(self): return self._angle
    @angle.setter
    def angle(self, v): self._angle = v; self.update()

    def start(self): self._anim.start(); self.show()
    def stop(self): self._anim.stop(); self.hide()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(4, 4, -4, -4)
        pen = QPen(QColor(COLORS["accent"])); pen.setWidth(3); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen); p.drawArc(rect, -int(self._angle * 16), 280 * 16); p.end()


class ResultBox(QWidget):
    """Container para exibir um resumo de resultados com títulos e pares chave-valor."""
    def __init__(self, title: str, rows: list[tuple[str, str]], kind: str = "success", parent=None):
        super().__init__(parent)
        self.setObjectName("ResultBox")
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        self._title_lbl = QLabel(title.upper())
        self._title_lbl.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
        lay.addWidget(self._title_lbl)

        grid_w = QWidget()
        grid_w.setStyleSheet("background: transparent; border: none;")
        self._grid = QGridLayout(grid_w)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(10)
        
        for i, (k, v) in enumerate(rows):
            kl = QLabel(k.upper() if k else "")
            kl.setFont(QFont(FONT_SANS, 10, QFont.Weight.Bold))
            vl = QLabel(v)
            vl.setFont(QFont(FONT_SANS, 10))
            vl.setWordWrap(True)
            self._grid.addWidget(kl, i, 0)
            self._grid.addWidget(vl, i, 1)
        
        lay.addWidget(grid_w)
        
        self._kind = kind
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        color_key = "accent2" if self._kind == "success" else "warn" if self._kind == "warn" else "danger"
        color = COLORS.get(color_key, COLORS["accent"])
        dim   = COLORS.get(f"{color_key}_dim", COLORS["accent_dim"])
        
        self.setStyleSheet(f"""
            QWidget#ResultBox {{ 
                background: {dim}; 
                border: 1px solid {color}; 
                border-left: 5px solid {color};
                border-radius: 6px; 
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
        self._title_lbl.setStyleSheet(f"color: {color};")
        for i in range(self._grid.count()):
            w = self._grid.itemAt(i).widget()
            if isinstance(w, QLabel):
                w.setStyleSheet(f"color: {COLORS['text' if i%2 != 0 else 'text_dim']};")
