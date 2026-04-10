# =============================================================================
# FUTURA SETUP — UI Components: Containers
# =============================================================================

import html
from PyQt6.QtWidgets import QWidget, QTextEdit, QStackedWidget, QSizePolicy, QVBoxLayout
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QTimer, pyqtProperty
from PyQt6.QtGui import QFont, QPainter, QColor, QBrush, QPen

from ui.theme import COLORS, FONT_MONO, FONT_SANS
from ui.theme_manager import theme_manager
from ui.components.base import hex_to_rgb

class LogConsole(QTextEdit):
    def __init__(self, max_height: int = 0, max_lines: int = 500, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont(FONT_MONO, 11))
        self.document().setMaximumBlockCount(max_lines)
        if max_height > 0:
            self.setMaximumHeight(max_height)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        else:
            self.setMinimumHeight(120)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._upd_bg()
        theme_manager.theme_changed.connect(self._upd_bg)

    def _upd_bg(self, _mode: str = ""):
        bg = "#FAFAFA" if theme_manager.mode == "light" else "#111111"
        self.setStyleSheet(f"background: {bg}; border: 1px solid {COLORS['border']}; color: {COLORS['text_mid']}; "
                           f"font-family: Consolas; font-size: 11px; padding: 10px 14px; border-radius: 4px;")

    def append_line(self, text: str, kind: str = "dim"):
        color = COLORS.get(f"log_{kind}", COLORS.get("text_dim"))
        safe = html.escape(text)
        self.append(f'<span style="color:{color};">{safe}</span>')
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def clear_console(self):
        self.clear()

class FadeStackedWidget(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._offset_y = 0
        self._anim_group = QPropertyAnimation(self, b"offset_y")
        self._anim_group.setDuration(350)
        self._anim_group.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self._opacity_anim.setDuration(300)
        self._opacity_anim.setStartValue(0.0)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @pyqtProperty(int)
    def offset_y(self): return self._offset_y
    @offset_y.setter
    def offset_y(self, v): self._offset_y = v; self.update()

    def setCurrentIndex(self, index):
        if index == self.currentIndex(): return
        super().setCurrentIndex(index)
        
        self._offset_y = 12
        self._anim_group.stop()
        self._anim_group.setStartValue(12)
        self._anim_group.setEndValue(0)
        self._anim_group.start()
        
        self._opacity_anim.stop()
        self._opacity_anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        if self._offset_y != 0: p.translate(0, self._offset_y)
        super().paintEvent(event)

class BusyOverlay(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._angle = 0
        self._message = "Aguarde…"
        self._timer = QTimer(self)
        self._timer.setInterval(25)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def show_with(self, message: str):
        self._message = message
        self.resize(self.parentWidget().size())
        self._timer.start()
        self.show()
        self.raise_()

    def hide(self):
        self._timer.stop()
        super().hide()

    def hide_spinner(self):
        self.hide()

    def _tick(self):
        self._angle = (self._angle + 9) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fundo semi-transparente
        bg_color = QColor(COLORS["bg"])
        bg_color.setAlpha(200)
        painter.fillRect(self.rect(), bg_color)
        
        cx, cy = self.width() // 2, self.height() // 2
        R = 28
        
        # Spinner
        arc_pen = QPen(QColor(COLORS["accent"]))
        arc_pen.setWidth(5)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        painter.drawArc(cx - R, cy - R, R * 2, R * 2, (90 - self._angle) * 16, -270 * 16)
        
        # Mensagem
        if self._message:
            painter.setPen(QColor(COLORS["text"]))
            painter.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
            painter.drawText(
                self.rect().adjusted(0, R * 2 + 20, 0, 0),
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop,
                self._message
            )
        painter.end()


class BlurOverlay(QWidget):
    """
    Overlay que aplica um efeito de desfoque suave ao widget pai.
    Ideal para diálogos e modais "premium".
    """
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.hide()

    def show_event(self, event):
        self.resize(self.parentWidget().size())
        self.raise_()

    def paintEvent(self, event):
        p = QPainter(self)
        # Camada de vidro (blur simulado com cor semi-transparente + overlay)
        r, g, b = hex_to_rgb(COLORS["bg"])
        p.fillRect(self.rect(), QColor(r, g, b, 160))
        
        # Se o tema for escuro, adicionamos um toque de profundidade
        if theme_manager.mode == "dark":
            p.fillRect(self.rect(), QColor(0, 0, 0, 40))
