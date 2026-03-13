# =============================================================================
# FUTURA SETUP — Página: Firebird Portable
# FB3 e FB4 totalmente simétricos:
#   - Instalação / Remoção portable
#   - Modo processo ou serviço Windows
#   - Toggle ativar/inativar independente
# Salvar em: ui/page_fb_portable.py
# =============================================================================
from __future__ import annotations

from PyQt6.QtCore    import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui     import QFont, QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QScrollArea, QProgressBar,
    QButtonGroup, QRadioButton, QAbstractButton,
    QPlainTextEdit, QPushButton,
)

from ui.theme         import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets       import (
    PageTitle, SectionHeader, AlertBox,
    make_primary_btn, make_secondary_btn,
    btn_row, spacer, h_line, label,
)
from core.fb_portable import (
    FB_CONFIGS,
    fb_portable_instalado,
    versao_fb_portable,
    status_detalhado,
    is_admin, solicitar_admin,
    ativar_fb, inativar_fb,
    instalar_fb_portable,
    remover_fb_portable,
    fb_obter_modo,
    fb_servico_existe,
    fb_servico_rodando,
    registrar_fb_servico,
    remover_fb_servico,
)

# Cores por versão
_COR = {
    "3": COLORS.get("accent2", "#2ecc71"),
    "4": COLORS.get("accent",  "#0078d4"),
}


# =============================================================================
# Toggle Switch
# =============================================================================

class _ToggleSwitch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(52, 28)

    def setAtivo(self, v: bool):
        self.setEnabled(v)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        checked  = self.isChecked()
        disabled = not self.isEnabled()
        if disabled:
            track = QColor("#555"); thumb = QColor("#888")
        elif checked:
            track = QColor(COLORS.get("accent", "#0078d4")); thumb = QColor("#fff")
        else:
            track = QColor(COLORS.get("border", "#444")); thumb = QColor("#ccc")
        path = QPainterPath()
        path.addRoundedRect(0, 4, 52, 20, 10, 10)
        p.fillPath(path, track)
        p.setBrush(thumb)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(30 if checked else 4, 4, 20, 20)
        p.end()

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(52, 28)


# =============================================================================
# Workers
# =============================================================================

class _AtivarWorker(QThread):
    log       = pyqtSignal(str)
    concluido = pyqtSignal(dict)

    def __init__(self, versao: str, ativar: bool, parent=None):
        super().__init__(parent)
        self.versao = versao
        self.ativar = ativar

    def run(self):
        fn = ativar_fb if self.ativar else inativar_fb
        r  = fn(self.versao, self.log.emit)
        r["versao"] = self.versao
        r["ativar"] = self.ativar
        self.concluido.emit(r)


class _InstalarWorker(QThread):
    log       = pyqtSignal(str)
    progresso = pyqtSignal(int)
    concluido = pyqtSignal(dict)

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self.versao = versao

    def run(self):
        self.concluido.emit(
            instalar_fb_portable(self.versao, self.log.emit, self.progresso.emit)
        )


class _RemoverWorker(QThread):
    log       = pyqtSignal(str)
    concluido = pyqtSignal(dict)

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self.versao = versao

    def run(self):
        self.concluido.emit(remover_fb_portable(self.versao, self.log.emit))


class _ServicoWorker(QThread):
    """Worker para registrar ou remover o serviço Windows de qualquer versão."""
    log       = pyqtSignal(str)
    concluido = pyqtSignal(dict)

    def __init__(self, versao: str, acao: str, parent=None):
        super().__init__(parent)
        self.versao = versao
        self.acao   = acao   # 'registrar' | 'remover'

    def run(self):
        if self.acao == "registrar":
            r = registrar_fb_servico(self.versao, self.log.emit)
        else:
            r = remover_fb_servico(self.versao, self.log.emit)
        r["versao"] = self.versao
        r["acao"]   = self.acao
        self.concluido.emit(r)


# =============================================================================
# Card de modo de execução — reutilizável para FB3 e FB4
# =============================================================================

class _ModoCard(QFrame):
    """Card com info do modo (processo / serviço) e botão de ação."""
    acao_solicitada = pyqtSignal(str, str)   # (versao, 'registrar'|'remover')

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self._versao         = versao
        self._svc_registrado = False
        self.setObjectName(f"modo_card_{versao}")
        self._build_ui()
        self._upd_style()
        theme_manager.theme_changed.connect(lambda _: self._upd_style())

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        titulo = QLabel("Modo de execução")
        titulo.setFont(QFont(FONT_SANS, 10, QFont.Weight.Bold))
        titulo.setStyleSheet(
            f"color:{COLORS.get('text','#fff')}; background:transparent; border:none;"
        )
        lay.addWidget(titulo)

        # Linha de status
        row = QHBoxLayout()
        row.setSpacing(8)
        self._dot = QWidget()
        self._dot.setFixedSize(8, 8)
        self._lbl_modo = QLabel()
        self._lbl_modo.setFont(QFont(FONT_MONO, 9))
        self._lbl_modo.setStyleSheet(
            f"color:{COLORS.get('text_mid','#aaa')}; background:transparent; border:none;"
        )
        self._badge = QLabel()
        self._badge.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self._badge.setFixedWidth(72)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._dot)
        row.addWidget(self._lbl_modo, 1)
        row.addWidget(self._badge)
        lay.addLayout(row)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color:{COLORS.get('border','#444')};")
        lay.addWidget(div)

        desc_row = QHBoxLayout()
        desc_row.setSpacing(12)
        self._lbl_desc = QLabel()
        self._lbl_desc.setFont(QFont(FONT_SANS, 9))
        self._lbl_desc.setWordWrap(True)
        self._lbl_desc.setStyleSheet(
            f"color:{COLORS.get('text_dim','#888')}; background:transparent; border:none;"
        )
        self._btn_acao = QPushButton()
        self._btn_acao.setFixedHeight(28)
        self._btn_acao.setFont(QFont(FONT_SANS, 9))
        self._btn_acao.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_acao.clicked.connect(self._on_btn)
        desc_row.addWidget(self._lbl_desc, 1)
        desc_row.addWidget(self._btn_acao)
        lay.addLayout(desc_row)

        self._lbl_nota = QLabel("⚠  Requer privilégios de administrador")
        self._lbl_nota.setFont(QFont(FONT_SANS, 8))
        self._lbl_nota.setStyleSheet(
            "color:#e67e22; background:transparent; border:none;"
        )
        lay.addWidget(self._lbl_nota)

    def atualizar(self, instalado: bool, modo: str, svc_registrado: bool, svc_rodando: bool):
        self._svc_registrado = svc_registrado
        self.setEnabled(instalado)
        cor = _COR[self._versao]
        v   = self._versao

        if not instalado:
            self._lbl_modo.setText(f"FB{v} não instalado")
            self._badge.setText("—")
            self._lbl_desc.setText("Instale o portable para acessar esta opção.")
            self._btn_acao.setEnabled(False)
            self._dot.setStyleSheet(
                f"background:{COLORS.get('text_dim','#888')}; border-radius:4px;"
            )
            return

        self._btn_acao.setEnabled(True)

        if modo == "servico" and svc_registrado:
            self._dot.setStyleSheet(f"background:{cor}; border-radius:4px;")
            estado = "RUNNING" if svc_rodando else "PARADO"
            self._lbl_modo.setText(
                f"Serviço Windows  •  FuturaFirebirdFB{v}  •  {estado}"
            )
            self._badge.setText("SERVIÇO")
            self._badge.setStyleSheet(f"""
                QLabel {{
                    background:{cor}; color:#fff;
                    border-radius:4px; padding:1px 4px; font-weight:bold;
                }}
            """)
            self._lbl_desc.setText(
                f"O FB{v} está registrado como serviço Windows (start=auto). "
                "Inicia automaticamente com o Windows, independente do Futura Setup."
            )
            self._btn_acao.setText("Remover Serviço Windows")
            self._btn_acao.setStyleSheet(self._style_danger())
        else:
            self._dot.setStyleSheet(
                f"background:{COLORS.get('text_dim','#888')}; border-radius:4px;"
            )
            self._lbl_modo.setText(f"Processo portable  •  inicia com o Futura Setup")
            self._badge.setText("PROCESSO")
            self._badge.setStyleSheet(f"""
                QLabel {{
                    background:{COLORS.get('surface','#2a2a2a')};
                    color:{COLORS.get('text_mid','#aaa')};
                    border:1px solid {COLORS.get('border','#444')};
                    border-radius:4px; padding:1px 4px; font-weight:bold;
                }}
            """)
            self._lbl_desc.setText(
                f"O FB{v} roda como processo portable — só fica ativo enquanto o "
                "Futura Setup estiver aberto. Registre como serviço para iniciar "
                "automaticamente com o Windows."
            )
            self._btn_acao.setText("Registrar como Serviço Windows")
            self._btn_acao.setStyleSheet(self._style_primary())

        self._lbl_nota.setVisible(not is_admin())

    def _on_btn(self):
        acao = "remover" if self._svc_registrado else "registrar"
        self.acao_solicitada.emit(self._versao, acao)

    def set_ocupado(self, v: bool):
        self._btn_acao.setEnabled(not v)

    def _style_primary(self) -> str:
        acc = _COR[self._versao]
        return f"""
            QPushButton {{
                background:{acc}; color:#fff; border:none;
                border-radius:5px; padding:4px 12px; font-weight:bold;
            }}
            QPushButton:hover {{ opacity: 0.85; }}
            QPushButton:disabled {{ background:{COLORS.get('border','#444')}; color:#888; }}
        """

    def _style_danger(self) -> str:
        return """
            QPushButton {
                background:#c0392b; color:#fff; border:none;
                border-radius:5px; padding:4px 12px; font-weight:bold;
            }
            QPushButton:hover { background:#e74c3c; }
            QPushButton:disabled { background:#555; color:#888; }
        """

    def _upd_style(self, _=""):
        self.setStyleSheet(f"""
            QFrame#modo_card_{self._versao} {{
                background:{COLORS.get('bg','#121212')};
                border:1px solid {COLORS.get('border','#444')};
                border-radius:8px;
            }}
        """)


# =============================================================================
# Linha de toggle por versão
# =============================================================================

class _ToggleRow(QWidget):
    def __init__(self, versao: str, detalhe: str, parent=None):
        super().__init__(parent)
        self._versao = versao
        self._cor    = _COR[versao]

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        self._dot = QWidget()
        self._dot.setFixedSize(10, 10)
        self._dot.setStyleSheet(
            f"background:{COLORS.get('text_dim','#888')}; border-radius:5px;"
        )

        col = QVBoxLayout()
        col.setSpacing(2)

        self._lbl_titulo = QLabel(FB_CONFIGS[versao]["label"])
        self._lbl_titulo.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        self._lbl_titulo.setStyleSheet(
            f"color:{COLORS.get('text','#fff')}; background:transparent; border:none;"
        )
        self._lbl_detalhe = QLabel(detalhe)
        self._lbl_detalhe.setFont(QFont(FONT_MONO, 9))
        self._lbl_detalhe.setStyleSheet(
            f"color:{COLORS.get('text_dim','#888')}; background:transparent; border:none;"
        )
        col.addWidget(self._lbl_titulo)
        col.addWidget(self._lbl_detalhe)

        self._badge = QLabel("INATIVO")
        self._badge.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self._badge.setFixedWidth(64)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_badge(False)

        self.toggle = _ToggleSwitch()

        lay.addWidget(self._dot)
        lay.addLayout(col, 1)
        lay.addWidget(self._badge)
        lay.addWidget(self.toggle)

    def set_estado(self, ativo: bool, instalado: bool, detalhe: str = ""):
        cor = self._cor if ativo else COLORS.get("text_dim", "#888")
        self._dot.setStyleSheet(f"background:{cor}; border-radius:5px;")
        self._lbl_titulo.setStyleSheet(
            f"color:{COLORS.get('text','#fff')}; background:transparent; border:none;"
        )
        if not instalado:
            self._lbl_detalhe.setText("Não instalado — use o painel abaixo para instalar")
        elif detalhe:
            self._lbl_detalhe.setText(detalhe)
        self._set_badge(ativo)

    def _set_badge(self, ativo: bool):
        if ativo:
            self._badge.setText("ATIVO")
            self._badge.setStyleSheet(f"""
                QLabel {{
                    background:{self._cor}; color:#fff;
                    border-radius:4px; padding:2px 6px; font-weight:bold;
                }}
            """)
        else:
            self._badge.setText("INATIVO")
            self._badge.setStyleSheet(f"""
                QLabel {{
                    background:{COLORS.get('surface','#2a2a2a')};
                    color:{COLORS.get('text_dim','#888')};
                    border:1px solid {COLORS.get('border','#444')};
                    border-radius:4px; padding:2px 6px; font-weight:bold;
                }}
            """)


# =============================================================================
# Card de status de instalação
# =============================================================================

class _StatusCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("status_card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)

        self._dot = QWidget()
        self._dot.setFixedSize(10, 10)
        col = QVBoxLayout()
        col.setSpacing(2)
        self._lbl_status  = QLabel()
        self._lbl_status.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
        self._lbl_detalhe = QLabel()
        self._lbl_detalhe.setFont(QFont(FONT_MONO, 9))
        col.addWidget(self._lbl_status)
        col.addWidget(self._lbl_detalhe)
        lay.addWidget(self._dot)
        lay.addLayout(col, 1)

        self._data = (False, "", "", "")
        self.atualizar(False, "", "", "")
        theme_manager.theme_changed.connect(
            lambda _: self.atualizar(*self._data)
        )

    def atualizar(self, instalado: bool, ver_str: str, fb_dir: str, label_v: str):
        self._data = (instalado, ver_str, fb_dir, label_v)
        cor = COLORS.get("accent2", "#2ecc71") if instalado else COLORS.get("text_dim", "#888")
        self._dot.setStyleSheet(f"background:{cor}; border-radius:5px;")
        if instalado:
            self._lbl_status.setText(f"{label_v} instalado")
            self._lbl_detalhe.setText(
                f"{ver_str}   |   {fb_dir}" if fb_dir else ver_str
            )
        else:
            self._lbl_status.setText(f"{label_v} não instalado")
            self._lbl_detalhe.setText(f"Será instalado em: {fb_dir}" if fb_dir else "")
        self._lbl_status.setStyleSheet(
            f"color:{cor}; background:transparent; border:none;"
        )
        self._lbl_detalhe.setStyleSheet(
            f"color:{COLORS.get('text_dim','#888')}; background:transparent; border:none;"
        )
        self.setStyleSheet(f"""
            QFrame#status_card {{
                background:{COLORS.get('surface','#1e1e1e')};
                border:1.5px solid {COLORS.get('border','#444')};
                border-radius:8px;
            }}
        """)


# =============================================================================
# Console de log
# =============================================================================

class _Console(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("console")
        self.setFixedHeight(200)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        bar = QWidget()
        bar_lay = QHBoxLayout(bar)
        bar_lay.setContentsMargins(10, 4, 6, 4)
        bar_lay.setSpacing(0)
        lbl = QLabel("Log")
        lbl.setFont(QFont(FONT_SANS, 8))
        lbl.setStyleSheet(
            f"color:{COLORS.get('text_dim','#888')}; background:transparent; border:none;"
        )
        self._btn_copiar = QPushButton("Copiar tudo")
        self._btn_copiar.setFixedHeight(20)
        self._btn_copiar.setFont(QFont(FONT_SANS, 8))
        self._btn_copiar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_copiar.clicked.connect(self._copiar)
        bar_lay.addWidget(lbl)
        bar_lay.addStretch()
        bar_lay.addWidget(self._btn_copiar)
        lay.addWidget(bar)

        self._texto = QPlainTextEdit()
        self._texto.setReadOnly(True)
        self._texto.setFont(QFont(FONT_MONO, 9))
        self._texto.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._texto.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        lay.addWidget(self._texto)

        self._upd_style()
        theme_manager.theme_changed.connect(self._upd_style)

    def append(self, txt: str):
        self._texto.appendPlainText(txt)
        sb = self._texto.verticalScrollBar()
        sb.setValue(sb.maximum())

    def limpar(self):
        self._texto.clear()

    def _copiar(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._texto.toPlainText())
        self._btn_copiar.setText("Copiado!")
        QTimer.singleShot(2000, lambda: self._btn_copiar.setText("Copiar tudo"))

    def _upd_style(self, _=""):
        bg = COLORS.get("bg", "#121212"); brd = COLORS.get("border", "#444")
        txt = COLORS.get("text_mid", "#aaa"); surf = COLORS.get("surface", "#1e1e1e")
        acc = COLORS.get("accent", "#0078d4")
        self.setStyleSheet(f"""
            QFrame#console {{ background:{bg}; border:1px solid {brd}; border-radius:6px; }}
        """)
        self._texto.setStyleSheet(f"""
            QPlainTextEdit {{
                background:{bg}; color:{txt}; border:none;
                border-bottom-left-radius:6px; border-bottom-right-radius:6px;
                padding:6px 10px; selection-background-color:{acc};
            }}
            QScrollBar:vertical {{ background:{surf}; width:8px; border-radius:4px; }}
            QScrollBar::handle:vertical {{ background:{brd}; border-radius:4px; min-height:20px; }}
        """)
        self._btn_copiar.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{acc}; border:none; padding:0 4px; }}
            QPushButton:hover {{ color:{txt}; }}
        """)


# =============================================================================
# Banner admin
# =============================================================================

class _BannerAdmin(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("banner_admin")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        ico = QLabel("⚠")
        ico.setFont(QFont(FONT_SANS, 14))
        ico.setStyleSheet("color:#e67e22; background:transparent; border:none;")
        ico.setFixedWidth(24)

        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel("Permissão de administrador necessária")
        t.setFont(QFont(FONT_SANS, 10, QFont.Weight.Bold))
        t.setStyleSheet("color:#e67e22; background:transparent; border:none;")
        s = QLabel(
            "Gerenciar serviços Windows exige privilégios elevados. "
            "Reinicie o Futura Setup como Administrador."
        )
        s.setFont(QFont(FONT_SANS, 9))
        s.setWordWrap(True)
        s.setStyleSheet(
            f"color:{COLORS.get('text_mid','#aaa')}; background:transparent; border:none;"
        )
        col.addWidget(t); col.addWidget(s)

        self.btn_reiniciar = make_primary_btn("Reiniciar como Admin", 160)
        self.btn_reiniciar.setFixedHeight(30)

        lay.addWidget(ico)
        lay.addLayout(col, 1)
        lay.addWidget(self.btn_reiniciar)

        self.setStyleSheet("""
            QFrame#banner_admin {
                background:rgba(230,126,34,0.12);
                border:1.5px solid #e67e22;
                border-radius:8px;
            }
        """)


# =============================================================================
# Página principal
# =============================================================================

class PageFbPortable(QWidget):
    go_menu = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: QThread | None = None
        self._versao_sel   = "4"
        self._upd_toggle   = False   # bloqueia sinal durante atualização
        self._toggle_rows  : dict[str, _ToggleRow]  = {}
        self._modo_cards   : dict[str, _ModoCard]   = {}
        self._build_ui()
        theme_manager.theme_changed.connect(self._upd_style)

        self._timer = QTimer(self)
        self._timer.setInterval(4000)
        self._timer.timeout.connect(self._atualizar_status)
        self._timer.start()

    # =========================================================================
    # Construção da UI
    # =========================================================================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        lay   = QVBoxLayout(inner)
        lay.setContentsMargins(40, 36, 40, 20)
        lay.setSpacing(10)

        lay.addWidget(PageTitle(
            "FIREBIRD PORTABLE",
            "Instale, ative e configure FB3 e FB4 de forma independente"
        ))

        # Banner admin
        if not is_admin():
            self._banner_admin = _BannerAdmin()
            self._banner_admin.btn_reiniciar.clicked.connect(self._on_reiniciar_admin)
            lay.addWidget(self._banner_admin)
        else:
            self._banner_admin = None

        # Info
        lay.addWidget(SectionHeader("Como funciona"))
        info = label(
            "Ambas as versões podem ser instaladas como portable e rodar como "
            "processo (ativo apenas com o Futura Setup aberto) ou como serviço "
            "Windows (start=auto, inicia com o Windows). "
            "FB3 usa a porta 3050, FB4 usa a porta 3051.",
            COLORS["text_mid"], 11,
        )
        info.setWordWrap(True)
        lay.addWidget(info)
        lay.addWidget(spacer(h=8))

        # ── TOGGLES ───────────────────────────────────────────────────────
        lay.addWidget(SectionHeader("Controle de versões"))

        tf = QFrame()
        tf.setObjectName("toggles_frame")
        tlay = QVBoxLayout(tf)
        tlay.setContentsMargins(20, 16, 20, 16)
        tlay.setSpacing(16)

        for i, versao in enumerate(("3", "4")):
            cfg     = FB_CONFIGS[versao]
            detalhe = f"Processo portable  •  porta {cfg['porta']}"
            row     = _ToggleRow(versao, detalhe)
            row.toggle.toggled.connect(
                lambda checked, v=versao: self._on_toggle(v, checked)
            )
            self._toggle_rows[versao] = row
            tlay.addWidget(row)

            card = _ModoCard(versao)
            card.acao_solicitada.connect(self._on_servico_acao)
            self._modo_cards[versao] = card
            tlay.addWidget(card)

            if i == 0:
                div = QFrame()
                div.setFrameShape(QFrame.Shape.HLine)
                div.setStyleSheet(f"color:{COLORS.get('border','#444')};")
                tlay.addWidget(div)

        lay.addWidget(tf)
        lay.addWidget(spacer(h=6))
        lay.addWidget(h_line())

        # ── INSTALAÇÃO / REMOÇÃO ──────────────────────────────────────────
        lay.addWidget(SectionHeader("Instalar / Remover Portable"))

        nota = label(
            "Selecione a versão e use os botões para instalar ou remover o portable.",
            COLORS["text_dim"], 9,
        )
        nota.setWordWrap(True)
        lay.addWidget(nota)
        lay.addWidget(spacer(h=4))

        self._radio_group = QButtonGroup(self)
        radio_row = QHBoxLayout()
        radio_row.setSpacing(20)
        for ver, cfg in FB_CONFIGS.items():
            rb = QRadioButton(cfg["label"])
            rb.setFont(QFont(FONT_SANS, 11))
            rb.setChecked(ver == "4")
            rb.toggled.connect(
                lambda checked, v=ver: self._on_versao_changed(v) if checked else None
            )
            self._radio_group.addButton(rb)
            radio_row.addWidget(rb)
        radio_row.addStretch()
        lay.addLayout(radio_row)

        self._lbl_porta = label("", COLORS["text_dim"], 9)
        lay.addWidget(self._lbl_porta)
        lay.addWidget(spacer(h=4))

        self._card_status = _StatusCard()
        lay.addWidget(self._card_status)
        lay.addWidget(spacer(h=6))

        self._btn_instalar = make_primary_btn("INSTALAR", 160)
        self._btn_instalar.clicked.connect(self._on_instalar)
        self._btn_remover  = make_secondary_btn("REMOVER", 100)
        self._btn_remover.clicked.connect(self._on_remover)
        btn_voltar = make_secondary_btn("VOLTAR", 80)
        btn_voltar.clicked.connect(self.go_menu.emit)
        lay.addWidget(btn_row(self._btn_instalar, self._btn_remover, btn_voltar))

        # Progresso / Alert / Console
        lay.addWidget(spacer(h=6))
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(8)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        lay.addWidget(self._progress)

        self._alert = AlertBox("", "info")
        self._alert.setVisible(False)
        lay.addWidget(self._alert)

        self._console = _Console()
        lay.addWidget(self._console)

        lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

        self._upd_style()
        self._on_versao_changed("4")
        self._atualizar_status()

    # =========================================================================
    # Toggles
    # =========================================================================

    def _on_toggle(self, versao: str, checked: bool):
        if self._upd_toggle:
            return
        acao = "Ativando" if checked else "Inativando"
        self._setar_ocupado(True)
        self._console.limpar()
        self._alert.setVisible(False)
        self._console.append(f"{acao} {FB_CONFIGS[versao]['label']} ...")

        worker = _AtivarWorker(versao, checked)
        worker.log.connect(self._console.append)
        worker.concluido.connect(self._on_toggle_concluido)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_toggle_concluido(self, r: dict):
        self._setar_ocupado(False)
        self._atualizar_status()
        versao = r.get("versao", "")
        ativar = r.get("ativar", True)
        lbl    = FB_CONFIGS.get(versao, {}).get("label", f"FB{versao}")
        acao   = "ativado" if ativar else "inativado"
        if r.get("requer_admin"):
            self._alerta("Permissao de administrador necessaria. Use o botão 'Reiniciar como Admin'.", "warn")
        elif r["ok"]:
            self._alerta(f"{lbl} {acao} com sucesso!", "success")
        else:
            self._alerta(f"Erro: {r['erro']}", "error")

    def _on_reiniciar_admin(self):
        if solicitar_admin():
            from PyQt6.QtWidgets import QApplication
            QApplication.quit()
        else:
            self._alerta(
                "Não foi possível solicitar permissão. "
                "Clique direito no atalho e escolha 'Executar como administrador'.",
                "error"
            )

    # =========================================================================
    # Card de modo — registrar / remover serviço
    # =========================================================================

    def _on_servico_acao(self, versao: str, acao: str):
        if not is_admin():
            self._alerta(
                "Permissao de administrador necessaria. Reinicie como Administrador.", "warn"
            )
            return
        label_acao = "Registrando" if acao == "registrar" else "Removendo"
        self._setar_ocupado(True)
        self._console.limpar()
        self._alert.setVisible(False)
        self._console.append(
            f"{label_acao} servico Windows do {FB_CONFIGS[versao]['label']} ..."
        )
        worker = _ServicoWorker(versao, acao)
        worker.log.connect(self._console.append)
        worker.concluido.connect(self._on_servico_concluido)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_servico_concluido(self, r: dict):
        self._setar_ocupado(False)
        self._atualizar_status()
        versao = r.get("versao", "")
        acao   = r.get("acao", "")
        lbl    = FB_CONFIGS.get(versao, {}).get("label", f"FB{versao}")
        if r.get("requer_admin"):
            self._alerta("Permissao de administrador necessaria. Reinicie como Administrador.", "warn")
        elif r["ok"]:
            if acao == "registrar":
                self._alerta(
                    f"{lbl} registrado como serviço Windows! Inicia automaticamente com o Windows.",
                    "success"
                )
            else:
                self._alerta(f"Serviço Windows do {lbl} removido. Voltou ao modo processo.", "success")
        else:
            self._alerta(f"Erro: {r['erro']}", "error")

    # =========================================================================
    # Status geral (timer + pós-ações)
    # =========================================================================

    def _atualizar_status(self):
        if self._worker and self._worker.isRunning():
            return

        st = status_detalhado()
        self._upd_toggle = True

        for versao in ("3", "4"):
            d        = st[f"fb{versao}"]
            inst     = d["instalado"]
            # Toggle e badge refletem se está EFETIVAMENTE RODANDO,
            # não apenas registrado/habilitado.
            rodando  = d["rodando"]
            row      = self._toggle_rows[versao]
            card     = self._modo_cards[versao]

            row.toggle.setAtivo(inst)
            row.toggle.setChecked(rodando)

            porta = FB_CONFIGS[versao]['porta']
            if d["servico_rod"]:
                det = f"Serviço Windows  •  porta {porta}  •  rodando"
            elif d["processo_rod"]:
                det = f"Processo portable  •  porta {porta}  •  rodando"
            elif inst and d["modo"] == "servico" and d["servico_reg"]:
                det = f"Serviço Windows  •  porta {porta}  •  parado"
            elif inst:
                det = f"Processo portable  •  porta {porta}  •  parado"
            else:
                det = f"Processo portable  •  porta {porta}"

            # Informar sobre serviço oficial do FB3
            if versao == "3" and d.get("servico_oficial_rod"):
                det = f"Serviço oficial  •  porta {porta}  •  rodando"

            row.set_estado(rodando, inst, det)
            card.atualizar(
                instalado      = inst,
                modo           = d["modo"],
                svc_registrado = d["servico_reg"],
                svc_rodando    = d["servico_rod"],
            )

        self._upd_toggle = False

        if st["conflito"]:
            self._alerta(
                "FB3 e FB4 estão ativos simultaneamente — isso pode causar conflitos.", "warn"
            )

        self._atualizar_card_status()

    # =========================================================================
    # Instalação / Remoção
    # =========================================================================

    def _on_versao_changed(self, versao: str):
        self._versao_sel = versao
        cfg = FB_CONFIGS[versao]
        self._lbl_porta.setText(
            f"Porta: {cfg['porta']}  |  Diretório: {cfg['dir']}"
        )
        self._alert.setVisible(False)
        self._atualizar_card_status()

    def _on_instalar(self):
        versao = self._versao_sel
        cfg    = FB_CONFIGS[versao]

        if fb_portable_instalado(versao):
            self._alerta(f"{cfg['label']} já está instalado em {cfg['dir']}.", "info")
            return

        self._setar_ocupado(True)
        self._console.limpar()
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._alert.setVisible(False)

        worker = _InstalarWorker(versao)
        worker.log.connect(self._console.append)
        worker.progresso.connect(self._progress.setValue)
        worker.concluido.connect(self._on_instalado)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_instalado(self, r: dict):
        self._setar_ocupado(False)
        self._progress.setVisible(False)
        self._atualizar_status()
        cfg = FB_CONFIGS[self._versao_sel]
        if r["ok"]:
            self._alerta(f"{cfg['label']} instalado! Versão: {r['versao']}", "success")
        else:
            self._alerta(f"Erro na instalação: {r['erro']}", "error")

    def _on_remover(self):
        versao = self._versao_sel
        cfg    = FB_CONFIGS[versao]

        if not fb_portable_instalado(versao):
            self._alerta(f"{cfg['label']} não está instalado.", "warn")
            return

        self._setar_ocupado(True)
        self._console.limpar()
        self._alert.setVisible(False)

        worker = _RemoverWorker(versao)
        worker.log.connect(self._console.append)
        worker.concluido.connect(self._on_removido)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_removido(self, r: dict):
        self._setar_ocupado(False)
        self._atualizar_status()
        cfg = FB_CONFIGS[self._versao_sel]
        if r["ok"]:
            self._alerta(f"{cfg['label']} removido.", "success")
        else:
            self._alerta(f"Erro ao remover: {r['erro']}", "error")

    def _limpar_worker(self, worker):
        if self._worker is worker:
            self._worker = None

    # =========================================================================
    # Helpers
    # =========================================================================

    def _setar_ocupado(self, v: bool):
        self._btn_instalar.setEnabled(not v)
        self._btn_remover.setEnabled(not v)
        for row in self._toggle_rows.values():
            row.toggle.setEnabled(not v)
        for card in self._modo_cards.values():
            card.set_ocupado(v)
        for btn in self._radio_group.buttons():
            btn.setEnabled(not v)

    def _atualizar_card_status(self):
        versao    = self._versao_sel
        instalado = fb_portable_instalado(versao)
        ver_str   = versao_fb_portable(versao) if instalado else ""
        cfg       = FB_CONFIGS[versao]

        self._card_status.atualizar(instalado, ver_str, cfg["dir"], cfg["label"])
        self._btn_instalar.setEnabled(not instalado)
        self._btn_remover.setEnabled(instalado)

    def _alerta(self, txt: str, kind: str):
        self._alert.set_text(txt)
        self._alert.set_kind(kind)
        self._alert.setVisible(True)

    def _upd_style(self, _=""):
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background:{COLORS.get('surface','#1e1e1e')};
                border:none; border-radius:4px;
            }}
            QProgressBar::chunk {{
                background:{COLORS.get('accent','#0078d4')};
                border-radius:4px;
            }}
        """)
        bg  = COLORS.get("surface", "#1e1e1e")
        brd = COLORS.get("border",  "#444")
        try:
            self.findChild(QFrame, "toggles_frame").setStyleSheet(f"""
                QFrame#toggles_frame {{
                    background:{bg};
                    border:1.5px solid {brd};
                    border-radius:10px;
                }}
            """)
        except Exception:
            pass
        for btn in self._radio_group.buttons():
            btn.setStyleSheet(
                f"color:{COLORS.get('text','#fff')}; background:transparent;"
            )

    def reset(self):
        self._alert.setVisible(False)
        self._progress.setVisible(False)
        self._console.limpar()
        self._atualizar_status()

    def showEvent(self, event):
        self._timer.start()
        self._atualizar_status()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)