# =============================================================================
# FUTURA SETUP — UI Components: Firebird Widgets
# =============================================================================

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QProgressBar, QRadioButton, QListWidget, QListWidgetItem,
    QAbstractItemView, QFileDialog, QAbstractButton, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath

from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets import (
    make_primary_btn, make_secondary_btn, make_danger_btn,
    spacer, label, h_line
)

# Constantes
FB_PORTABLE_CONFIGS = {
    "3": {"label": "Firebird 3.0 Portable", "tag": "FB3"},
    "4": {"label": "Firebird 4.0 Portable", "tag": "FB4"},
}

# Cores por versão
COR_VERSAOT = {
    "3": COLORS.get("accent2", "#2ecc71"),
    "4": COLORS.get("accent",  "#0078d4"),
}

class FirebirdBannerAdmin(QFrame):
    reiniciar_solicitado = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FirebirdBannerAdmin")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)

        icon = QLabel("⚠")
        icon.setFont(QFont(FONT_SANS, 14, QFont.Weight.Bold))
        icon.setStyleSheet(f"color: {COLORS['warn']}; background: transparent;")

        msg = QLabel("Permissao de administrador necessaria para instalacao / servicos do Firebird.")
        msg.setFont(QFont(FONT_SANS, 10))
        msg.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")

        btn = make_primary_btn("EXECUTAR COMO ADMIN", 180)
        btn.setFixedHeight(30)
        btn.clicked.connect(self.reiniciar_solicitado.emit)

        lay.addWidget(icon)
        lay.addWidget(msg, 1)
        lay.addWidget(btn)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode=""):
        self.setStyleSheet(f"""
            QFrame#FirebirdBannerAdmin {{
                background: {COLORS['warn_dim']};
                border: 1px solid {COLORS['warn']};
                border-radius: 8px;
            }}
        """)

class FirebirdVersionCard(QFrame):
    instalar_solicitado = pyqtSignal(str) # (versao)

    def __init__(self, versao: str, arch: str, parent=None):
        super().__init__(parent)
        self._versao = versao
        self._arch   = arch
        self.setObjectName(f"FirebirdVersionCard_{versao}")
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        # Header
        header = QHBoxLayout()
        self.title_lbl = QLabel(f"Firebird {versao}")
        self.title_lbl.setFont(QFont(FONT_SANS, 14, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet(f"color: {COR_VERSAOT[versao]};")
        
        self._badge = QLabel("N/A")
        self._badge.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setContentsMargins(10, 4, 10, 4)
        
        header.addWidget(self.title_lbl, 1)
        header.addWidget(self._badge)
        lay.addLayout(header)

        lay.addWidget(h_line())

        self.info_lbl = QLabel(f"Relase Oficial: {arch}")
        self.info_lbl.setFont(QFont(FONT_MONO, 9))
        self.info_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        lay.addWidget(self.info_lbl)

        desc_txt = "Estável e compatível com ERPs legados." if versao == "3" else "Performantee moderno para novas bases."
        self.desc_lbl = QLabel(desc_txt)
        self.desc_lbl.setFont(QFont(FONT_SANS, 10))
        self.desc_lbl.setWordWrap(True)
        lay.addWidget(self.desc_lbl)

        lay.addStretch()

        # Botão
        self._btn = make_primary_btn("BAIXAR E INSTALAR", 200)
        self._btn.setFixedHeight(38)
        self._btn.clicked.connect(lambda: self.instalar_solicitado.emit(versao))
        lay.addWidget(self._btn, 0, Qt.AlignmentFlag.AlignCenter)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode=""):
        acc = COR_VERSAOT[self._versao]
        self.setStyleSheet(f"""
            QFrame#FirebirdVersionCard_{self._versao} {{
                background: {COLORS['surface']};
                border: 1.5px solid {COLORS['border']};
                border-radius: 12px;
            }}
            QFrame#FirebirdVersionCard_{self._versao}:hover {{
                border-color: {acc};
                background: {COLORS['surface2']};
            }}
        """)
        self.set_installed(False) # Reset initial state if needed

    def set_installed(self, v: bool):
        brd = COLORS["border"]
        if v:
            self._badge.setText("INSTALADO")
            self._badge.setStyleSheet(f"background: {COLORS['accent2']}; color: white; border-radius: 4px;")
            self._btn.setText("REINSTALAR")
        else:
            self._badge.setText("NÃO DETECTADO")
            self._badge.setStyleSheet(f"background: {COLORS['surface2']}; color: {COLORS['text_dim']}; border: 1px solid {brd}; border-radius: 4px;")
            self._btn.setText("BAIXAR E INSTALAR")

class FirebirdServiceCard(QFrame):
    acao_solicitada = pyqtSignal(str, str) # (versao, acao)

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self._versao = versao
        self.setObjectName(f"FirebirdServiceCard_{versao}")
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)

        # Header
        header = QHBoxLayout()
        self.title_lbl = QLabel(f"Firebird {versao}")
        self.title_lbl.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet(f"color: {COR_VERSAOT[versao]};")
        
        self.status_badge = QLabel("VERIFICANDO")
        self.status_badge.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setContentsMargins(8, 3, 8, 3)
        
        header.addWidget(self.title_lbl, 1)
        header.addWidget(self.status_badge)
        lay.addLayout(header)

        lay.addWidget(h_line())

        self.path_lbl = QLabel("Aguardando detecção...")
        self.path_lbl.setFont(QFont(FONT_MONO, 8))
        self.path_lbl.setWordWrap(True)
        self.path_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        lay.addWidget(self.path_lbl)

        lay.addStretch()

        # Botões
        self.btn_iniciar = make_primary_btn("INICIAR", 100)
        self.btn_parar = make_danger_btn("PARAR", 90)
        self.btn_reiniciar = make_secondary_btn("REINICIAR", 100)

        for b in (self.btn_iniciar, self.btn_parar, self.btn_reiniciar):
            b.setFixedHeight(32)

        self.btn_iniciar.clicked.connect(lambda: self.acao_solicitada.emit(versao, "iniciar"))
        self.btn_parar.clicked.connect(lambda: self.acao_solicitada.emit(versao, "parar"))
        self.btn_reiniciar.clicked.connect(lambda: self.acao_solicitada.emit(versao, "reiniciar"))

        btn_lay = QHBoxLayout()
        btn_lay.addWidget(self.btn_iniciar)
        btn_lay.addWidget(self.btn_parar)
        btn_lay.addWidget(self.btn_reiniciar)
        lay.addLayout(btn_lay)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode=""):
        acc = COR_VERSAOT[self._versao]
        self.setStyleSheet(f"""
            QFrame#FirebirdServiceCard_{self._versao} {{
                background: {COLORS['surface']};
                border: 1.5px solid {COLORS['border']};
                border-radius: 12px;
            }}
            QFrame#FirebirdServiceCard_{self._versao}:hover {{
                border-color: {acc};
            }}
        """)

    def atualizar(self, instalado: bool, rodando: bool, pasta: str):
        acc = COR_VERSAOT[self._versao]
        brd = COLORS["border"]
        
        if rodando:
            self.status_badge.setText("ONLINE")
            self.status_badge.setStyleSheet(f"background: {acc}; color: white; border-radius: 4px;")
        elif instalado:
            self.status_badge.setText("PARADO")
            self.status_badge.setStyleSheet(f"background: {COLORS['surface2']}; color: {COLORS['text_dim']}; border: 1px solid {brd}; border-radius: 4px;")
        else:
            self.status_badge.setText("AUSENTE")
            self.status_badge.setStyleSheet(f"background: transparent; color: {COLORS['text_disabled']}; border: 1px solid {brd}; border-radius: 4px;")

        self.path_lbl.setText(pasta if pasta else "Não instalado")
        self.btn_iniciar.setEnabled(instalado and not rodando)
        self.btn_parar.setEnabled(rodando)
        self.btn_reiniciar.setEnabled(rodando)

class FirebirdToggleSwitch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(52, 28)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        checked = self.isChecked()
        enabled = self.isEnabled()
        
        # Cores v5.0
        track_bg = QColor(COLORS["accent"]) if checked else QColor(COLORS["border"])
        if not enabled: track_bg = QColor(COLORS["surface2"])
        
        thumb_bg = QColor("#fff")
        
        # Track
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track_bg)
        p.drawRoundedRect(0, 4, 52, 20, 10, 10)
        
        # Thumb
        p.setBrush(thumb_bg)
        thumb_x = 30 if checked else 4
        p.drawEllipse(thumb_x, 4, 20, 20)
        p.end()

class FirebirdPortableToggleRow(QFrame):
    clicked = pyqtSignal(bool)

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self._versao = versao
        self.setObjectName(f"FirebirdPortableToggleRow_{versao}")
        
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(12)

        self.dot = QWidget()
        self.dot.setFixedSize(10, 10)
        self.dot.setStyleSheet(f"background: {COLORS['text_dim']}; border-radius: 5px;")

        info_lay = QVBoxLayout()
        self.title_lbl = label(FB_PORTABLE_CONFIGS[versao]["label"], COLORS["text"], 11, bold=True)
        self.status_lbl = label("Desconectado", COLORS["text_dim"], 9)
        info_lay.addWidget(self.title_lbl)
        info_lay.addWidget(self.status_lbl)

        self.badge = label("OFFLINE", COLORS["text_dim"], 8, bold=True)
        self.badge.setFixedWidth(60)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.toggle = FirebirdToggleSwitch()
        self.toggle.clicked.connect(self.clicked.emit)

        lay.addWidget(self.dot)
        lay.addLayout(info_lay, 1)
        lay.addWidget(self.badge)
        lay.addWidget(self.toggle)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode=""):
        self.setStyleSheet(f"""
            QFrame#FirebirdPortableToggleRow_{self._versao} {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
            QFrame#FirebirdPortableToggleRow_{self._versao}:hover {{
                border-color: {COR_VERSAOT[self._versao]};
            }}
        """)

    def set_estado(self, ativo: bool, instalado: bool, msg: str = ""):
        acc = COR_VERSAOT[self._versao]
        self.dot.setStyleSheet(f"background: {acc if ativo else COLORS['text_dim']}; border-radius: 5px;")
        self.badge.setText("ATIVO" if ativo else "INATIVO")
        self.badge.setStyleSheet(f"color: {acc if ativo else COLORS['text_dim']}; font-weight: bold;")
        self.status_lbl.setText(msg if msg else ("Instalado" if instalado else "Não instalado"))
        self.toggle.setChecked(ativo)
        self.toggle.setEnabled(instalado)

class FirebirdStatusCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FirebirdStatusCard")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        
        self.icon = label("📡", COLORS["text_dim"], 18)
        
        info = QVBoxLayout()
        self.title = label("Status do Sistema", COLORS["text"], 11, bold=True)
        self.detail = label("Verificando...", COLORS["text_dim"], 9)
        info.addWidget(self.title)
        info.addWidget(self.detail)
        
        lay.addWidget(self.icon)
        lay.addLayout(info, 1)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode=""):
        self.setStyleSheet(f"""
            QFrame#FirebirdStatusCard {{
                background: {COLORS['surface2']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)

    def atualizar(self, instalado: bool, ver_str: str, fb_dir: str, label_v: str):
        self.icon.setText("✅" if instalado else "❌")
        self.title.setText(f"{label_v} {'Instalado' if instalado else 'Não Detectado'}")
        self.title.setStyleSheet(f"color: {COLORS['accent2'] if instalado else COLORS['text_dim']}; font-weight: bold;")
        self.detail.setText(f"{ver_str} | {fb_dir}" if instalado else f"Base: {fb_dir}")

class FirebirdAutoInstallCard(QFrame):
    acao_solicitada = pyqtSignal(str)
    sig_set_loading = pyqtSignal(bool, str, int)

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self._versao = versao
        self._installed = False
        self.setObjectName(f"FirebirdAutoInstallCard_{versao}")
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        self.title = label(FB_PORTABLE_CONFIGS[versao]["label"], COLORS["text"], 12, bold=True)
        self.desc = label("Instalação e configuração completa em um clique.", COLORS["text_dim"], 9)
        self.desc.setWordWrap(True)

        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(6)
        self.pbar.setTextVisible(False)
        self.pbar.setVisible(False)

        self.status_lbl = label("", COLORS["accent"], 9)
        self.status_lbl.setVisible(False)

        self.btn = make_primary_btn("INSTALAÇÃO AUTOMÁTICA", 180)
        self.btn.clicked.connect(lambda: self.acao_solicitada.emit(self._versao))

        lay.addWidget(self.title)
        lay.addWidget(self.desc)
        lay.addStretch()
        lay.addWidget(self.status_lbl)
        lay.addWidget(self.pbar)
        lay.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignCenter)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode=""):
        acc = COR_VERSAOT[self._versao]
        self.setStyleSheet(f"""
            QFrame#FirebirdAutoInstallCard_{self._versao} {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
            QFrame#FirebirdAutoInstallCard_{self._versao}:hover {{
                border-color: {acc};
            }}
            QProgressBar {{ background: {COLORS['border']}; border: none; border-radius: 3px; }}
            QProgressBar::chunk {{ background: {acc}; border-radius: 3px; }}
        """)

    def set_loading(self, v: bool, msg: str = "", pct: int = 0):
        self.btn.setEnabled(not v)
        self.pbar.setVisible(v)
        self.status_lbl.setVisible(v)
        if v:
            self.status_lbl.setText(msg)
            self.pbar.setValue(pct)

    def set_installed(self, v: bool):
        self._installed = v
        if v:
            self.btn.setText("REINSTALAR")
            self.desc.setText("Firebird já detectado. Você pode reinstalar se necessário.")
        else:
            self.btn.setText("INSTALAÇÃO AUTOMÁTICA")
            self.desc.setText("Instalação e configuração completa em um clique.")

class FirebirdFb4ConfigCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FirebirdFb4ConfigCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        self.title = label("Otimização Firebird 4.0", COLORS["text"], 13, bold=True)
        self.desc = label(
            "Aplica configurações oficiais de performance e segurança para o Firebird 4.\n"
            "Recomendado para servidores de produção.",
            COLORS["text_dim"], 10
        )
        self.desc.setWordWrap(True)

        self.btn = make_primary_btn("APLICAR OTIMIZAÇÕES", 220)
        
        lay.addWidget(self.title)
        lay.addWidget(self.desc)
        lay.addSpacing(10)
        lay.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignLeft)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode=""):
        self.setStyleSheet(f"""
            QFrame#FirebirdFb4ConfigCard {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)

class FirebirdStatusDashboard(QFrame):
    versao_clicada = pyqtSignal(str)
    acao_solicitada = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FirebirdStatusDashboard")
        self.setFixedHeight(110)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(20)

        self.boxes = {}
        for v in ("3", "4"):
            box = QFrame()
            box.setObjectName(f"dash_box_{v}")
            box.setCursor(Qt.CursorShape.PointingHandCursor)
            box.mousePressEvent = lambda e, versao=v: self.versao_clicada.emit(versao)
            
            bl = QVBoxLayout(box)
            bl.setContentsMargins(12, 8, 12, 8)
            
            header = QHBoxLayout()
            title = label(f"FB {v}.0", COR_VERSAOT[v], 10, bold=True)
            self.st_icon = label("🕒", COLORS["text_dim"], 10)
            self.st_text = label("Verificando", COLORS["text_dim"], 8)
            
            header.addWidget(title, 1)
            header.addWidget(self.st_icon)
            header.addWidget(self.st_text)
            bl.addLayout(header)

            actions = QHBoxLayout()
            actions.setSpacing(4)
            btn_start = self._make_mini_btn("Iniciar", v, "iniciar")
            btn_stop = self._make_mini_btn("Parar", v, "parar")
            btn_restart = self._make_mini_btn("Reiniciar", v, "reiniciar")
            
            actions.addWidget(btn_start)
            actions.addWidget(btn_stop)
            actions.addWidget(btn_restart)
            bl.addLayout(actions)
            
            self.boxes[v] = {
                "frame": box, "icon": self.st_icon, "text": self.st_text,
                "start": btn_start, "stop": btn_stop, "restart": btn_restart
            }
            lay.addWidget(box, 1)

        lay.addStretch()
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _make_mini_btn(self, txt, v, acao):
        btn = QPushButton(txt)
        btn.setFixedHeight(22)
        btn.setFont(QFont(FONT_SANS, 8))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.acao_solicitada.emit(v, acao))
        return btn

    def _upd(self, _mode=""):
        self.setStyleSheet(f"QFrame#FirebirdStatusDashboard {{ background: {COLORS['surface']}; border: 1px solid {COLORS['border']}; border-radius: 12px; }}")
        for v in ("3", "4"):
            acc = COR_VERSAOT[v]
            self.boxes[v]["frame"].setStyleSheet(f"""
                QFrame#dash_box_{v} {{
                    background: {COLORS['bg']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 8px;
                }}
                QFrame#dash_box_{v}:hover {{ border-color: {acc}; }}
                QPushButton {{ background: transparent; color: {acc}; border: 1px solid {acc}; border-radius: 4px; }}
                QPushButton:hover {{ background: {acc}; color: #fff; }}
            """)

    def atualizar(self, st: dict):
        for v in ("3", "4"):
            d = st.get(f"fb{v}", {})
            rodando = d.get("rodando", False)
            instalado = d.get("instalado", False)
            
            self.boxes[v]["start"].setVisible(not rodando and instalado)
            self.boxes[v]["stop"].setVisible(rodando)
            self.boxes[v]["restart"].setVisible(rodando)
            
            if rodando:
                self.boxes[v]["text"].setText("ONLINE")
                self.boxes[v]["icon"].setText("🟢")
            elif instalado:
                self.boxes[v]["text"].setText("OFFLINE")
                self.boxes[v]["icon"].setText("⚪")
            else:
                self.boxes[v]["text"].setText("N/A")
                self.boxes[v]["icon"].setText("❌")

class FirebirdDatabaseConfigCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FirebirdDatabaseConfigCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        header = QHBoxLayout()
        icon = label("📁", COLORS["accent"], 14)
        title = label("Configuração de Databases", COLORS["text"], 11, bold=True)
        header.addWidget(icon)
        header.addWidget(title, 1)
        lay.addLayout(header)

        # Controles
        ctrl_lay = QHBoxLayout()
        self.radio_fb3 = QRadioButton("FB 3.0")
        self.radio_fb4 = QRadioButton("FB 4.0")
        self.radio_fb4.setChecked(True)
        
        self.btn_procurar = make_secondary_btn("PROCURAR .FDB", 150)
        self.btn_procurar.setFixedHeight(32)
        
        ctrl_lay.addWidget(label("Versão Alvo:", COLORS["text_dim"], 9))
        ctrl_lay.addWidget(self.radio_fb3)
        ctrl_lay.addWidget(self.radio_fb4)
        ctrl_lay.addStretch()
        ctrl_lay.addWidget(self.btn_procurar)
        lay.addLayout(ctrl_lay)

        self.list = QListWidget()
        self.list.setFixedHeight(150)
        self.list.setFont(QFont(FONT_MONO, 9))
        self.list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QListWidget::item {{ padding: 6px; border-radius: 4px; }}
            QListWidget::item:selected {{ background: {COLORS['accent_dim']}; color: {COLORS['accent']}; }}
        """)
        lay.addWidget(self.list)

        self.btn_aplicar = make_primary_btn("CONFIGURAR AGORA", 200)
        self.btn_aplicar.setFixedHeight(38)
        self.btn_aplicar.setEnabled(False)
        lay.addWidget(self.btn_aplicar, 0, Qt.AlignmentFlag.AlignCenter)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode=""):
        self.setStyleSheet(f"""
            QFrame#FirebirdDatabaseConfigCard {{
                background: {COLORS['surface']};
                border: 1.5px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
