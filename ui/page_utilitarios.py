# =============================================================================
# FUTURA SETUP — Página: Utilitários
# =============================================================================

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import pyqtSignal, Qt, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QFont, QColor

from ui.widgets import PageHeader, spacer
from ui.theme import COLORS, FONT_SANS
from ui.theme_manager import theme_manager


class ActionButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, number: str, title: str, description: str,
                 accent: str, parent=None):
        super().__init__(parent)
        self._accent = accent
        self._state  = "normal"
        self._glow   = 0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(76)

        self._anim = QPropertyAnimation(self, b"glow")
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setOffset(0, 0)
        self._shadow.setColor(QColor(accent))
        self.setGraphicsEffect(self._shadow)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 16, 0)
        lay.setSpacing(0)

        self._badge = QLabel(number)
        self._badge.setFixedSize(60, 76)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))

        self._div = QWidget()
        self._div.setFixedSize(1, 76)

        txt_w = QWidget()
        txt_w.setObjectName("txt_w")
        txt = QVBoxLayout(txt_w)
        txt.setSpacing(4)
        txt.setContentsMargins(18, 0, 0, 0)

        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("btn_title")
        self._title_lbl.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))

        self._desc_lbl = QLabel(description)
        self._desc_lbl.setObjectName("btn_desc")
        self._desc_lbl.setFont(QFont(FONT_SANS, 11))

        txt.addStretch()
        txt.addWidget(self._title_lbl)
        txt.addWidget(self._desc_lbl)
        txt.addStretch()

        self._arrow = QLabel("›")
        self._arrow.setObjectName("btn_arrow")
        self._arrow.setFont(QFont(FONT_SANS, 18))
        self._arrow.setFixedWidth(20)
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(self._badge)
        lay.addWidget(self._div)
        lay.addWidget(txt_w, 1)
        lay.addWidget(self._arrow)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    @pyqtProperty(int)
    def glow(self):
        return self._glow

    @glow.setter
    def glow(self, val):
        self._glow = val
        self._shadow.setBlurRadius(val * 0.25)
        self._upd()

    def _upd(self, _mode: str = ""):
        if self._state == "hover":
            bg, border = COLORS["accent_dim"], self._accent
        elif self._state == "press":
            bg, border = COLORS["panel_press"], self._accent
        else:
            bg, border = COLORS["surface"], COLORS["border"]

        self.setStyleSheet(f"""
            ActionButton {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 8px;
            }}
            QLabel#btn_title {{
                color: {COLORS['text']};
                border: none;
                background: transparent;
            }}
            QLabel#btn_desc {{
                color: {COLORS['text_mid']};
                border: none;
                background: transparent;
            }}
            QLabel#btn_arrow {{
                color: {COLORS['text_dim']};
                border: none;
                background: transparent;
            }}
            QWidget#txt_w {{
                border: none;
                background: transparent;
            }}
        """)
        self._badge.setStyleSheet(
            f"color: {self._accent}; border: none; background: transparent;"
        )
        self._div.setStyleSheet(
            f"background: {COLORS['border']}; border: none;"
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


class PageUtilitarios(QWidget):
    go_menu                 = pyqtSignal()
    go_log                  = pyqtSignal()
    go_backup_gbak          = pyqtSignal()
    go_port_opener          = pyqtSignal()
    go_diagnostico          = pyqtSignal()
    go_editar_func          = pyqtSignal()
    go_implantar_mobile     = pyqtSignal()
    go_shutdown_online      = pyqtSignal()
    go_verificar_versao_fdb = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = PageHeader("UTILITARIOS", "Ferramentas auxiliares do sistema")
        self._header.back_clicked.connect(self.go_menu.emit)
        root.addWidget(self._header)

        # Container para o conteúdo original
        content_w = QWidget()
        content_lay = QVBoxLayout(content_w)
        content_lay.setContentsMargins(40, 24, 40, 36)
        content_lay.setSpacing(0)

        btn_lay = QVBoxLayout()
        btn_lay.setSpacing(12)
        btn_lay.setContentsMargins(0, 8, 0, 0)

        items = [
            ("01", "Ver Log",
             "Visualiza o historico de operacoes e eventos do sistema",
             COLORS["accent2"], self.go_log),
            ("02", "Backup / Restaurar DB",
             "Gera ou restaura backup do banco de dados Firebird (.gbak)",
             COLORS["accent2"], self.go_backup_gbak),
            ("03", "Firewall — Portas",
             "Abre ou fecha portas no firewall do Windows",
             COLORS["accent2"], self.go_port_opener),
            ("04", "Diagnostico",
             "Testa conectividade, share, Firebird e versao de um servidor",
             COLORS["accent2"], self.go_diagnostico),
            ("05", "Editar Funcionario",
             "Altera dados de login e senha de funcionarios no banco",
             COLORS["accent2"], self.go_editar_func),
            ("06", "Implantar Mobile",
             "Configura e implanta o modulo mobile no servidor",
             COLORS["accent2"], self.go_implantar_mobile),
            ("07", "Shutdown / Online",
             "Encerra ou coloca o sistema online remotamente",
             COLORS["accent2"], self.go_shutdown_online),
            ("08", "Verificar Versao .fdb",
             "Detecta a versao do Firebird e valida a integridade do arquivo",
             COLORS["accent2"], self.go_verificar_versao_fdb),
        ]

        for num, title, desc, accent, sig in items:
            btn = ActionButton(num, title, desc, accent)
            btn.clicked.connect(sig.emit)
            btn_lay.addWidget(btn)

        content_lay.addLayout(btn_lay)
        content_lay.addStretch()

        root.addWidget(content_w, 1)