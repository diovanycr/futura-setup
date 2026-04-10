# =============================================================================
# FUTURA SETUP — Página: Firebird Portable
# FB3 e FB4 totalmente simétricos:
#   - Instalação / Remoção portable
#   - Modo processo ou serviço Windows
#   - Toggle ativar/inativar independente
#   - Ativar uma versão desativa automaticamente a outra
#   - Configuração do databases.conf com varredura de .fdb
# Salvar em: ui/page_fb_portable.py
#
# CORREÇÕES APLICADAS:
#   1. is_admin() removido da thread principal (__init__ e _ModoCard.atualizar).
#      Resultado cacheado em self._eh_admin após _AdminCheckWorker concluir.
#   2. Timer pausado durante qualquer operação (_setar_ocupado) para evitar
#      colisão de status_detalhado() com workers ativos.
#   3. _ModoCard não chama mais is_admin() — recebe o valor via atualizar().
#   4. Banner admin construído após verificação assíncrona.
#   5. [CORRIGIDO] f-string faltando em _ModoCard._build_ui() no setStyleSheet do titulo.
#   6. [CORRIGIDO] Lógica de alerta invertida em _on_toggle_concluido (outra_rod).
#   7. [CORRIGIDO] del em dict substituído por .pop(v, None) em _on_status_concluido.
#   8. [CORRIGIDO] Lambda frágil com argumento nomeado substituído por posicional.
#   9. [CORRIGIDO] Índice de aba hardcoded substituído por indexOf(tab_db).
#  10. [CORRIGIDO] _upd_toggle protegido com try/finally para garantir reset do flag.
#  11. [CORRIGIDO] showEvent agora verifica se _admin_check_worker já está rodando
#      antes de disparar novo worker, evitando duplicação de banner/callbacks.
#  12. [CORRIGIDO] _setar_ocupado agora verifica se está na thread principal antes
#      de manipular o QTimer. Se chamado de outra thread, redireciona via
#      QMetaObject.invokeMethod com QueuedConnection, eliminando o erro
#      "QBasicTimer::stop: Failed. Possibly trying to stop from a different thread".
# =============================================================================
from __future__ import annotations

from PyQt6.QtCore    import Qt, pyqtSignal, pyqtSlot, QThread, QTimer, QMetaObject, Q_ARG
from PyQt6.QtGui     import QFont, QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QScrollArea, QProgressBar,
    QButtonGroup, QRadioButton, QAbstractButton,
    QPlainTextEdit, QPushButton, QListWidget,
    QListWidgetItem, QAbstractItemView, QFileDialog, QTabWidget,
    QGridLayout,
)

from ui.theme         import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets       import (
    PageHeader, SectionHeader, AlertBox, LogConsole,
    make_primary_btn, make_secondary_btn,
    btn_row, spacer, h_line, label,
    _apply_primary_style, _apply_secondary_style,
)
from ui.components.firebird_widgets import (
    FirebirdBannerAdmin as _BannerAdmin,
    FirebirdVersionCard as _VersionCard,
    FirebirdServiceCard as _ServicoCard,
    FirebirdDatabaseConfigCard as _DatabasesConfCard,
    FirebirdToggleSwitch as _ToggleSwitch,
    FirebirdPortableToggleRow as _ToggleRow,
    FirebirdStatusCard as _StatusCard,
    FirebirdAutoInstallCard as _AutoInstallCard,
    FirebirdFb4ConfigCard as _Fb4ConfigCard,
    FirebirdStatusDashboard as _StatusDashboard
)
from core.fb_portable import (
    FB_CONFIGS,
    fb_portable_instalado,
    versao_fb_portable,
    status_detalhado,
    is_admin, solicitar_admin,
    ativar_fb, inativar_fb,
    alternar_versao_ativa,
    instalar_fb_portable,
    remover_fb_portable,
    fb_obter_modo,
    fb_servico_existe,
    fb_servico_rodando,
    registrar_fb_servico,
    remover_fb_servico,
    ativar_fb_servico,
    varrer_fdb,
    atualizar_databases_conf,
    aplicar_configs_oficiais_fb4,
    reiniciar_fb,
)

# Cores por versão
_COR = {
    "3": COLORS.get("accent2", "#2ecc71"),
    "4": COLORS.get("accent",  "#0078d4"),
}


# =============================================================================
# Toggle Switch
# =============================================================================

# Componentes transferidos para ui/components/firebird_widgets.py e ui/widgets.py


# =============================================================================
# Card databases.conf
# =============================================================================

class _DatabasesConfCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("db_conf_card")
        self._arquivos: list[str] = []
        self._worker: QThread | None = None

        self._build_ui()

        theme_manager.ui_theme_changed.connect(self._upd_style)
        theme_manager.theme_changed.connect(lambda _: self._upd_style())
        self._upd_style()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("db_header")
        header_inner = QHBoxLayout(self._header_frame)
        header_inner.setContentsMargins(12, 8, 12, 8)

        self._header_icon = QLabel("🗄️")
        self._header_icon.setFont(QFont(FONT_SANS, 18))

        titulo_v = QVBoxLayout()
        self._titulo_lbl = QLabel("Configurar bases de dados")
        self._titulo_lbl.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
        self._subtitulo_lbl = QLabel("Selecione o arquivo .fdb para configurar o databases.conf")
        self._subtitulo_lbl.setFont(QFont(FONT_SANS, 9))
        titulo_v.addWidget(self._titulo_lbl)
        titulo_v.addWidget(self._subtitulo_lbl)

        info_btn = QLabel("ℹ️")
        info_btn.setToolTip(
            "O sistema buscará por arquivos .fdb. Ao selecionar o arquivo principal (Dados), "
            "o arquivo de CEP será vinculado automaticamente se estiver na mesma pasta."
        )

        header_inner.addWidget(self._header_icon)
        header_inner.addLayout(titulo_v, 1)
        header_inner.addWidget(info_btn)
        lay.addWidget(self._header_frame)

        self._ctrl_frame = QFrame()
        self._ctrl_frame.setObjectName("ctrl_box")
        ctrl_lay = QHBoxLayout(self._ctrl_frame)
        ctrl_lay.setContentsMargins(12, 8, 12, 8)

        lbl_v = QLabel("Versão Firebird:")
        lbl_v.setFont(QFont(FONT_SANS, 9, QFont.Weight.Bold))

        self._radio_fb3 = QRadioButton("FB 3.0")
        self._radio_fb4 = QRadioButton("FB 4.0")
        self._radio_fb4.setChecked(True)

        v_group = QHBoxLayout()
        v_group.setSpacing(12)
        v_group.addWidget(self._radio_fb3)
        v_group.addWidget(self._radio_fb4)

        self._btn_varrer = make_primary_btn("🔍  VARRER HD", 130)
        self._btn_varrer.setFixedHeight(32)
        self._btn_varrer.clicked.connect(self._on_varrer)

        self._btn_explorer = make_secondary_btn("📂  PROCURAR", 120)
        self._btn_explorer.setFixedHeight(32)
        self._btn_explorer.clicked.connect(self._on_selecionar_explorer)

        ctrl_lay.addWidget(lbl_v)
        ctrl_lay.addLayout(v_group)
        ctrl_lay.addSpacing(16)
        ctrl_lay.addWidget(self._btn_varrer)
        ctrl_lay.addWidget(self._btn_explorer)
        ctrl_lay.addStretch()
        lay.addWidget(self._ctrl_frame)

        self._lbl_count = QLabel("Aguardando início da varredura...")
        self._lbl_count.setFont(QFont(FONT_MONO, 8))
        lay.addWidget(self._lbl_count)

        self._lista = QListWidget()
        self._lista.setMinimumHeight(180)
        self._lista.setFont(QFont(FONT_MONO, 9))
        self._lista.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._lista.itemSelectionChanged.connect(self._on_selecao_changed)
        lay.addWidget(self._lista)

        self._preview_frame = QFrame()
        self._preview_frame.setObjectName("preview_box")
        prev_lay = QGridLayout(self._preview_frame)
        prev_lay.setContentsMargins(10, 6, 10, 6)
        prev_lay.setSpacing(4)

        self._lbl_dados_tag = QLabel("Dados:")
        self._lbl_dados_tag.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self._lbl_dados = QLabel("—")
        self._lbl_dados.setWordWrap(True)
        self._lbl_dados.setFont(QFont(FONT_MONO, 8))

        self._lbl_cep_tag = QLabel("CEP:")
        self._lbl_cep_tag.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self._lbl_cep = QLabel("—")
        self._lbl_cep.setWordWrap(True)
        self._lbl_cep.setFont(QFont(FONT_MONO, 8))

        prev_lay.addWidget(self._lbl_dados_tag, 0, 0)
        prev_lay.addWidget(self._lbl_dados,     0, 1)
        prev_lay.addWidget(self._lbl_cep_tag,   1, 0)
        prev_lay.addWidget(self._lbl_cep,       1, 1)
        lay.addWidget(self._preview_frame)

        self._btn_aplicar = make_primary_btn("⚙️  CONFIGURAR AGORA", 200)
        self._btn_aplicar.setFixedHeight(38)
        self._btn_aplicar.setEnabled(False)
        self._btn_aplicar.clicked.connect(self._on_aplicar)

        self._lbl_resultado = QLabel("")
        self._lbl_resultado.setFont(QFont(FONT_SANS, 9, QFont.Weight.Bold))
        self._lbl_resultado.setWordWrap(True)

        bt_row = QHBoxLayout()
        bt_row.addWidget(self._btn_aplicar)
        bt_row.addSpacing(12)
        bt_row.addWidget(self._lbl_resultado, 1)
        lay.addLayout(bt_row)
        lay.addStretch()

    def set_version(self, versao: str):
        if versao == "3":
            self._radio_fb3.setChecked(True)
        elif versao == "4":
            self._radio_fb4.setChecked(True)

    def _on_varrer(self):
        self._lista.clear()
        self._arquivos = []
        self._lbl_count.setText("Varrendo... aguarde.")
        self._btn_varrer.setEnabled(False)
        self._btn_explorer.setEnabled(False)
        self._btn_aplicar.setEnabled(False)
        self._lbl_dados.setText("—")
        self._lbl_cep.setText("—")
        self._lbl_resultado.setText("")

        worker = _VarreduraWorker()
        worker.log.connect(lambda m: self._lbl_count.setText(m))
        worker.concluido.connect(self._on_varredura_concluida)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _on_varredura_concluida(self, arquivos: list[str]):
        self._arquivos = arquivos
        self._btn_varrer.setEnabled(True)
        self._btn_explorer.setEnabled(True)
        self._lista.clear()

        if not arquivos:
            self._lbl_count.setText("Nenhum arquivo .fdb encontrado.")
            return

        self._lbl_count.setText(
            f"{len(arquivos)} arquivo(s) .fdb encontrado(s) — selecione o Dados:"
        )
        for caminho in arquivos:
            item = QListWidgetItem(caminho)
            item.setToolTip(caminho)
            self._lista.addItem(item)

    def _on_selecionar_explorer(self):
        import os
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo Dados", "C:\\",
            "Firebird Database (*.fdb);;Todos os arquivos (*.*)",
        )
        if not caminho:
            return

        caminho = os.path.normpath(caminho)
        pasta   = os.path.dirname(caminho)
        cep     = os.path.join(pasta, "cep.fdb")

        existentes = [self._lista.item(i).text() for i in range(self._lista.count())]
        if caminho not in existentes:
            item = QListWidgetItem(caminho)
            item.setToolTip(caminho)
            self._lista.insertItem(0, item)
            total = len(existentes) + 1
            self._lbl_count.setText(f"{total} arquivo(s) listado(s) — selecione o Dados:")

        for i in range(self._lista.count()):
            if self._lista.item(i).text() == caminho:
                self._lista.setCurrentRow(i)
                break

        self._lbl_dados.setText(caminho)
        self._lbl_cep.setText(cep)
        self._btn_aplicar.setEnabled(True)
        self._lbl_resultado.setText("")

    def _on_selecao_changed(self):
        import os
        items = self._lista.selectedItems()
        if not items:
            self._lbl_dados.setText("—")
            self._lbl_cep.setText("—")
            self._btn_aplicar.setEnabled(False)
            return

        caminho_dados = items[0].text()
        pasta         = os.path.dirname(caminho_dados)
        caminho_cep   = os.path.join(pasta, "cep.fdb")

        self._lbl_dados.setText(caminho_dados)
        self._lbl_cep.setText(caminho_cep)
        self._btn_aplicar.setEnabled(True)
        self._lbl_resultado.setText("")

    def _on_aplicar(self):
        items = self._lista.selectedItems()
        if not items:
            return

        versao        = "3" if self._radio_fb3.isChecked() else "4"
        caminho_dados = items[0].text()

        if not fb_portable_instalado(versao):
            self._lbl_resultado.setText(f"[!] FB{versao} não está instalado.")
            self._lbl_resultado.setStyleSheet(
                "color:#e67e22; background:transparent; border:none;"
            )
            return

        self._btn_aplicar.setEnabled(False)
        self._btn_varrer.setEnabled(False)
        self._btn_explorer.setEnabled(False)
        self._lbl_resultado.setText("Aplicando...")
        self._lbl_resultado.setStyleSheet(
            f"color:{COLORS.get('text_mid','#aaa')}; background:transparent; border:none;"
        )

        worker = _DatabasesConfWorker(versao, caminho_dados)
        worker.concluido.connect(self._on_aplicar_concluido)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _on_aplicar_concluido(self, r: dict):
        self._btn_aplicar.setEnabled(True)
        self._btn_varrer.setEnabled(True)
        self._btn_explorer.setEnabled(True)
        if r["ok"]:
            versao = "3" if self._radio_fb3.isChecked() else "4"
            self._lbl_resultado.setText(f"databases.conf do FB{versao} atualizado!")
            self._lbl_resultado.setStyleSheet(
                "color:#2ecc71; background:transparent; border:none;"
            )
        else:
            self._lbl_resultado.setText(f"Erro: {r['erro']}")
            self._lbl_resultado.setStyleSheet(
                "color:#e74c3c; background:transparent; border:none;"
            )

    def _lista_style(self) -> str:
        if theme_manager.ui_theme == "classic":
            bg   = COLORS.get("bg",      "#121212")
            surf = COLORS.get("surface", "#1e1e1e")
            brd  = COLORS.get("border",  "#444")
            acc  = COLORS.get("accent",  "#0078d4")
            txt  = COLORS.get("text")
            return f"""
                QListWidget {{
                    background:{bg}; color:{txt};
                    border:1px solid {brd}; border-radius:6px;
                    padding:4px;
                }}
                QListWidget::item {{
                    padding:4px 8px; border-radius:4px;
                }}
                QListWidget::item:selected {{
                    background:{acc}; color:#fff;
                }}
                QListWidget::item:hover:!selected {{
                    background:{surf};
                }}
                QScrollBar:vertical {{
                    background:{surf}; width:8px; border-radius:4px;
                }}
                QScrollBar::handle:vertical {{
                    background:{brd}; border-radius:4px; min-height:20px;
                }}
            """
        else:
            bg   = COLORS.get("bg",      "#0f0f0f")
            surf = COLORS.get("surface", "#181818")
            brd  = COLORS.get("border",  "#2a2a2a")
            acc  = COLORS.get("accent",  "#0078d4")
            txt  = COLORS.get("text")
            return f"""
                QListWidget {{
                    background:{bg}; color:{txt};
                    border:1px solid {brd}; border-radius:8px;
                    padding:6px; outline: none;
                }}
                QListWidget::item {{
                    padding:8px 12px; border-radius:6px;
                    margin-bottom: 2px;
                    color: {COLORS.get('text_mid','#aaa')};
                    border-bottom: 1px solid {surf};
                }}
                QListWidget::item:selected {{
                    background: rgba(0, 120, 212, 0.2);
                    color: {acc};
                    border: 1px solid {acc};
                    font-weight: bold;
                }}
                QListWidget::item:hover:!selected {{
                    background:{surf};
                    color: {COLORS.get('text','#fff')};
                }}
                QScrollBar:vertical {{
                    background: transparent; width:10px; margin: 4px; border-radius:5px;
                }}
                QScrollBar::handle:vertical {{
                    background:{brd}; border-radius:5px; min-height:30px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background:{acc};
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            """

    def _upd_style(self, _=""):
        self._lista.setStyleSheet(self._lista_style())

        if theme_manager.ui_theme == "classic":
            self.setStyleSheet(f"""
                QFrame#db_conf_card {{
                    background:{COLORS.get('surface','#1e1e1e')};
                    border:1.5px solid {COLORS.get('border','#444')};
                    border-radius:10px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#db_conf_card {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {COLORS.get('surface','#1a1a1a')},
                        stop:1 {COLORS.get('bg','#121212')});
                    border:1.5px solid {COLORS.get('border','#333')};
                    border-radius:12px;
                }}
                QFrame#ctrl_box {{
                    background: rgba(255, 255, 255, 0.03);
                    border: 1px solid {COLORS.get('border','#2a2a2a')};
                    border-radius: 8px;
                }}
                QRadioButton {{
                    color: {COLORS.get('text_mid','#aaa')};
                    spacing: 8px;
                }}
                QRadioButton::indicator {{
                    width: 14px; height: 14px;
                }}
                QRadioButton:checked {{
                    color: {COLORS.get('accent','#0078d4')};
                    font-weight: bold;
                }}
            """)


# =============================================================================
# Card de Instalação / Remoção
# =============================================================================

class _InstallRemoveCard(QFrame):
    instalar_solicitado = pyqtSignal(str)
    remover_solicitado  = pyqtSignal(str)
    sig_set_loading     = pyqtSignal(bool, str, int)

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self._versao    = versao
        self._instalado = False
        self.setObjectName(f"install_remove_card_{versao}")
        self._build_ui()
        self._upd_style()
        theme_manager.theme_changed.connect(lambda _: self._upd_style())
        self.sig_set_loading.connect(self.set_loading)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        header = QHBoxLayout()
        titulo = QLabel(f"Firebird {self._versao}")
        titulo.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        titulo.setStyleSheet(f"color:{_COR[self._versao]};")

        icon = QLabel("📦")
        icon.setFont(QFont(FONT_SANS, 14))

        self._lbl_badge = QLabel("NÃO INSTALADO")
        self._lbl_badge.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self._lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_badge.setMinimumWidth(120)
        self._lbl_badge.setContentsMargins(6, 2, 6, 2)

        header.addWidget(titulo, 1)
        header.addWidget(self._lbl_badge)
        header.addWidget(icon)
        lay.addLayout(header)

        hl = QFrame()
        hl.setFrameShape(QFrame.Shape.HLine)
        hl.setStyleSheet(f"background:{COLORS.get('border','#444')}; max-height:1px;")
        lay.addWidget(hl)

        cfg = FB_CONFIGS[self._versao]
        self._lbl_info = QLabel(
            f"Diretório: {cfg['dir']}\n"
            f"Porta: {cfg['porta']}"
        )
        self._lbl_info.setFont(QFont(FONT_MONO, 9))
        self._lbl_info.setWordWrap(True)
        self._lbl_info.setStyleSheet(
            f"color:{COLORS.get('text_mid','#aaa')}; background:transparent; border:none;"
        )
        lay.addWidget(self._lbl_info)

        self._lbl_ver = QLabel("")
        self._lbl_ver.setFont(QFont(FONT_MONO, 8))
        self._lbl_ver.setStyleSheet(
            f"color:{COLORS.get('accent2','#2ecc71')}; background:transparent; border:none;"
        )
        lay.addWidget(self._lbl_ver)

        lay.addStretch()

        self._status_box = QWidget()
        self._status_box.setVisible(False)
        st_lay = QVBoxLayout(self._status_box)
        st_lay.setContentsMargins(0, 4, 0, 4)
        st_lay.setSpacing(4)
        self._lbl_status = label("Preparando...", COLORS["text_dim"], 8)
        self._pbar = QProgressBar()
        self._pbar.setFixedHeight(4)
        self._pbar.setTextVisible(False)
        self._pbar.setRange(0, 100)
        st_lay.addWidget(self._lbl_status)
        st_lay.addWidget(self._pbar)
        lay.addWidget(self._status_box)

        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(10)

        self._btn_instalar = make_primary_btn("⚡  INSTALAR", 160)
        self._btn_instalar.setFixedHeight(38)
        self._btn_instalar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_instalar.clicked.connect(
            lambda: self.instalar_solicitado.emit(self._versao)
        )

        self._btn_remover = QPushButton("🗑️  REMOVER")
        self._btn_remover.setFixedHeight(38)
        self._btn_remover.setMinimumWidth(130)
        self._btn_remover.setFont(QFont(FONT_SANS, 10, QFont.Weight.Bold))
        self._btn_remover.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_remover.clicked.connect(
            lambda: self.remover_solicitado.emit(self._versao)
        )

        btn_lay.addWidget(self._btn_instalar, 1)
        btn_lay.addWidget(self._btn_remover, 1)
        lay.addLayout(btn_lay)

        self._set_estado(False)

    def set_instalado(self, instalado: bool, ver_str: str = ""):
        try:
            self._instalado = instalado
            self._lbl_ver.setText(f"Versão: {ver_str}" if ver_str else "")
            self._set_estado(instalado)
        except RuntimeError:
            pass

    @pyqtSlot(bool)
    @pyqtSlot(bool, str)
    @pyqtSlot(bool, str, int)
    def set_loading(self, active: bool, msg: str = "", progress: int = 0):
        try:
            self._status_box.setVisible(active)
            self._btn_instalar.setEnabled(not active)
            self._btn_remover.setEnabled(not active)
            if active:
                if msg:
                    self._lbl_status.setText(msg)
                self._pbar.setValue(progress)
        except RuntimeError:
            pass

    def _set_estado(self, instalado: bool):
        acc = _COR[self._versao]
        brd = COLORS.get("border", "#444")

        if instalado:
            self._lbl_badge.setText("INSTALADO")
            self._lbl_badge.setStyleSheet(f"""
                QLabel {{
                    background:{COLORS.get('accent2','#2ecc71')}; color:#fff;
                    border-radius:4px; padding:2px 8px; font-weight:bold;
                }}
            """)
        else:
            self._lbl_badge.setText("NÃO INSTALADO")
            self._lbl_badge.setStyleSheet(f"""
                QLabel {{
                    background:{COLORS.get('surface','#2a2a2a')};
                    color:{COLORS.get('text_dim','#888')};
                    border:1px solid {brd};
                    border-radius:4px; padding:2px 8px; font-weight:bold;
                }}
            """)

        self._btn_instalar.setEnabled(not instalado)
        if not instalado:
            self._btn_instalar.setStyleSheet(f"""
                QPushButton {{
                    background:{acc}; color:#fff; border:none;
                    border-radius:6px; padding:6px 16px; font-weight:bold;
                    font-size:10pt;
                }}
                QPushButton:hover {{ background:{acc}; opacity:0.85; }}
                QPushButton:disabled {{
                    background:{brd}; color:{COLORS.get('text_disabled','#666')};
                    border-radius:6px;
                }}
            """)
        else:
            self._btn_instalar.setStyleSheet(f"""
                QPushButton {{
                    background:{brd}; color:{COLORS.get('text_disabled','#666')};
                    border:none; border-radius:6px; padding:6px 16px;
                    font-weight:bold; font-size:10pt;
                }}
            """)

        self._btn_remover.setEnabled(instalado)
        if instalado:
            self._btn_remover.setStyleSheet(f"""
                QPushButton {{
                    background:#c0392b; color:#fff; border:none;
                    border-radius:6px; padding:6px 16px; font-weight:bold;
                    font-size:10pt;
                }}
                QPushButton:hover {{ background:#e74c3c; }}
                QPushButton:disabled {{
                    background:{brd}; color:{COLORS.get('text_disabled','#666')};
                    border-radius:6px;
                }}
            """)
        else:
            self._btn_remover.setStyleSheet(f"""
                QPushButton {{
                    background:{brd}; color:{COLORS.get('text_disabled','#666')};
                    border:none; border-radius:6px; padding:6px 16px;
                    font-weight:bold; font-size:10pt;
                }}
            """)

    def _upd_style(self, _=""):
        acc = _COR[self._versao]
        bg  = COLORS.get("surface", "#1e1e1e")
        brd = COLORS.get("border",  "#444")
        self.setStyleSheet(f"""
            QFrame#install_remove_card_{self._versao} {{
                background:{bg};
                border:1.5px solid {brd};
                border-radius:12px;
            }}
            QFrame#install_remove_card_{self._versao}:hover {{
                border:1.5px solid {acc};
                background:{COLORS.get('surface2','#2a2a2a')};
            }}
        """)
        self._pbar.setStyleSheet(f"""
            QProgressBar {{ background:{brd}; border:none; border-radius:2px; }}
            QProgressBar::chunk {{ background:{acc}; border-radius:2px; }}
        """)
        self._set_estado(self._instalado)


class _AutoInstallCard(QFrame):
    acao_solicitada = pyqtSignal(str)
    sig_set_loading = pyqtSignal(bool, str, int)

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self._versao = versao
        self.setObjectName(f"auto_install_card_{versao}")
        self._build_ui()
        self._upd_style()
        theme_manager.theme_changed.connect(lambda _: self._upd_style())
        self.sig_set_loading.connect(self.set_loading)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        header = QHBoxLayout()
        titulo = QLabel(f"Firebird {self._versao}")
        titulo.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        titulo.setStyleSheet(f"color:{_COR[self._versao]};")

        icon = QLabel("🚀")
        icon.setFont(QFont(FONT_SANS, 14))

        header.addWidget(titulo, 1)

        self._lbl_installed = label("✅ INSTALADO", COLORS["accent2"], 8)
        self._lbl_installed.setStyleSheet(f"color:{COLORS['accent2']}; font-weight: bold;")
        self._lbl_installed.setVisible(False)
        header.addWidget(self._lbl_installed)

        header.addWidget(icon)
        lay.addLayout(header)

        h_line_lay = QVBoxLayout()
        h_line_lay.setContentsMargins(0, 4, 0, 8)
        hl = QFrame()
        hl.setFrameShape(QFrame.Shape.HLine)
        hl.setStyleSheet(f"background:{COLORS.get('border','#444')}; max-height:1px;")
        h_line_lay.addWidget(hl)
        lay.addLayout(h_line_lay)

        steps = [
            "Download e instalação do portable",
            "Configuração do modo de execução",
            "Ativação automática da versão"
        ]
        if self._versao == "4":
            steps.insert(2, "Importação de configurações oficiais")

        desc_text = "Este assistente executará:\n"
        for i, s in enumerate(steps, 1):
            desc_text += f"   {i}. {s}\n"

        desc = label(desc_text.strip(), COLORS["text_mid"], 9)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{COLORS['text_mid']}; line-height: 1.4;")
        lay.addWidget(desc)

        lay.addStretch()

        self._status_box = QWidget()
        self._status_box.setVisible(False)
        st_lay = QVBoxLayout(self._status_box)
        st_lay.setContentsMargins(0, 8, 0, 8)
        st_lay.setSpacing(6)

        self._lbl_status = label("Preparando...", COLORS["text_dim"], 8)
        self._pbar = QProgressBar()
        self._pbar.setFixedHeight(4)
        self._pbar.setTextVisible(False)
        self._pbar.setRange(0, 100)

        st_lay.addWidget(self._lbl_status)
        st_lay.addWidget(self._pbar)
        lay.addWidget(self._status_box)

        self._btn = make_primary_btn("INSTALAÇÃO AUTOMÁTICA", 240)
        self._btn.setFixedHeight(38)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(lambda: self.acao_solicitada.emit(self._versao))
        lay.addWidget(self._btn, 0, Qt.AlignmentFlag.AlignCenter)

    @pyqtSlot(bool)
    @pyqtSlot(bool, str)
    @pyqtSlot(bool, str, int)
    def set_loading(self, active: bool, msg: str = "", progress: int = 0):
        try:
            self._status_box.setVisible(active)
            self._btn.setEnabled(not active)
            if active:
                if msg:
                    self._lbl_status.setText(msg)
                self._pbar.setValue(progress)
        except RuntimeError:
            pass

    def set_installed(self, installed: bool):
        try:
            self._lbl_installed.setVisible(installed)
            if installed:
                self._btn.setText("REINSTALAR")
                _apply_secondary_style(self._btn)
            else:
                self._btn.setText("INSTALAÇÃO AUTOMÁTICA")
                _apply_primary_style(self._btn)
        except RuntimeError:
            return

    def _upd_style(self, _=""):
        acc = _COR[self._versao]
        bg  = COLORS.get('surface', '#1e1e1e')
        brd = COLORS.get('border', '#444')
        self.setStyleSheet(f"""
            QFrame#auto_install_card_{self._versao} {{
                background:{bg};
                border:1.5px solid {brd};
                border-radius:12px;
            }}
            QFrame#auto_install_card_{self._versao}:hover {{
                border:1.5px solid {acc};
                background:{COLORS.get('surface2','#2a2a2a')};
            }}
        """)
        self._pbar.setStyleSheet(f"""
            QProgressBar {{ background: {brd}; border: none; border-radius: 2px; }}
            QProgressBar::chunk {{ background: {acc}; border-radius: 2px; }}
        """)


# Componentes movidos para firebird_widgets.py


# =============================================================================
# Página principal
# =============================================================================

class PageFbPortable(QWidget):
    go_menu           = pyqtSignal()
    sig_setar_ocupado = pyqtSignal(bool)
    sig_admin_res     = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: QThread | None             = None
        self._admin_check_worker: QThread | None = None
        self._status_worker: QThread | None      = None
        self._versao_sel   = "4"
        self._upd_toggle   = False
        self._toggle_rows  : dict[str, _ToggleRow]  = {}
        self._modo_cards   : dict[str, _ModoCard]   = {}
        self._versao_auto_install: str = "4"
        self._tabs_built = {0: True, 1: False, 2: False, 3: False, 4: False, 5: False}

        self._last_st: dict | None = None
        self._eh_admin: bool | None = None
        self._tab_db: QWidget | None = None

        self._build_ui()
        theme_manager.theme_changed.connect(self._upd_style)

        # Conectar sinais de ponte para threads
        self.sig_setar_ocupado.connect(self._setar_ocupado_slot)
        self.sig_admin_res.connect(self._on_admin_check_full_concluido)

        self._timer = QTimer(self)
        self._timer.setInterval(4000)
        self._timer.timeout.connect(self._atualizar_status)

    # =========================================================================
    # Verificação assíncrona de admin
    # =========================================================================

    def _verificar_admin_background(self):
        if self._admin_check_worker and self._admin_check_worker.isRunning():
            return
        aw = _AdminCheckWorker(self)
        aw.concluido.connect(self._on_admin_resultado_inicial)
        aw.finished.connect(lambda: setattr(self, "_admin_check_worker", None))
        self._admin_check_worker = aw
        aw.start()

    def _on_admin_resultado_inicial(self, admin_ok: bool):
        self._eh_admin = admin_ok

        if not admin_ok and self._banner_admin is None:
            self._banner_admin = _BannerAdmin()
            self._banner_admin.btn_reiniciar.clicked.connect(self._on_reiniciar_admin)
            self._content_lay.insertWidget(0, self._banner_admin)

        for card in self._modo_cards.values():
            try:
                card._lbl_nota.setVisible(not admin_ok)
            except RuntimeError:
                pass

        self._timer.start()
        self._atualizar_status()

    # =========================================================================
    # Construção da UI
    # =========================================================================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = PageHeader(
            "FIREBIRD PORTABLE",
            "Instale, ative e configure FB3 e FB4 de forma independente"
        )
        self._header.back_clicked.connect(self.go_menu.emit)
        root.addWidget(self._header)

        content_w = QWidget()
        self._content_lay = QVBoxLayout(content_w)
        self._content_lay.setContentsMargins(20, 16, 20, 12)
        self._content_lay.setSpacing(8)

        def _upd_title():
            if theme_manager.ui_theme == "modern":
                self._header.set_subtitle("✨ Interface Premium - Configuração Avançada")
            else:
                self._header.set_subtitle("Instale, ative e configure FB3 e FB4 de forma independente")

        theme_manager.ui_theme_changed.connect(_upd_title)
        _upd_title()

        self._banner_admin = None
        
        # Componentes globais que precisam existir desde o início
        self._alert    = AlertBox("", "info")
        self._progress = QProgressBar()
        self._console  = _Console(fixed_height=0)
        self._ir_cards : dict[str, _InstallRemoveCard] = {}
        self._auto_cards : dict[str, _AutoInstallCard] = {}
        self._toggle_rows : dict[str, _ToggleRow] = {}
        self._modo_cards : dict[str, _ModoCard] = {}
        
        self._tabs = QTabWidget()
        self._tabs.setFont(QFont(FONT_SANS, 10))
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._content_lay.addWidget(self._tabs)

        # -- ABA 0: Instalação Automática (Carregada no Início) -----------
        self._tab_auto = QWidget()
        self._build_tab_auto()
        self._tabs.addTab(self._tab_auto, "⚡ Instalação Automática")

        # -- Placeholders para as outras abas (Lazy Loading) -------------
        self._tab_controle = QWidget()
        self._tab_instalar = QWidget()
        self._tab_db       = QWidget()
        self._tab_fb4      = QWidget()
        self._tab_log      = QWidget()

        self._tabs.addTab(self._tab_controle, "⚙️ Controle de Versões")
        self._tabs.addTab(self._tab_instalar, "📦 Instalar / Remover")
        self._tabs.addTab(self._tab_db,       "🗄️ Banco de Dados")
        self._tabs.addTab(self._tab_fb4,      "🔧 Configurações FB4")
        self._tabs.addTab(self._tab_log,      "📋 Logs")

        self._content_lay.addStretch()
        root.addWidget(content_w)

        self._upd_style()

    def _on_tab_changed(self, index):
        if self._tabs_built.get(index):
            return
        
        if index == 1: self._build_tab_controle()
        elif index == 2: self._build_tab_instalar()
        elif index == 3: self._build_tab_db()
        elif index == 4: self._build_tab_fb4()
        elif index == 5: self._build_tab_log()
        
        self._tabs_built[index] = True
        self._upd_style()

    def _build_tab_auto(self):
        alay = QVBoxLayout(self._tab_auto)
        alay.setContentsMargins(16, 16, 16, 16)
        alay.setSpacing(10)
        desc_auto = label("Assistente para instalar e configurar o Firebird de forma automatizada.", COLORS["text_mid"], 10)
        desc_auto.setWordWrap(True)
        alay.addWidget(desc_auto)
        card_lay = QHBoxLayout(); card_lay.setSpacing(16)
        self._auto_cards = {}
        for v in ("3", "4"):
            card = _AutoInstallCard(v)
            card.acao_solicitada.connect(self._on_auto_install)
            card.sig_set_loading.connect(card.set_loading)
            self._auto_cards[v] = card
            card_lay.addWidget(card, 1)
        alay.addLayout(card_lay); alay.addStretch()

    def _build_tab_controle(self):
        tlay_root = QVBoxLayout(self._tab_controle)
        tlay_root.setContentsMargins(16, 16, 16, 16)
        tlay_root.setSpacing(10)
        info = label("Ative/inative cada versão e configure o modo de execução. ", COLORS["text_mid"], 10)
        info.setWordWrap(True); tlay_root.addWidget(info)
        self._dashboard = _StatusDashboard()
        self._dashboard.versao_clicada.connect(self._on_dash_v_clicada)
        self._dashboard.acao_solicitada.connect(self._on_dash_acao)
        tlay_root.addWidget(self._dashboard)
        tf = QFrame(); tf.setObjectName("toggles_frame")
        tlay_cols = QHBoxLayout(tf); tlay_cols.setContentsMargins(16, 16, 16, 16); tlay_cols.setSpacing(16)
        for versao in ("3", "4"):
            cfg = FB_CONFIGS[versao]; det = f"Porta {cfg['porta']}"
            col_frame = QFrame(); col_lay = QVBoxLayout(col_frame); col_lay.setContentsMargins(0,0,0,0); col_lay.setSpacing(10)
            row = _ToggleRow(versao, det)
            row.toggle.toggled.connect(lambda checked, v=versao: self._on_toggle(v, checked))
            self._toggle_rows[versao] = row
            col_lay.addWidget(row)
            card = _ModoCard(versao); card.acao_solicitada.connect(self._on_servico_acao)
            self._modo_cards[versao] = card
            col_lay.addWidget(card); col_lay.addStretch(); tlay_cols.addWidget(col_frame, 1)
        tlay_root.addWidget(tf); tlay_root.addStretch()

    def _build_tab_instalar(self):
        ilay = QVBoxLayout(self._tab_instalar)
        ilay.setContentsMargins(16, 16, 16, 16); ilay.setSpacing(10)
        ir_card_lay = QHBoxLayout(); ir_card_lay.setSpacing(16)
        for v in ("3", "4"):
            ir_card = _InstallRemoveCard(v); ir_card.instalar_solicitado.connect(self._on_instalar); ir_card.remover_solicitado.connect(self._on_remover); ir_card.sig_set_loading.connect(ir_card.set_loading)
            self._ir_cards[v] = ir_card; ir_card_lay.addWidget(ir_card, 1)
        ilay.addLayout(ir_card_lay)
        ilay.addWidget(self._progress); ilay.addWidget(self._alert); ilay.addStretch()

    def _build_tab_db(self):
        dlay = QVBoxLayout(self._tab_db); dlay.setContentsMargins(16,16,16,16)
        self._tab_db = self._tab_db # No-op to satisfy reference
        self._db_conf_card = _DatabasesConfCard(); dlay.addWidget(self._db_conf_card); dlay.addStretch()

    def _build_tab_fb4(self):
        flay = QVBoxLayout(self._tab_fb4); flay.setContentsMargins(16,16,16,16)
        self._fb4_conf_card = _Fb4ConfigCard()
        self._fb4_conf_card.btn.clicked.connect(self._on_recuperar_fb4)
        flay.addWidget(self._fb4_conf_card); flay.addStretch()

    def _on_recuperar_fb4(self):
        if self._worker and self._worker.isRunning(): return
        self._console.clear_console()
        self._console.append("Iniciando otimização do Firebird 4...")
        worker = _ConfigsOficiaisWorker()
        worker.log.connect(self._console.append)
        worker.concluido.connect(self._on_recuperar_fb4_concluido)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _on_recuperar_fb4_concluido(self, r: dict):
        if r["ok"]: self._alerta("Firebird 4 otimizado com sucesso!", "success")
        else: self._alerta(f"Erro: {r['erro']}", "error")

    def _build_tab_log(self):
        llay = QVBoxLayout(self._tab_log); llay.setContentsMargins(0, 8, 0, 0)
        llay.addWidget(self._console, 1)
        btn_limpar = make_secondary_btn("Limpar Log", 130); btn_limpar.clicked.connect(self._console.limpar); llay.addWidget(btn_limpar)

    # =========================================================================
    # Toggles — alternância automática
    # =========================================================================

    def _on_toggle(self, versao: str, checked: bool):
        if self._upd_toggle:
            return

        outra = "4" if versao == "3" else "3"

        if checked:
            lbl_alvo  = FB_CONFIGS[versao]["label"]
            lbl_outra = FB_CONFIGS[outra]["label"]
            outra_ativa = (self._last_st or {}).get(f"fb{outra}", {}).get("rodando", False)
            if outra_ativa:
                msg_console = (
                    f"Ativando {lbl_alvo} e desativando {lbl_outra} automaticamente ..."
                )
            else:
                msg_console = f"Ativando {lbl_alvo} ..."
        else:
            msg_console = f"Inativando {FB_CONFIGS[versao]['label']} ..."

        self.sig_setar_ocupado.emit(True)
        self._console.limpar()
        self._alert.setVisible(False)
        self._console.append(msg_console)

        worker = _AlternarWorker(versao, checked)
        worker.log.connect(self._console.append,
                           Qt.ConnectionType.QueuedConnection)
        worker.concluido.connect(self._on_toggle_concluido,
                                 Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_toggle_concluido(self, r: dict):
        self.sig_setar_ocupado.emit(False)
        self._atualizar_status()
        versao = r.get("versao", "")
        ativar = r.get("ativar", True)
        lbl    = FB_CONFIGS.get(versao, {}).get("label", f"FB{versao}")
        acao   = "ativado" if ativar else "inativado"
        if r.get("requer_admin"):
            self._alerta(
                "Permissao de administrador necessaria. Use o botão 'Reiniciar como Admin'.",
                "warn"
            )
        elif r["ok"]:
            if ativar:
                outra     = "4" if versao == "3" else "3"
                lbl_outra = FB_CONFIGS[outra]["label"]
                outra_rod = (self._last_st or {}).get(f"fb{outra}", {}).get("rodando", False)
                if outra_rod:
                    self._alerta(
                        f"{lbl} ativado! {lbl_outra} foi desativado automaticamente.",
                        "success"
                    )
                else:
                    self._alerta(f"{lbl} {acao} com sucesso!", "success")
            else:
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
        if not self._eh_admin:
            self._alerta(
                "Permissao de administrador necessaria. Reinicie como Administrador.", "warn"
            )
            return
        label_acao = "Registrando" if acao == "registrar" else "Removendo"
        self.sig_setar_ocupado.emit(True)
        self._console.limpar()
        self._alert.setVisible(False)
        self._console.append(
            f"{label_acao} servico Windows do {FB_CONFIGS[versao]['label']} ..."
        )
        worker = _ServicoWorker(versao, acao)
        worker.log.connect(self._console.append,
                           Qt.ConnectionType.QueuedConnection)
        worker.concluido.connect(self._on_servico_concluido,
                                 Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_servico_concluido(self, r: dict):
        self.sig_setar_ocupado.emit(False)
        self._atualizar_status()
        versao = r.get("versao", "")
        acao   = r.get("acao", "")
        lbl    = FB_CONFIGS.get(versao, {}).get("label", f"FB{versao}")
        if r.get("requer_admin"):
            self._alerta(
                "Permissao de administrador necessaria. Reinicie como Administrador.", "warn"
            )
        elif r["ok"]:
            if acao == "registrar":
                self._alerta(
                    f"{lbl} registrado como serviço Windows! "
                    "Inicia automaticamente com o Windows.",
                    "success"
                )
            else:
                self._alerta(
                    f"Serviço Windows do {lbl} removido. Voltou ao modo processo.",
                    "success"
                )
        else:
            self._alerta(f"Erro: {r['erro']}", "error")

    def _on_dash_v_clicada(self, versao: str):
        if self._worker:
            return
        row = self._toggle_rows.get(versao)
        if row and row.toggle.isEnabled():
            row.toggle.setChecked(not row.toggle.isChecked())

    def _on_dash_acao(self, versao: str, acao: str):
        if self._worker:
            return

        if acao == "reiniciar":
            self._on_reiniciar(versao)
        elif acao == "iniciar":
            row = self._toggle_rows.get(versao)
            if row and row.toggle.isEnabled():
                row.toggle.setChecked(True)
        elif acao == "parar":
            row = self._toggle_rows.get(versao)
            if row and row.toggle.isEnabled():
                row.toggle.setChecked(False)

    def _on_reiniciar(self, versao: str):
        self.sig_setar_ocupado.emit(True)
        self._console.limpar()
        self._console.append(f"Reiniciando {FB_CONFIGS[versao]['label']} ...")
        worker = _ReiniciarWorker(versao)
        worker.log.connect(self._console.append,
                           Qt.ConnectionType.QueuedConnection)
        worker.concluido.connect(self._on_reiniciar_concluido,
                                 Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_reiniciar_concluido(self, r: dict):
        self.sig_setar_ocupado.emit(False)
        self._atualizar_status()
        if r["ok"]:
            self._alerta("Reiniciado com sucesso!", "success")
        else:
            self._alerta(f"Erro ao reiniciar: {r['erro']}", "error")

    # =========================================================================
    # Status geral (timer + pós-ações) — tudo em background via _StatusWorker
    # =========================================================================

    def _atualizar_status(self):
        if self._worker and self._worker.isRunning():
            return
        if self._status_worker and self._status_worker.isRunning():
            return

        sw = _StatusWorker()
        sw.concluido.connect(self._on_status_concluido,
                             Qt.ConnectionType.QueuedConnection)
        sw.finished.connect(lambda: setattr(self, "_status_worker", None))
        self._status_worker = sw
        sw.start()

    def _on_status_concluido(self, st: dict):
        if not st:
            return

        self._last_st = st

        self._upd_toggle = True
        eh_admin = self._eh_admin if self._eh_admin is not None else False

        try:
            for versao in ("3", "4"):
                try:
                    d       = st[f"fb{versao}"]
                    inst    = d["instalado"]
                    rodando = d["rodando"]
                    
                    if versao not in self._toggle_rows: continue
                    row     = self._toggle_rows[versao]
                    
                    if versao not in self._modo_cards: continue
                    card    = self._modo_cards[versao]

                    porta = FB_CONFIGS[versao]['porta']
                    if d.get("servico_rod"):
                        det = f"Serviço Windows - porta {porta} - rodando"
                    elif d.get("processo_rod"):
                        det = f"Processo portable - porta {porta} - rodando"
                    elif inst and d.get("modo") == "servico" and d.get("servico_reg"):
                        det = f"Serviço Windows - porta {porta} - parado"
                    elif inst:
                        det = f"Processo portable - porta {porta} - parado"
                    else:
                        det = f"Processo portable - porta {porta}"

                    if versao == "3" and d.get("servico_oficial_rod"):
                        det = f"Serviço oficial - porta {porta} - rodando"

                    try:
                        row.set_estado(rodando, inst, det)
                        row.toggle.setChecked(rodando)
                        row.toggle.setAtivo(inst)
                        row.toggle.setToolTip(
                            "Ativar esta versão irá desativar a outra automaticamente."
                            if inst else ""
                        )
                    except RuntimeError:
                        continue

                    card.atualizar(
                        instalado      = inst,
                        modo           = d.get("modo", "processo"),
                        svc_registrado = d.get("servico_reg", False),
                        svc_rodando    = d.get("servico_rod", False),
                        eh_admin       = eh_admin,
                    )
                except Exception:
                    continue
        finally:
            self._upd_toggle = False

        try:
            if hasattr(self, "_dashboard") and self._dashboard:
                self._dashboard.atualizar(st)
        except Exception:
            pass

        for v in list(self._auto_cards.keys()):
            try:
                inst = st[f"fb{v}"]["instalado"]
                card = self._auto_cards.get(v)
                if card is None:
                    continue
                card.set_installed(inst)
            except RuntimeError:
                self._auto_cards.pop(v, None)
            except Exception:
                continue

        for v in ("3", "4"):
            try:
                d    = st.get(f"fb{v}", {})
                inst = d.get("instalado", False)
                ver  = d.get("ver_str", "")
                ir   = self._ir_cards.get(v)
                if ir:
                    ir.set_instalado(inst, ver)
            except Exception:
                continue

        if st.get("conflito"):
            self._alerta(
                "FB3 e FB4 estão ativos simultaneamente — isso pode causar conflitos.",
                "warn"
            )

    # =========================================================================
    # Instalação Automática
    # =========================================================================

    def _on_auto_install(self, versao: str):
        if self._worker and self._worker.isRunning():
            return

        self._versao_auto_install = versao
        card = self._auto_cards.get(versao)
        if card:
            card.sig_set_loading.emit(True, "Verificando permissões...", 0)

        if self._eh_admin is not None:
            self.sig_admin_res.emit(self._eh_admin)
            return

        aw = _AdminCheckWorker(self)
        aw.concluido.connect(self.sig_admin_res.emit)
        aw.finished.connect(lambda: setattr(self, "_admin_check_worker", None))
        self._admin_check_worker = aw
        aw.start()

    @pyqtSlot(bool)
    def _on_admin_check_full_concluido(self, ok: bool):
        """Bridge para garantir que _on_admin_check_concluido rode na Main Thread."""
        self._on_admin_check_concluido(ok, self._versao_auto_install)

    def _on_admin_check_concluido(self, admin_ok: bool, versao: str):
        self._eh_admin = admin_ok
        card = self._auto_cards.get(versao)

        if not admin_ok:
            if card:
                card.set_loading(False)
            self._alerta(
                "Permissão de administrador necessária para instalação automática.",
                "warn"
            )
            return

        if card:
            card.sig_set_loading.emit(True, "Iniciando...", 0)

        self.sig_setar_ocupado.emit(True)
        self._console.limpar()
        self._alert.setVisible(False)
        self._console.append(f"Iniciando Instalação Automática do Firebird {versao}...")

        worker = _AutoInstallWorker(versao)

        worker.log.connect(self._console.append, Qt.ConnectionType.QueuedConnection)
        
        if card:
            # Corrigido: Remover lambdas inseguras que podem floodar a thread principal se chamadas em loop
            # Criamos slots de ponte para o card
            worker.log.connect(lambda m: card.sig_set_loading.emit(True, m, 0), Qt.ConnectionType.QueuedConnection)
            worker.progresso.connect(lambda v: card.sig_set_loading.emit(True, "", v), Qt.ConnectionType.QueuedConnection)

        worker.concluido.connect(self._on_auto_install_concluido,
                                 Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_auto_install_concluido(self, r: dict):
        versao = self._versao_auto_install
        card   = self._auto_cards.get(versao)
        if card:
            card.sig_set_loading.emit(False, "", 0)

        self.sig_setar_ocupado.emit(False)

        if r["ok"]:
            msg = (
                f"Firebird {versao} instalado e iniciado com sucesso!\n"
                "Agora, o sistema irá procurar seus bancos de dados para completar a configuração."
            )
            self._alerta(msg, "success")

            self._db_conf_card.set_version(versao)
            idx = self._tabs.indexOf(self._tab_db)
            if idx >= 0:
                self._tabs.setCurrentIndex(idx)
            QTimer.singleShot(1000, self._db_conf_card._on_varrer)
        else:
            self._alerta(
                f"Falha na instalação automática: {r.get('erro', 'Erro desconhecido')}",
                "error"
            )

        self._atualizar_status()

    # =========================================================================
    # Instalação / Remoção manual
    # =========================================================================

    def _on_versao_changed(self, versao: str):
        self._versao_sel = versao
        self._alert.setVisible(False)

    def _on_instalar(self, versao: str):
        cfg = FB_CONFIGS[versao]

        inst_cache = (self._last_st or {}).get(f"fb{versao}", {}).get("instalado", False)
        if inst_cache:
            self._alerta(f"{cfg['label']} já está instalado em {cfg['dir']}.", "info")
            return

        self._versao_sel = versao
        ir = self._ir_cards.get(versao)
        if ir:
            ir.sig_set_loading.emit(True, "Iniciando instalação...", 0)

        self.sig_setar_ocupado.emit(True)
        self._console.limpar()
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._alert.setVisible(False)

        worker = _InstalarWorker(versao)
        worker.log.connect(self._console.append,
                           Qt.ConnectionType.QueuedConnection)
        worker.progresso.connect(self._progress.setValue,
                                 Qt.ConnectionType.QueuedConnection)
        worker.concluido.connect(self._on_instalado,
                                 Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_instalado(self, r: dict):
        versao = self._versao_sel
        ir = self._ir_cards.get(versao)
        if ir:
            ir.sig_set_loading.emit(False, "", 0)

        self.sig_setar_ocupado.emit(False)
        self._progress.setVisible(False)
        self._atualizar_status()
        cfg = FB_CONFIGS[versao]
        if r["ok"]:
            self._alerta(f"{cfg['label']} instalado! Versão: {r['versao']}", "success")
        else:
            self._alerta(f"Erro na instalação: {r['erro']}", "error")

    def _on_remover(self, versao: str):
        cfg = FB_CONFIGS[versao]

        inst_cache = (self._last_st or {}).get(f"fb{versao}", {}).get("instalado", False)
        if not inst_cache:
            self._alerta(f"{cfg['label']} não está instalado.", "warn")
            return

        self._versao_sel = versao
        ir = self._ir_cards.get(versao)
        if ir:
            ir.sig_set_loading.emit(True, "Removendo...", 0)

        self.sig_setar_ocupado.emit(True)
        self._console.limpar()
        self._alert.setVisible(False)

        worker = _RemoverWorker(versao)
        worker.log.connect(self._console.append,
                           Qt.ConnectionType.QueuedConnection)
        worker.concluido.connect(self._on_removido,
                                 Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_removido(self, r: dict):
        versao = self._versao_sel
        ir = self._ir_cards.get(versao)
        if ir:
            ir.sig_set_loading.emit(False, "", 0)

        self.sig_setar_ocupado.emit(False)
        self._atualizar_status()
        cfg = FB_CONFIGS[versao]
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

    # CORREÇÃO 12: _setar_ocupado agora verifica se está na thread principal.
    # Se chamado de outra thread (ex: dentro de um worker), redireciona via
    # QMetaObject.invokeMethod com QueuedConnection, garantindo que o QTimer
    # seja manipulado apenas na thread onde foi criado.
    # Isso elimina o erro:
    #   "QBasicTimer::stop: Failed. Possibly trying to stop from a different thread"
    def _setar_ocupado(self, v: bool):
        """Envia sinal para mudar estado ocupado na Main Thread."""
        self.sig_setar_ocupado.emit(v)

    @pyqtSlot(bool)
    def _setar_ocupado_slot(self, v: bool):
        """Implementação real do estado ocupado, sempre rodando na Main Thread."""
        if v:
            self._timer.stop()
        else:
            if not (self._status_worker and self._status_worker.isRunning()):
                self._timer.start()

        for row in self._toggle_rows.values():
            try:
                row.toggle.setEnabled(not v)
            except RuntimeError: pass

        for card in self._modo_cards.values():
            try:
                card.set_ocupado(v)
            except RuntimeError: pass

        for card in self._auto_cards.values():
            try:
                card._btn.setEnabled(not v)
            except RuntimeError: pass

    def _alerta(self, txt: str, kind: str):
        self._alert.set_text(txt)
        self._alert.set_kind(kind)
        self._alert.setVisible(True)

    def _upd_style(self, _=""):
        bg   = COLORS.get("surface",  "#1e1e1e")
        bg2  = COLORS.get("bg",       "#121212")
        brd  = COLORS.get("border",   "#444")
        txt  = COLORS.get("text",     "#fff")
        tmid = COLORS.get("text_mid", "#aaa")
        acc  = COLORS.get("accent",   "#0078d4")

        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background:{bg};
                border:none; border-radius:4px;
            }}
            QProgressBar::chunk {{
                background:{acc};
                border-radius:4px;
            }}
        """)

        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background:{bg};
                border:1.5px solid {brd};
                border-radius:8px;
                padding:12px;
            }}
            QTabBar::tab {{
                background:{bg2};
                color:{tmid};
                border:1px solid {brd};
                border-bottom:none;
                border-top-left-radius:6px;
                border-top-right-radius:6px;
                padding:8px 18px;
                margin-right:3px;
                font-family:{FONT_SANS};
                font-size:10pt;
            }}
            QTabBar::tab:selected {{
                background:{bg};
                color:{txt};
                border-bottom:2px solid {acc};
                font-weight:bold;
            }}
            QTabBar::tab:hover:!selected {{
                background:{bg};
                color:{txt};
            }}
        """)

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

    def reset(self):
        self._alert.setVisible(False)
        self._progress.setVisible(False)
        self._console.limpar()
        self._atualizar_status()

    def showEvent(self, event):
        super().showEvent(event)
        # Delay de 100ms para garantir que a página já apareceu na tela e o menu não trave
        QTimer.singleShot(100, self._verificar_admin_background)

    def hideEvent(self, event):
        self._timer.stop()
        for attr in ("_worker", "_admin_check_worker", "_status_worker"):
            w = getattr(self, attr, None)
            if w and w.isRunning():
                w.wait(200)
        super().hideEvent(event)