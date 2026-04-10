# =============================================================================
# FUTURA SETUP — Página: Menu Principal
# =============================================================================

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import (
    pyqtSignal, Qt, QPropertyAnimation, QEasingCurve,
    pyqtProperty, QTimer
)
from PyQt6.QtGui import QFont, QColor

from ui.widgets import PageHeader, spacer, label
from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager

from core.logger import log
from core.service_manager import servico_rodando, is_fb3_oficial_rodando


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


class DashboardWidget(QFrame):
    def __init__(self, icon: str, title: str, value: str, color: str, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setFixedHeight(70)
        
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)
        
        self.icon_lbl = QLabel(icon)
        self.icon_lbl.setFont(QFont(FONT_SANS, 16))
        self.icon_lbl.setStyleSheet(f"color: {color}; background: transparent;")
        
        info_lay = QVBoxLayout()
        info_lay.setSpacing(2)
        
        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
        
        self.value_lbl = QLabel(value)
        self.value_lbl.setFont(QFont(FONT_MONO, 10, QFont.Weight.Bold))
        self.value_lbl.setWordWrap(True)
        self.value_lbl.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        
        info_lay.addWidget(self.title_lbl)
        info_lay.addWidget(self.value_lbl)
        
        lay.addWidget(self.icon_lbl)
        lay.addLayout(info_lay, 1)
        
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode=""):
        self.setStyleSheet(f"""
            DashboardWidget {{
                background: {COLORS['surface2']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
    
    def set_value(self, val: str, color: str = None):
        self.value_lbl.setText(val)
        if color:
            self.value_lbl.setStyleSheet(f"color: {color}; background: transparent;")


class PageMenu(QWidget):
    go_atalhos           = pyqtSignal()
    go_terminal          = pyqtSignal()
    go_atualizacao       = pyqtSignal()
    go_log               = pyqtSignal()
    go_restaurar         = pyqtSignal()
    go_instalar_firebird = pyqtSignal()
    go_fb_portable       = pyqtSignal()
    go_utilitarios       = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = PageHeader("FUTURA SETUP", "Menu Principal", back_visible=False)
        root.addWidget(header)

        # Container para o conteúdo original
        content_w = QWidget()
        content_lay = QVBoxLayout(content_w)
        content_lay.setContentsMargins(40, 20, 40, 36)
        content_lay.setSpacing(0)

        # -- DASHBOARD --
        dash_lay = QHBoxLayout()
        dash_lay.setSpacing(12)
        
        server_hist = log.prefs.servidores_hist
        srv_name = server_hist[0]["hostname"] if server_hist else "Nenhum"
        self._dash_srv = DashboardWidget("☁", "Servidor", srv_name, COLORS["accent"])
        
        self._dash_fb = DashboardWidget("🔥", "Firebird", "Checando...", COLORS["accent2"])
        
        self._dash_bkp = DashboardWidget("💾", "Last Backup", log.prefs.last_backup, COLORS["warn"])
        
        import platform
        import socket
        sys_info = f"{platform.system()} {platform.release()}"
        self._dash_sys = DashboardWidget("🖥", "Sistema", sys_info, COLORS["accent"])

        dash_lay.addWidget(self._dash_srv)
        dash_lay.addWidget(self._dash_fb)
        dash_lay.addWidget(self._dash_bkp)
        dash_lay.addWidget(self._dash_sys)
        dash_lay.addStretch()
        
        content_lay.addLayout(dash_lay)
        content_lay.addWidget(spacer(h=24))

        # Secao: Implantacao
        content_lay.addWidget(SectionLabel("IMPLANTACAO"))
        content_lay.addWidget(spacer(h=6))

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

        content_lay.addLayout(grid_impl)
        content_lay.addWidget(spacer(h=20))

        # Divisor
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {COLORS.get('border', '#444')};")
        content_lay.addWidget(div)
        content_lay.addWidget(spacer(h=12))

        # Secao: Firebird
        content_lay.addWidget(SectionLabel("FIREBIRD"))
        content_lay.addWidget(spacer(h=6))

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

        content_lay.addLayout(grid_fb)
        content_lay.addWidget(spacer(h=24))

        # Secao: Utilitarios
        content_lay.addWidget(SectionLabel("UTILITARIOS"))
        content_lay.addWidget(spacer(h=6))

        card_util = ActionCard(
            "06", "Ferramentas",
            "Logs, Backup, Firewall, Diagnostico e mais",
            COLORS["accent2"],
        )
        card_util.clicked.connect(self.go_utilitarios.emit)
        content_lay.addWidget(card_util)

        content_lay.addStretch()

        root.addWidget(content_w, 1)
        
        # Timer para atualizar dashboard
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(10000) # 10s
        self._refresh_timer.timeout.connect(self.refresh_dashboard)
        self._refresh_timer.start()
        QTimer.singleShot(500, self.refresh_dashboard)

    def refresh_dashboard(self):
        """Atualiza widgets com dados reais do sistema."""
        # 1. Servidor
        server_hist = log.prefs.servidores_hist
        self._dash_srv.set_value(server_hist[0]["hostname"] if server_hist else "Nenhum")
        
        # 2. Firebird
        fb_online = any([
            servico_rodando("FirebirdServerDefaultInstance"),
            servico_rodando("FuturaFirebird3"),
            servico_rodando("FuturaFirebird4"),
            is_fb3_oficial_rodando()
        ])
        status_fb = "ONLINE" if fb_online else "OFFLINE"
        cor_fb = COLORS["accent2"] if fb_online else COLORS["danger"]
        self._dash_fb.set_value(status_fb, cor_fb)
        
        # 3. Backup
        self._dash_bkp.set_value(log.prefs.last_backup)