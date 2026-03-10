# =============================================================================
# FUTURA SETUP -- Widgets v8
# Melhorias v8:
#   - card_style(): helper centralizado para estados normal/hover/selected
#     → elimina duplicação em ServerItem, BackupItem, ToggleRow, RadioRow
#   - ServerItem / BackupItem: usam pyqtSignal em vez de callback por atributo
#   - theme_changed conectado com self._upd (sem lambda desnecessária)
#   - _DestOpt: subclasse de QWidget em vez de monkey-patch de mousePressEvent
#   - make_btn_row: parâmetro back_fn removido (use back=)
# Melhorias v9:
#   - ProgressBlock.set_progress(): alias de update() para compatibilidade
# Melhorias v10:
#   - ConfirmDialog centralizado
# Melhorias v11:
#   - RadioRow._upd: QRadioButton estilizado via stylesheet
# Melhorias v12:
#   - LogConsole: SizePolicy expandindo corretamente (sem max_height fixo)
# =============================================================================

import html

from PyQt6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout,
    QPushButton, QFrame, QProgressBar, QTextEdit,
    QSizePolicy, QRadioButton, QDialog, QStackedWidget,
    QGridLayout, QScrollArea, QFileDialog, QLineEdit,
    QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtProperty, QPropertyAnimation, QEasingCurve, QByteArray, QRectF
from PyQt6.QtGui import QFont, QPainter, QColor, QBrush, QPen, QIcon, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from ui.theme import COLORS, FONT_MONO, FONT_SANS
from ui.theme_manager import theme_manager


# ── UTILITÁRIOS ───────────────────────────────────────────────────────────────

def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def card_style(state: str, selected: bool) -> tuple[str, str]:
    if selected:
        return COLORS["accent_dim"], COLORS["accent"]
    elif state == "hover":
        return COLORS["panel_hover"], COLORS["border_light"]
    return COLORS["surface"], COLORS["border"]


def make_btn(text: str, cls: str = "secondary", min_width: int = 120) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("class", cls)
    btn.setMinimumWidth(min_width)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyle(btn.style())
    return btn


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


# ── BUTTON HELPERS ────────────────────────────────────────────────────────────

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


def make_folder_btn(parent=None) -> QPushButton:
    """Cria um botão de seleção de pasta padronizado."""
    btn = make_secondary_btn("", 40)
    btn.setIcon(
        QApplication.style().standardIcon(
            QApplication.style().StandardPixmap.SP_DirOpenIcon
        )
    )
    btn.setMaximumWidth(40)
    btn.setMinimumHeight(28)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip("Selecionar pasta")
    return btn

def btn_row(*btns, centered: bool = True) -> QWidget:
    """Cria uma linha de botões centralizada ou alinhada à esquerda."""
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


# ── SECTION HEADER ────────────────────────────────────────────────────────────

class SectionHeader(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 8)
        lay.setSpacing(0)
        self._lbl = QLabel(text)
        self._lbl.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
        lay.addWidget(self._lbl)
        lay.addStretch()
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        self._lbl.setStyleSheet(
            f"color: {COLORS['text']}; background: transparent; border: none;"
        )


# ── PAGE TITLE ────────────────────────────────────────────────────────────────

class PageTitle(QWidget):
    def __init__(self, tag: str, title: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 24)
        lay.setSpacing(2)

        self._tag_lbl   = QLabel(tag.upper())
        self._tag_lbl.setFont(QFont(FONT_SANS, 11))

        self._title_lbl = QLabel(title)
        self._title_lbl.setFont(QFont(FONT_SANS, 22, QFont.Weight.Bold))

        self._line = QFrame()
        self._line.setFrameShape(QFrame.Shape.HLine)
        self._line.setFixedHeight(1)

        lay.addWidget(self._tag_lbl)
        lay.addWidget(self._title_lbl)
        lay.addWidget(spacer(h=6))
        lay.addWidget(self._line)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        self._tag_lbl.setStyleSheet(
            f"color: {COLORS['text_dim']}; background: transparent; border: none;"
        )
        self._title_lbl.setStyleSheet(
            f"color: {COLORS['text']}; background: transparent; border: none;"
        )
        self._line.setStyleSheet(f"background: {COLORS['border']}; border: none;")


# ── ALERT BOX ─────────────────────────────────────────────────────────────────

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
        self._icon_w.setObjectName("ab_icon")
        self._icon_w.setFixedSize(20, 20)
        self._icon_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_w.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))

        self._msg = QLabel(text)
        self._msg.setObjectName("ab_msg")
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
            color_key, icon_ch = self._KINDS[kind]
            self._kind = kind
            self._icon_w.setText(icon_ch)
            self._upd()

    def _upd(self, _mode: str = ""):
        color_key, _ = self._KINDS.get(self._kind, self._KINDS["info"])
        color = COLORS[color_key]
        dim   = COLORS.get(f"{color_key}_dim", COLORS["accent_dim"])
        self.setStyleSheet(f"""
            QWidget#AlertBox {{
                background: {dim};
                border-left: 3px solid {color};
                border-radius: 4px;
            }}
            QLabel#ab_icon {{ color: {color}; background: transparent; border: none; }}
            QLabel#ab_msg  {{ color: {COLORS['text']}; background: transparent; border: none; }}
        """)


# ── RESULT BOX ────────────────────────────────────────────────────────────────

class ResultBox(QWidget):
    _KINDS = {"success": "accent2", "error": "danger", "warning": "warn"}

    def __init__(self, title: str, rows: list, kind: str = "success", parent=None):
        super().__init__(parent)
        self._kind = kind
        self._row_widgets: list[tuple[QLabel, QLabel]] = []
        self.setObjectName("ResultBox")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(0)

        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("rb_title")
        self._title_lbl.setFont(QFont(FONT_SANS, 14, QFont.Weight.Bold))
        lay.addWidget(self._title_lbl)
        lay.addWidget(spacer(h=10))

        for key, val in rows:
            row_w = QWidget()
            row_w.setStyleSheet("background: transparent; border: none;")
            row_lay = QHBoxLayout(row_w)
            row_lay.setContentsMargins(0, 3, 0, 3)
            row_lay.setSpacing(16)
            k = QLabel(key)
            k.setFont(QFont(FONT_SANS, 11))
            k.setFixedWidth(110)
            v = QLabel(str(val))
            v.setFont(QFont(FONT_SANS, 12))
            v.setWordWrap(True)
            row_lay.addWidget(k)
            row_lay.addWidget(v, 1)
            lay.addWidget(row_w)
            self._row_widgets.append((k, v))

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        color = COLORS[self._KINDS.get(self._kind, "accent2")]
        self.setStyleSheet(f"""
            QWidget#ResultBox {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-left: 3px solid {color};
                border-radius: 4px;
            }}
            QLabel#rb_title {{ color: {color}; background: transparent; border: none; }}
        """)
        for k, v in self._row_widgets:
            k.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent; border: none;")
            v.setStyleSheet(f"color: {COLORS['text']}; background: transparent; border: none;")


# ── PROGRESS BLOCK ────────────────────────────────────────────────────────────

class ProgressBlock(QWidget):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("ProgressBlock")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        header = QHBoxLayout()
        self.name_lbl = QLabel(title)
        self.name_lbl.setObjectName("pb_name")
        self.name_lbl.setFont(QFont(FONT_SANS, 13))
        self.pct_lbl = QLabel("0%")
        self.pct_lbl.setObjectName("pb_pct")
        self.pct_lbl.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
        header.addWidget(self.name_lbl, 1)
        header.addWidget(self.pct_lbl)
        header_w = QWidget()
        header_w.setLayout(header)
        header_w.setStyleSheet("background: transparent; border: none;")

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setFixedHeight(3)
        self.bar.setTextVisible(False)

        self.sub_lbl = QLabel("Aguardando...")
        self.sub_lbl.setObjectName("pb_sub")
        self.sub_lbl.setFont(QFont(FONT_SANS, 11))

        lay.addWidget(header_w)
        lay.addWidget(self.bar)
        lay.addWidget(self.sub_lbl)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(f"""
            QWidget#ProgressBlock {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
            }}
            QLabel#pb_name {{ color: {COLORS['text']}; background: transparent; border: none; }}
            QLabel#pb_pct  {{ color: {COLORS['accent']}; background: transparent; border: none; }}
            QLabel#pb_sub  {{ color: {COLORS['text_dim']}; background: transparent; border: none; }}
        """)

    def update(self, value: int, name: str = None, sub: str = None):
        self.bar.setValue(value)
        self.pct_lbl.setText(f"{value}%")
        if name:
            self.name_lbl.setText(name)
        if sub:
            self.sub_lbl.setText(sub)

    def set_progress(self, value: int, name: str = None, sub: str = None):
        self.update(value, name, sub)


# ── LOG CONSOLE ───────────────────────────────────────────────────────────────

LOG_CONSOLE_MAX_LINES = 500


class LogConsole(QTextEdit):
    """
    Console de log com rolagem automática.
    Por padrão expande para preencher o espaço disponível no layout.
    Passe max_height > 0 apenas quando quiser limitar a altura (ex: consoles inline).
    """

    def __init__(self, max_height: int = 0, max_lines: int = LOG_CONSOLE_MAX_LINES,
                 parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont(FONT_MONO, 11))
        self.document().setMaximumBlockCount(max_lines)

        if max_height and max_height > 0:
            # Altura limitada (uso inline em outras páginas)
            self.setMaximumHeight(max_height)
            self.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
        else:
            # Expande para preencher todo o espaço disponível
            self.setMinimumHeight(120)
            self.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )

        self._upd_bg()
        theme_manager.theme_changed.connect(self._upd_bg)

    def _upd_bg(self, _mode: str = ""):
        bg = "#FAFAFA" if theme_manager.mode == "light" else "#111111"
        self.setStyleSheet(
            f"background: {bg};"
            f"border: 1px solid {COLORS['border']};"
            f"color: {COLORS['text_mid']};"
            f"font-family: Consolas;"
            f"font-size: 11px;"
            f"padding: 10px 14px;"
            f"border-radius: 4px;"
        )

    def _log_color(self, kind: str) -> str:
        return {
            "ok":   COLORS["log_ok"],
            "info": COLORS["log_info"],
            "warn": COLORS["log_warn"],
            "err":  COLORS["log_err"],
            "dim":  COLORS["text_dim"],
        }.get(kind, COLORS["text_dim"])

    def _make_html(self, text: str, kind: str) -> str:
        color = self._log_color(kind)
        safe  = html.escape(text)
        return f'<span style="color:{color};font-family:Consolas;font-size:11px">{safe}</span>'

    def append_line(self, text: str, kind: str = "dim"):
        self.append(self._make_html(text, kind))
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def clear_console(self):
        self.clear()


# ── FADE STACKED WIDGET ───────────────────────────────────────────────────────

class FadeStackedWidget(QStackedWidget):
    """
    Substituto para QStackedWidget com transição suave (fade).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self._opacity_anim.setDuration(250)
        self._opacity_anim.setStartValue(0.0)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def setCurrentIndex(self, index):
        if index == self.currentIndex():
            return
        # Para um fade simples, apenas reiniciamos a opacidade do widget inteiro
        # (Nota: Funciona melhor se os widgets filhos forem opacos ou tiverem fundo próprio)
        super().setCurrentIndex(index)
        self._opacity_anim.stop()
        self._opacity_anim.start()

    def setCurrentWidget(self, widget):
        idx = self.indexOf(widget)
        if idx >= 0:
            self.setCurrentIndex(idx)


# ── SERVER ITEM ───────────────────────────────────────────────────────────────

class ServerItem(QWidget):
    selected = pyqtSignal(object)

    def __init__(self, hostname: str, ip: str, path: str,
                 version: str = "", parent=None):
        super().__init__(parent)
        self.hostname  = hostname
        self.ip        = ip
        self.path      = path
        self.version   = version
        self._selected = False
        self._state    = "normal"
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(60)
        self.setObjectName("ServerItem")

        # Animação de lift (pos)
        self._offset_y = 0
        self._lift_anim = QPropertyAnimation(self, b"offset_y")
        self._lift_anim.setDuration(150)
        self._lift_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 16, 0)
        lay.setSpacing(0)

        dot_w = QWidget()
        dot_w.setObjectName("si_dot_w")
        dot_w.setFixedSize(40, 60)
        dot_lay = QVBoxLayout(dot_w)
        dot_lay.setContentsMargins(0, 0, 0, 0)
        dot_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dot = QWidget()
        self._dot.setObjectName("si_dot")
        self._dot.setFixedSize(8, 8)
        dot_lay.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignCenter)

        info_w = QWidget()
        info_w.setObjectName("si_info")
        info = QVBoxLayout(info_w)
        info.setSpacing(2)
        info.setContentsMargins(0, 0, 0, 0)

        self._name_lbl = QLabel(hostname)
        self._name_lbl.setObjectName("si_name")
        self._name_lbl.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))

        path_text = f"{path}  —  v{version}" if version else path
        self._path_lbl = QLabel(path_text)
        self._path_lbl.setObjectName("si_path")
        self._path_lbl.setFont(QFont(FONT_MONO, 10))

        info.addStretch()
        info.addWidget(self._name_lbl)
        info.addWidget(self._path_lbl)
        info.addStretch()

        self._ip_lbl = QLabel(ip)
        self._ip_lbl.setObjectName("si_ip")
        self._ip_lbl.setFont(QFont(FONT_MONO, 11))
        self._ip_lbl.setFixedWidth(110)
        self._ip_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        lay.addWidget(dot_w)
        lay.addWidget(info_w, 1)
        lay.addWidget(self._ip_lbl)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    @pyqtProperty(int)
    def offset_y(self):
        return self._offset_y

    @offset_y.setter
    def offset_y(self, v):
        self._offset_y = v
        # Ajusta a margem do layout para simular o "pulo"
        self.layout().setContentsMargins(0, v, 16, -v)
        self.update()

    def _upd(self, _mode: str = ""):
        bg, border = card_style(self._state, self._selected)
        name_c = COLORS["accent"] if self._selected else COLORS["text"]
        dot_c  = COLORS["accent"] if self._selected else COLORS["accent2"]

        self.setStyleSheet(f"""
            QWidget#ServerItem {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 8px;
            }}
            QWidget#si_dot_w {{ border: none; background: transparent; }}
            QWidget#si_info  {{ border: none; background: transparent; }}
            QWidget#si_dot   {{ background: {dot_c}; border-radius: 4px; border: none; }}
            QLabel#si_name {{ color: {name_c}; background: transparent; border: none; font-weight: 600; }}
            QLabel#si_path {{ color: {COLORS['text_dim']}; background: transparent; border: none; }}
            QLabel#si_ip   {{ color: {COLORS['text_dim']}; background: transparent; border: none; }}
        """)

    def set_selected(self, v: bool):
        self._selected = v
        self._upd()

    def enterEvent(self, e):
        self._state = "hover"
        self._upd()
        self._lift_anim.stop()
        self._lift_anim.setEndValue(-3)
        self._lift_anim.start()

    def leaveEvent(self, e):
        self._state = "normal"
        self._upd()
        self._lift_anim.stop()
        self._lift_anim.setEndValue(0)
        self._lift_anim.start()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self)


# ── STEP INDICATOR ────────────────────────────────────────────────────────────

class StepIndicator(QWidget):
    def __init__(self, steps: list[str], parent=None):
        super().__init__(parent)
        self._steps   = steps
        self._current = 0
        self.setFixedHeight(52)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._circles: list[QLabel] = []
        self._labels:  list[QLabel] = []
        self._lines:   list[QWidget] = []

        for i, name in enumerate(steps):
            sw = QWidget()
            sw.setStyleSheet("background: transparent; border: none;")
            sl = QVBoxLayout(sw)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(4)

            circle = QLabel(str(i + 1))
            circle.setFixedSize(22, 22)
            circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            circle.setFont(QFont(FONT_SANS, 9, QFont.Weight.Bold))
            self._circles.append(circle)

            lbl = QLabel(name)
            lbl.setFont(QFont(FONT_SANS, 8))
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            self._labels.append(lbl)

            sl.addWidget(circle, 0, Qt.AlignmentFlag.AlignHCenter)
            sl.addWidget(lbl,    0, Qt.AlignmentFlag.AlignHCenter)
            lay.addWidget(sw, 1)

            if i < len(steps) - 1:
                line = QWidget()
                line.setFixedHeight(2)
                line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                self._lines.append(line)
                lay.addWidget(line)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def set_step(self, current: int):
        self._current = current
        self._upd()

    def _upd(self, _mode: str = ""):
        for i, (circle, lbl) in enumerate(zip(self._circles, self._labels)):
            if i < self._current:
                circle.setStyleSheet(
                    f"background: {COLORS['accent2']}; color: #fff;"
                    "border-radius: 12px; border: none;"
                )
                lbl.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent; border: none;")
            elif i == self._current:
                circle.setStyleSheet(
                    f"background: {COLORS['accent']}; color: #fff;"
                    "border-radius: 11px; border: none;"
                )
                lbl.setStyleSheet(f"color: {COLORS['accent']}; font-weight: 600; background: transparent; border: none;")
            else:
                circle.setStyleSheet(
                    f"background: {COLORS['border']}; color: {COLORS['text_dim']};"
                    "border-radius: 12px; border: none;"
                )
                lbl.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent; border: none;")

        for i, line in enumerate(self._lines):
            color = COLORS["accent2"] if i < self._current - 1 else COLORS["border"]
            line.setStyleSheet(f"background: {color}; border: none;")


# ── MINI CHECKBOX ─────────────────────────────────────────────────────────────

class MiniCheckbox(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(14, 14)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("MiniCheckbox")
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        if self._checked:
            self.setStyleSheet(
                f"background: {COLORS['accent']}; border-radius: 7px; border: none;"
            )
        else:
            self.setStyleSheet(
                f"background: transparent; border-radius: 7px;"
                f"border: 1px solid {COLORS['border']};"
            )

    def toggle(self):
        self._checked = not self._checked
        self._upd()
        self.toggled.emit(self._checked)

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, v: bool):
        self._checked = v
        self._upd()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.toggle()


# ── MINI FILE ITEM ────────────────────────────────────────────────────────────

class MiniFileItem(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, name: str, size_str: str = "", parent=None):
        super().__init__(parent)
        self.name     = name
        self._checked = False
        self._state    = "normal"
        self.setFixedHeight(34)
        self.setObjectName("MiniFileItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Animação de lift (pos)
        self._offset_y = 0
        self._lift_anim = QPropertyAnimation(self, b"offset_y")
        self._lift_anim.setDuration(150)
        self._lift_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(8)

        self._check = QLabel()
        self._check.setObjectName("mfi_check")
        self._check.setFixedSize(16, 16)
        self._check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._check.setFont(QFont(FONT_SANS, 9, QFont.Weight.Bold))

        self._name_lbl = QLabel(name)
        self._name_lbl.setObjectName("mfi_name")
        self._name_lbl.setFont(QFont(FONT_MONO, 10))

        self._size_lbl = QLabel(size_str)
        self._size_lbl.setObjectName("mfi_size")
        self._size_lbl.setFont(QFont(FONT_MONO, 9))
        self._size_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        lay.addWidget(self._check)
        lay.addWidget(self._name_lbl, 1)
        if size_str:
            lay.addWidget(self._size_lbl)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    @pyqtProperty(int)
    def offset_y(self): return self._offset_y
    @offset_y.setter
    def offset_y(self, val):
        self._offset_y = val
        self.move(self.x(), self.y() + val) # Ajuste manual se necessário, mas pos é melhor
        # Se estiver em um layout, move() pode ser ignorado. 
        # Para Grid/Box layouts, o ideal é usar renderização com offset no paintEvent ou margens.
        # Vamos usar translação no paintEvent para ser mais robusto em layouts.
        self.update()

    def _upd(self, _mode: str = ""):
        if self._checked:
            bg, border    = COLORS["accent_dim"], COLORS["accent"]
            chk_bg, chk_bd, chk_txt = COLORS["accent"], "none", "✓"
        elif self._state == "hover":
            bg, border    = COLORS["panel_hover"], COLORS["border"]
            chk_bg, chk_bd, chk_txt = "transparent", f"1px solid {COLORS['text_dim']}", ""
        else:
            bg, border    = COLORS["surface"], COLORS["border"]
            chk_bg = "transparent"
            chk_bd = f"1px solid {COLORS['border']}"
            chk_txt = ""

        self.setStyleSheet(f"""
            QWidget#MiniFileItem {{
                background: {bg}; border: 1px solid {border}; border-radius: 6px;
            }}
            QLabel#mfi_check {{
                background: {chk_bg}; color: #ffffff;
                border-radius: 8px; border: {chk_bd}; font-size: 9px;
            }}
            QLabel#mfi_name {{ color: {COLORS['text']}; background: transparent; border: none; }}
            QLabel#mfi_size {{ color: {COLORS['text_dim']}; background: transparent; border: none; }}
        """)
        self._check.setText(chk_txt)

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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._offset_y != 0:
            painter.translate(0, self._offset_y)
        super().paintEvent(event)

    def toggle(self):
        self._checked = not self._checked
        self._upd()
        self.toggled.emit(self._checked)

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, v: bool):
        if self._checked != v:
            self._checked = v
            self._upd()
            self.toggled.emit(v)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.toggle()


# ── DEST PANEL ────────────────────────────────────────────────────────────────

class _DestOpt(QWidget):
    clicked = pyqtSignal(int)

    def __init__(self, rid: int, text: str, parent=None):
        super().__init__(parent)
        self.rid = rid
        self.setObjectName(f"dest_opt_{rid}")
        self._state    = "normal"
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Animação de lift (pos)
        self._offset_y = 0
        self._lift_anim = QPropertyAnimation(self, b"offset_y")
        self._lift_anim.setDuration(150)
        self._lift_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(7)

        self._dot = QWidget()
        self._dot.setObjectName(f"dest_dot_{rid}")
        self._dot.setFixedSize(10, 10)

        self._lbl = QLabel(text)
        self._lbl.setObjectName(f"dest_lbl_{rid}")
        self._lbl.setFont(QFont(FONT_SANS, 11))

        lay.addWidget(self._dot)
        lay.addWidget(self._lbl)
        lay.addStretch()

        self.apply_selected(False)
        theme_manager.theme_changed.connect(lambda _: self.apply_selected(self._is_selected()))

    def _is_selected(self):
        # Helper para pegar o estado real via parent se necessário, 
        # mas quem controla é o DestPanel chamando apply_selected.
        # Vamos manter o estado local para o hover.
        return getattr(self, "_selected_state", False)

    @pyqtProperty(int)
    def offset_y(self): return self._offset_y
    @offset_y.setter
    def offset_y(self, val):
        self._offset_y = val
        self.update()

    def enterEvent(self, e):
        self._state = "hover"
        self.apply_selected(self._is_selected())
        self._lift_anim.stop()
        self._lift_anim.setEndValue(-2)
        self._lift_anim.start()

    def leaveEvent(self, e):
        self._state = "normal"
        self.apply_selected(self._is_selected())
        self._lift_anim.stop()
        self._lift_anim.setEndValue(0)
        self._lift_anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._offset_y != 0:
            painter.translate(0, self._offset_y)
        super().paintEvent(event)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.rid)

    def apply_selected(self, selected: bool):
        self._selected_state = selected
        rid = self.rid
        
        if selected:
            bg     = COLORS['accent_dim']
            border = "none"
            l_clr  = COLORS['accent']
            l_wght = 600
            d_bg   = COLORS['accent']
            d_brd  = "none"
        elif self._state == "hover":
            bg     = COLORS['panel_hover']
            border = f"1px solid {COLORS['border_light']}"
            l_clr  = COLORS['text']
            l_wght = "normal"
            d_bg   = "transparent"
            d_brd  = f"1.5px solid {COLORS['text_dim']}"
        else:
            bg     = "transparent"
            border = "none"
            l_clr  = COLORS['text_mid']
            l_wght = "normal"
            d_bg   = "transparent"
            d_brd  = f"1.5px solid {COLORS['border']}"

        self.setStyleSheet(f"QWidget#dest_opt_{rid} {{ background: {bg}; border-radius: 5px; border: {border}; }}")
        self._lbl.setStyleSheet(f"color: {l_clr}; font-weight: {l_wght}; background: transparent; border: none;")
        self._dot.setStyleSheet(f"background: {d_bg}; border-radius: 5px; border: {d_brd};")


class DestPanel(QWidget):
    changed = pyqtSignal(int)

    _OPTS = [
        (1, "Somente Desktop"),
        (2, "Somente Menu Iniciar"),
        (0, "Desktop + Menu Iniciar"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected = 1
        self.setObjectName("DestPanel")
        self.setFixedHeight(42)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._opts: list[_DestOpt] = []
        for i, (rid, text) in enumerate(self._OPTS):
            opt = _DestOpt(rid, text)
            opt.clicked.connect(self._select)
            self._opts.append(opt)
            lay.addWidget(opt, 1)
            if i < len(self._OPTS) - 1:
                div = QFrame()
                div.setFrameShape(QFrame.Shape.VLine)
                div.setFixedWidth(1)
                div.setObjectName("dest_div")
                lay.addWidget(div)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _select(self, rid: int):
        self._selected = rid
        self._upd()
        self.changed.emit(rid)

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(f"""
            QWidget#DestPanel {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['btn_border']};
                border-radius: 6px;
            }}
            QFrame#dest_div {{ background: {COLORS['border']}; border: none; }}
        """)
        for opt in self._opts:
            opt.apply_selected(opt.rid == self._selected)

    def selected_id(self) -> int:
        return self._selected

    def reset(self):
        self._select(1)


# ── RADIO ROW ─────────────────────────────────────────────────────────────────

class RadioRow(QWidget):
    def __init__(self, text: str, desc: str, checked: bool = False, parent=None):
        super().__init__(parent)
        self._state = "normal"
        self.setFixedHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("RadioRow")

        # Animação de lift (pos)
        self._offset_y = 0
        self._lift_anim = QPropertyAnimation(self, b"offset_y")
        self._lift_anim.setDuration(150)
        self._lift_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        txt_w = QWidget()
        txt_w.setObjectName("rr_txt")
        txt = QVBoxLayout(txt_w)
        txt.setSpacing(2)
        txt.setContentsMargins(20, 0, 0, 0)

        self._name_lbl = QLabel(text)
        self._name_lbl.setObjectName("rr_name")
        self._name_lbl.setFont(QFont(FONT_MONO, 12, QFont.Weight.Bold))
        self._name_lbl.setWordWrap(True)

        self._desc_lbl = QLabel(desc)
        self._desc_lbl.setObjectName("rr_desc")
        self._desc_lbl.setFont(QFont(FONT_SANS, 11))

        txt.addStretch()
        txt.addWidget(self._name_lbl)
        txt.addWidget(self._desc_lbl)
        txt.addStretch()

        radio_w = QWidget()
        radio_w.setObjectName("rr_radio_w")
        radio_w.setFixedWidth(52)
        r_lay = QVBoxLayout(radio_w)
        r_lay.setContentsMargins(0, 0, 16, 0)
        r_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._radio = QRadioButton()
        self._radio.setChecked(checked)
        self._radio.toggled.connect(self._upd)
        r_lay.addWidget(self._radio, 0, Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(txt_w, 1)
        lay.addWidget(radio_w)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._radio.setChecked(True)

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
    def offset_y(self, val):
        self._offset_y = val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._offset_y != 0:
            painter.translate(0, self._offset_y)
        super().paintEvent(event)

    def _upd(self, _mode=None):
        checked = self._radio.isChecked()
        bg, border = card_style(self._state, checked)
        self.setStyleSheet(f"""
            RadioRow {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 8px;
            }}
            QWidget#rr_txt     {{ border: none; background: transparent; }}
            QWidget#rr_radio_w {{ border: none; background: transparent; }}
            QLabel#rr_name     {{ color: {COLORS['text']}; border: none; background: transparent; }}
            QLabel#rr_desc     {{ color: {COLORS['text_mid']}; border: none; background: transparent; }}
            QRadioButton {{
                background: transparent;
                border: none;
            }}
            QRadioButton::indicator {{
                width: 16px; height: 16px;
                border-radius: 8px;
                border: 2px solid {COLORS['border']};
                background: transparent;
            }}
            QRadioButton::indicator:checked {{
                border: 2px solid {COLORS['accent']};
                background: {COLORS['accent']};
            }}
            QRadioButton::indicator:unchecked {{
                border: 2px solid {COLORS['border']};
                background: transparent;
            }}
        """)

    def radio(self) -> QRadioButton:
        return self._radio

    def isChecked(self) -> bool:
        return self._radio.isChecked()

# ── CUSTOM PATH CARD ──────────────────────────────────────────────────────────

class CustomPathCard(QWidget):
    path_selected = pyqtSignal(str)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._state = "normal"
        self.setFixedHeight(70)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("CustomPathCard")

        # Animação de lift
        self._offset_y = 0
        self._lift_anim = QPropertyAnimation(self, b"offset_y")
        self._lift_anim.setDuration(150)
        self._lift_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Esquerda: Texto e Input
        txt_w = QWidget()
        txt_w.setObjectName("cpc_txt")
        txt = QVBoxLayout(txt_w)
        txt.setSpacing(4)
        txt.setContentsMargins(20, 8, 0, 8)

        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("cpc_title")
        self._title_lbl.setFont(QFont(FONT_MONO, 12, QFont.Weight.Bold))

        self._input = QLineEdit()
        self._input.setPlaceholderText("Clique para selecionar a pasta...")
        self._input.setReadOnly(True)
        self._input.setCursor(Qt.CursorShape.PointingHandCursor)
        self._input.setObjectName("cpc_input")
        self._input.setStyleSheet(f"""
            QLineEdit#cpc_input {{
                background: transparent;
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 4px 12px;
                color: {COLORS['text_mid']};
                font-size: 11px;
            }}
            QLineEdit#cpc_input:focus {{
                border-color: {COLORS['accent']};
            }}
        """)

        txt.addWidget(self._title_lbl)
        txt.addWidget(self._input)

        # Direita: Radio e Botão Pasta
        right_w = QWidget()
        right_w.setObjectName("cpc_right")
        r_lay = QHBoxLayout(right_w)
        r_lay.setContentsMargins(8, 0, 16, 0)
        r_lay.setSpacing(12)

        self._radio = QRadioButton()
        self._radio.setFixedWidth(20)
        self._radio.toggled.connect(self._upd)

        self._btn_folder = make_folder_btn(self)
        self._btn_folder.setFixedSize(40, 36) # Um pouco maior para o card

        r_lay.addWidget(self._radio)
        r_lay.addWidget(self._btn_folder)

        lay.addWidget(txt_w, 1)
        lay.addWidget(right_w)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)


    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._radio.setChecked(True)
            if self._input.geometry().contains(e.pos() - self.layout().itemAt(0).widget().pos()):
                # Se clicou na área do input, abre o diálogo (será tratado no PageTerminal via sinal ou callback)
                pass

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
    def offset_y(self, val):
        self._offset_y = val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._offset_y != 0:
            painter.translate(0, self._offset_y)
        super().paintEvent(event)

    def _upd(self, _mode=None):
        checked = self._radio.isChecked()
        bg, border = card_style(self._state, checked)
        self.setStyleSheet(f"""
            QWidget#CustomPathCard {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 8px;
            }}
            QWidget#cpc_txt, QWidget#cpc_right {{ background: transparent; border: none; }}
            QLabel#cpc_title {{ color: {COLORS['text']}; background: transparent; }}
            QRadioButton::indicator {{
                width: 16px; height: 16px;
                border-radius: 8px;
                border: 2px solid {COLORS['border']};
            }}
            QRadioButton::indicator:checked {{
                border: 2px solid {COLORS['accent']};
                background: {COLORS['accent']};
            }}
        """)

    def set_path(self, path: str):
        self._input.setText(path)

    def path(self) -> str:
        return self._input.text()

    def radio(self) -> QRadioButton: return self._radio
    def btn_folder(self) -> QPushButton: return self._btn_folder
    def input_field(self) -> QLineEdit: return self._input

# ── PROCESS CARD ─────────────────────────────────────────────────────────────

class ProcessCard(QWidget):
    def __init__(self, pid: str, name: str, exe_path: str, parent=None):
        super().__init__(parent)
        self._state = "normal"
        self.setFixedHeight(58)
        self.setCursor(Qt.CursorShape.ArrowCursor) # Não é clicável por padrão, mas tem hover visual
        self.setObjectName("ProcessCard")

        # Animação de lift (pos)
        self._offset_y = 0
        self._lift_anim = QPropertyAnimation(self, b"offset_y")
        self._lift_anim.setDuration(150)
        self._lift_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(12)

        dot = QWidget()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {COLORS['warn']}; border-radius: 4px; border: none;")

        pid_lbl = QLabel(f"PID {pid}")
        pid_lbl.setFont(QFont(FONT_MONO, 10))
        pid_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
        pid_lbl.setFixedWidth(72)

        info_lay = QVBoxLayout()
        info_lay.setSpacing(1)
        info_lay.setContentsMargins(0, 0, 0, 0)
        
        name_lbl = QLabel(name)
        name_lbl.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        
        path_lbl = QLabel(exe_path)
        path_lbl.setFont(QFont(FONT_MONO, 9))
        path_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
        
        info_lay.addStretch()
        info_lay.addWidget(name_lbl)
        info_lay.addWidget(path_lbl)
        info_lay.addStretch()

        info_w = QWidget()
        info_w.setLayout(info_lay)
        info_w.setStyleSheet("background: transparent;")

        lay.addWidget(dot)
        lay.addWidget(pid_lbl)
        lay.addWidget(info_w, 1)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    @pyqtProperty(int)
    def offset_y(self): return self._offset_y
    @offset_y.setter
    def offset_y(self, val):
        self._offset_y = val
        self.update()

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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._offset_y != 0:
            painter.translate(0, self._offset_y)
        super().paintEvent(event)

    def _upd(self, _mode=None):
        bg, border = card_style(self._state, False)
        self.setStyleSheet(f"""
            QWidget#ProcessCard {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 8px;
            }}
        """)


# ── CONFIRM DIALOG ────────────────────────────────────────────────────────────

class ConfirmDialog(QDialog):
    def __init__(self, titulo: str, linhas: list[str], parent=None,
                 btn_ok: str = "Confirmar", btn_cancel: str = "Cancelar",
                 largura: int = 460):
        super().__init__(parent)
        self.setWindowTitle("Confirmar operação")
        self.setFixedWidth(largura)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint)
        self._confirmado = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(8)

        t = QLabel(titulo)
        t.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
        t.setWordWrap(True)
        t.setObjectName("cd_titulo")
        lay.addWidget(t)

        for linha in linhas:
            if not linha:
                lay.addSpacing(4)
                continue
            lbl = QLabel(linha)
            lbl.setFont(QFont(FONT_SANS, 11))
            lbl.setWordWrap(True)
            lbl.setObjectName("cd_linha")
            lay.addWidget(lbl)

        lay.addSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(8)
        b_cancel = make_btn(btn_cancel, "secondary", min_width=110)
        b_ok     = make_btn(btn_ok,     "primary",   min_width=110)
        b_cancel.clicked.connect(self.reject)
        b_ok.clicked.connect(self._aceitar)
        row.addStretch()
        row.addWidget(b_cancel)
        row.addWidget(b_ok)
        lay.addLayout(row)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(f"""
            QDialog {{
                background: {COLORS['surface']};
            }}
            QLabel#cd_titulo {{
                color: {COLORS['text']};
                background: transparent;
            }}
            QLabel#cd_linha {{
                color: {COLORS['text_mid']};
                background: transparent;
            }}
        """)

    def _aceitar(self):
        self._confirmado = True
        self.accept()

    def confirmado(self) -> bool:
        return self._confirmado


# ── WORKER GUARD DIALOG ───────────────────────────────────────────────────────

class WorkerGuardDialog(QWidget):
    confirmed = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WorkerGuardDialog")
        self.setFixedSize(420, 200)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        box = QWidget()
        box.setObjectName("gdbox")
        box_lay = QVBoxLayout(box)
        box_lay.setContentsMargins(28, 24, 28, 24)
        box_lay.setSpacing(16)

        icon_row = QHBoxLayout()
        icon_lbl = QLabel("⚠")
        icon_lbl.setFont(QFont(FONT_SANS, 22))
        icon_lbl.setObjectName("gd_icon")
        icon_row.addWidget(icon_lbl)
        icon_row.addStretch()

        title = QLabel("Operação em andamento")
        title.setFont(QFont(FONT_SANS, 14, QFont.Weight.Bold))
        title.setObjectName("gd_title")

        msg = QLabel(
            "Se sair agora, a operação atual será interrompida.\n"
            "Deseja continuar mesmo assim?"
        )
        msg.setFont(QFont(FONT_SANS, 12))
        msg.setObjectName("gd_msg")
        msg.setWordWrap(True)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_cancel = make_btn("Continuar aqui")
        btn_cancel.clicked.connect(self.cancelled.emit)
        btn_cancel.clicked.connect(self.close)
        btn_confirm = make_btn("Sair mesmo assim", "danger", 160)
        btn_confirm.clicked.connect(self.confirmed.emit)
        btn_confirm.clicked.connect(self.close)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_confirm)

        box_lay.addLayout(icon_row)
        box_lay.addWidget(title)
        box_lay.addWidget(msg)
        box_lay.addLayout(btn_row)
        outer.addWidget(box)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(f"""
            QWidget#gdbox {{
                background: {COLORS['surface']};
                border: 1.5px solid {COLORS['warn']};
                border-radius: 10px;
            }}
            QLabel#gd_icon  {{ color: {COLORS['warn']}; background: transparent; }}
            QLabel#gd_title {{ color: {COLORS['text']}; background: transparent; }}
            QLabel#gd_msg   {{ color: {COLORS['text_mid']}; background: transparent; }}
        """)


# ── LOADING SPINNER ───────────────────────────────────────────────────────────

class LoadingSpinner(QWidget):
    """
    Spinner circular moderno usando QPainter e animação suave.
    Utiliza as cores do tema (accent).
    """
    def __init__(self, size: int = 40, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._anim = QPropertyAnimation(self, b"angle")
        self._anim.setDuration(1000)
        self._anim.setStartValue(0)
        self._anim.setEndValue(360)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.Type.Linear)

        theme_manager.theme_changed.connect(lambda _: self.update())

    @pyqtProperty(int)
    def angle(self):
        return self._angle

    @angle.setter
    def angle(self, v):
        self._angle = v
        self.update()

    def start(self):
        self._anim.start()
        self.show()

    def stop(self):
        self._anim.stop()
        self.hide()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(4, 4, -4, -4)
        color = QColor(COLORS["accent"])

        # Desenha o fundo (opcional, um círculo sutil)
        bg_color = QColor(color)
        bg_color.setAlpha(30)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg_color))
        # p.drawEllipse(rect) # Se quiser um fundo circular sutil

        # Desenha o arco giratório
        pen = QPen(color)
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)

        # startAngle e spanAngle são em 1/16 de grau
        # O arco gira conforme self._angle
        start_angle = int(self._angle * 16)
        span_angle  = 280 * 16 # Arco um pouco maior para um look mais "líquido"

        p.drawArc(rect, -start_angle, span_angle)

        # Adiciona um segundo arco mais fino para detalhe (opcional, mas premium)
        pen.setWidth(1)
        color_detail = QColor(color)
        color_detail.setAlpha(100)
        pen.setColor(color_detail)
        p.setPen(pen)
        p.drawArc(rect.adjusted(3, 3, -3, -3), int(start_angle * 1.5), span_angle)

        p.end()


# ── MENU CARD ─────────────────────────────────────────────────────────────────

class MenuCard(QWidget):
    """Mantido para compatibilidade com código legado."""
    def __init__(self, number: str, title: str, description: str,
                 accent: str = None, parent=None):
        super().__init__(parent)
        self._accent = accent or COLORS["accent"]
        self._state  = "normal"
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(100)
        self.setObjectName("MenuCard")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.setContentsMargins(0, 0, 0, 0)

        self._num_lbl = QLabel(number)
        self._num_lbl.setObjectName("mc_num")
        self._num_lbl.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))

        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("mc_title")
        self._title_lbl.setFont(QFont(FONT_SANS, 14, QFont.Weight.Bold))

        top.addWidget(self._num_lbl)
        top.addWidget(self._title_lbl)
        top.addStretch()

        top_w = QWidget()
        top_w.setObjectName("mc_top")
        top_w.setLayout(top)

        self._desc_lbl = QLabel(description)
        self._desc_lbl.setObjectName("mc_desc")
        self._desc_lbl.setFont(QFont(FONT_SANS, 12))
        self._desc_lbl.setWordWrap(True)

        lay.addWidget(top_w)
        lay.addWidget(self._desc_lbl)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _bg(self) -> str:
        r, g, b = hex_to_rgb(self._accent)
        if self._state == "press":
            return f"rgba({r},{g},{b},0.18)"
        elif self._state == "hover":
            return f"rgba({r},{g},{b},0.10)"
        return f"rgba({r},{g},{b},0.06)"

    def _upd(self, _mode: str = ""):
        r, g, b = hex_to_rgb(self._accent)
        border = (f"rgba({r},{g},{b},0.5)" if self._state == "hover"
                  else f"rgba({r},{g},{b},0.25)")
        self.setStyleSheet(f"""
            QWidget#MenuCard {{
                background: {self._bg()};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QWidget#mc_top  {{ border: none; background: transparent; }}
            QLabel#mc_num   {{ color: {self._accent}; background: transparent; border: none; }}
            QLabel#mc_title {{ color: {COLORS['text']}; background: transparent; border: none; }}
            QLabel#mc_desc  {{ color: {COLORS['text_mid']}; background: transparent; border: none; }}
        """)

    def enterEvent(self, e):
        self._state = "hover"
        self._upd()

    def leaveEvent(self, e):
        self._state = "normal"
        self._upd()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._state = "press"
            self._upd()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._state = "hover"
            self._upd()
            if self.rect().contains(e.pos()):
                self.clicked()

    def clicked(self): pass