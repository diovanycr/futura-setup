# =============================================================================
# FUTURA SETUP — Página: Menu Principal
# =============================================================================

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import pyqtSignal, Qt, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QFont, QColor

from ui.widgets import PageTitle, spacer
from ui.theme import COLORS, FONT_SANS
from ui.theme_manager import theme_manager


class ActionCard(QWidget):
    """
    Card de acao no estilo grade - numero grande destacado, titulo e descricao.
    """
    clicked = pyqtSignal()

    def __init__(self, number: str, title: str, description: str,
                 accent: str, parent=None):
        super().__init__(parent)
        self._accent = accent
        self._state  = "normal"
        self._glow   = 0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(88)

        self._anim = QPropertyAnimation(self, b"glow")
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setOffset(0, 0)
        self._shadow.setColor(QColor(accent))
        self.setGraphicsEffect(self._shadow)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(3)

        self._num_lbl = QLabel(number)
        self._num_lbl.setFont(QFont(FONT_SANS, 20, QFont.Weight.Bold))

        self._title_lbl = QLabel(title)
        self._title_lbl.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        self._title_lbl.setObjectName("card_title")

        self._desc_lbl = QLabel(description)
        self._desc_lbl.setFont(QFont(FONT_SANS, 10))
        self._desc_lbl.setObjectName("card_desc")
        self._desc_lbl.setWordWrap(True)

        lay.addWidget(self._num_lbl)
        lay.addWidget(self._title_lbl)
        lay.addWidget(self._desc_lbl)
        lay.addStretch()

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    @pyqtProperty(int)
    def glow(self):
        return self._glow

    @glow.setter
    def glow(self, val):
        self._glow = val
        self._shadow.setBlurRadius(val * 0.25) # 0 a 25px
        self._upd()

    def _upd(self, _mode: str = ""):
        # Mistura a cor de destaque com a opacidade do brilho
        if self._state == "hover":
            bg = COLORS["accent_dim"]
            border = self._accent
        elif self._state == "press":
            bg = COLORS["panel_press"]
            border = self._accent
        else:
            bg = COLORS["surface"]
            border = COLORS["border"]

        self.setStyleSheet(f"""
            ActionCard {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 10px;
            }}
            QLabel#card_title {{
                color: {COLORS['text']};
                background: transparent;
                border: none;
            }}
            QLabel#card_desc {{
                color: {COLORS['text_dim']};
                background: transparent;
                border: none;
            }}
        """)
        self._num_lbl.setStyleSheet(
            f"color: {self._accent}; background: transparent; border: none;"
        )

    def enterEvent(self, e):
        self._state = "hover"
        self._anim.stop()
        self._anim.setEndValue(100)
        self._anim.start()
        self._upd()

    def leaveEvent(self, e):
        self._state = "normal"
        self._anim.stop()
        self._anim.setEndValue(0)
        self._anim.start()
        self._upd()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._state = "press"
            self._upd()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._state = "hover" if self.rect().contains(e.pos()) else "normal"
            self._upd()
            if self.rect().contains(e.pos()):
                self.clicked.emit()


class SectionLabel(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont(FONT_SANS, 9, QFont.Weight.Bold))
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(
            f"color: {COLORS['text_dim']}; background: transparent;"
            f"padding: 4px 0px; letter-spacing: 1px;"
        )


class PageMenu(QWidget):
    go_atalhos           = pyqtSignal()
    go_terminal          = pyqtSignal()
    go_atualizacao       = pyqtSignal()
    go_log               = pyqtSignal()
    go_restaurar         = pyqtSignal()
    go_instalar_firebird = pyqtSignal()
    go_fb_portable       = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 36, 40, 36)
        lay.setSpacing(0)

        lay.addWidget(PageTitle("FUTURA SETUP", "Menu Principal"))
        lay.addWidget(spacer(h=8))

        # Secao: Implantacao
        lay.addWidget(SectionLabel("IMPLANTACAO"))
        lay.addWidget(spacer(h=6))

        grid_impl = QGridLayout()
        grid_impl.setSpacing(10)

        card_atalhos = ActionCard(
            "01", "Puxar via Rede",
            "Cria atalhos que executam os aplicativos direto do servidor",
            COLORS["accent"],
        )
        card_atalhos.clicked.connect(self.go_atalhos.emit)

        card_terminal = ActionCard(
            "02", "Novo Terminal",
            "Copia os arquivos e configura um terminal autonomo",
            COLORS["accent"],
        )
        card_terminal.clicked.connect(self.go_terminal.emit)

        card_atualizacao = ActionCard(
            "03", "Atualizar Sistema",
            "Baixa e executa a atualizacao completa do ERP Futura",
            COLORS["accent"],
        )
        card_atualizacao.clicked.connect(self.go_atualizacao.emit)

        grid_impl.addWidget(card_atalhos,     0, 0)
        grid_impl.addWidget(card_terminal,    0, 1)
        grid_impl.addWidget(card_atualizacao, 1, 0, 1, 2)

        lay.addLayout(grid_impl)
        lay.addWidget(spacer(h=20))

        # Divisor
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {COLORS.get('border', '#444')};")
        lay.addWidget(div)
        lay.addWidget(spacer(h=12))

        # Secao: Firebird
        lay.addWidget(SectionLabel("FIREBIRD"))
        lay.addWidget(spacer(h=6))

        grid_fb = QGridLayout()
        grid_fb.setSpacing(10)

        card_instalar = ActionCard(
            "04", "Instalar Firebird",
            "Baixa e instala o Firebird 3 ou 4 silenciosamente",
            COLORS["accent2"],
        )
        card_instalar.clicked.connect(self.go_instalar_firebird.emit)

        card_portable = ActionCard(
            "05", "Firebird Portable",
            "Instala e configura FB3 e FB4 de forma independente",
            COLORS["accent2"],
        )
        card_portable.clicked.connect(self.go_fb_portable.emit)

        grid_fb.addWidget(card_instalar, 0, 0)
        grid_fb.addWidget(card_portable, 0, 1)

        lay.addLayout(grid_fb)
        lay.addStretch()