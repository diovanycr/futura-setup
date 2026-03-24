# =============================================================================
# FUTURA SETUP — Página: Atualização Completa do Sistema (MODO 03)
# Melhorias v3:
#   - _ConfirmDialog: confirmação antes de iniciar a atualização
# Melhorias v4:
#   - _ConfirmDialog removido — usa ConfirmDialog centralizado de ui/widgets.py
#   - keyPressEvent: Escape volta ao passo anterior
# Melhorias v5:
#   - Botões substituídos por _make_primary_btn/_make_secondary_btn (padrão visual correto)
# =============================================================================

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QButtonGroup, QScrollArea, QPushButton, QRadioButton,
)
from PyQt6.QtCore import pyqtSignal, Qt, QThread
from PyQt6.QtGui import QFont

from ui.widgets import (
    PageHeader, SectionHeader, AlertBox, ResultBox,
    ProgressBlock, LogConsole, StepIndicator, RadioRow,
    make_primary_btn, make_secondary_btn, btn_row, spacer, label, ConfirmDialog,
)
from ui.theme import COLORS, FONT_MONO, FONT_SANS
from ui.theme_manager import theme_manager
from core.atualizador import (
    AtualizacaoWorker, find_instalacoes, find_bancos, find_firebird_dir
)


STEP_NAMES = ["Instalação", "Banco", "Resumo", "Executando", "Concluído"]




# ── CARD DE PASTA ─────────────────────────────────────────────────────────────

class _PastaCard(QWidget):
    """Card visual melhorado para exibir cada pasta detectada."""

    def __init__(self, path: str, checked: bool = False, parent=None):
        super().__init__(parent)
        self._path    = path
        self._state   = "normal"
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("PastaCard")
        self.setMinimumHeight(52)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        # Ícone de pasta
        self._icon = QLabel("📁")
        self._icon.setObjectName("pc_icon")
        self._icon.setFixedSize(28, 28)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setFont(QFont(FONT_SANS, 14))

        # Textos
        info_lay = QVBoxLayout()
        info_lay.setSpacing(2)
        info_lay.setContentsMargins(0, 0, 0, 0)

        # Mostra só o nome da pasta em destaque e o caminho completo abaixo
        import os
        folder_name = os.path.basename(path.rstrip("\\/")) or path
        self._name_lbl = QLabel(folder_name)
        self._name_lbl.setObjectName("pc_name")
        self._name_lbl.setFont(QFont(FONT_MONO, 11, QFont.Weight.Bold))

        self._path_lbl = QLabel(path)
        self._path_lbl.setObjectName("pc_path")
        self._path_lbl.setFont(QFont(FONT_MONO, 9))

        info_lay.addWidget(self._name_lbl)
        info_lay.addWidget(self._path_lbl)

        info_w = QWidget()
        info_w.setLayout(info_lay)
        info_w.setStyleSheet("background: transparent; border: none;")

        # Radio button (oculto visualmente, mantido para lógica de grupo)
        self._radio = QRadioButton()
        self._radio.setChecked(checked)
        self._radio.setFixedSize(20, 20)
        self._radio.toggled.connect(self._upd)

        lay.addWidget(self._icon)
        lay.addWidget(info_w, 1)
        lay.addWidget(self._radio)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _=None):
        checked = self._radio.isChecked()
        if checked:
            bg     = COLORS["accent_dim"]
            border = COLORS["accent"]
            name_c = COLORS["accent"]
        elif self._state == "hover":
            bg     = COLORS["panel_hover"]
            border = COLORS["border_light"]
            name_c = COLORS["text"]
        else:
            bg     = COLORS["surface"]
            border = COLORS["border"]
            name_c = COLORS["text"]

        self.setStyleSheet(f"""
            QWidget#PastaCard {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 8px;
            }}
            QLabel#pc_icon {{ background: transparent; border: none; }}
            QLabel#pc_name {{ color: {name_c}; background: transparent; border: none; }}
            QLabel#pc_path {{ color: {COLORS['text_dim']}; background: transparent; border: none; }}
            QRadioButton {{
                background: transparent; border: none;
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
        """)

    def enterEvent(self, e):
        self._state = "hover"
        self._upd()

    def leaveEvent(self, e):
        self._state = "normal"
        self._upd()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._radio.setChecked(True)

    def radio(self) -> QRadioButton:
        return self._radio

    def isChecked(self) -> bool:
        return self._radio.isChecked()


# -- WORKERS DE DETECÇÃO -------------------------------------------------------

class _DetectarPastasWorker(QThread):
    finished = pyqtSignal(list)

    def run(self):
        self.finished.emit(find_instalacoes())


class _DetectarBancosWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, pasta: str, parent=None):
        super().__init__(parent)
        self._pasta = pasta

    def run(self):
        self.finished.emit(find_bancos(self._pasta))


# -- PAGE ATUALIZACAO ----------------------------------------------------------

class PageAtualizacao(QWidget):
    go_menu = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._worker:              AtualizacaoWorker | None     = None
        self._detect_pasta_worker: _DetectarPastasWorker | None = None
        self._detect_banco_worker: _DetectarBancosWorker | None = None
        self._pasta_sel:  str        = ""
        self._banco_sel:  str        = ""
        self._pastas:     list[str]  = []
        self._bancos:     list[dict] = []
        self._pasta_rows: list[RadioRow] = []
        self._banco_rows: list[RadioRow] = []
        self._pasta_group: QButtonGroup | None = None
        self._banco_group: QButtonGroup | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 36, 40, 36)
        lay.setSpacing(0)


        self._step_ind = StepIndicator(STEP_NAMES)
        content_lay.addWidget(self._step_ind)
        content_lay.addWidget(spacer(h=12))

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        content_lay.addWidget(self._stack)
        root.addWidget(content_w, 1)

        self._stack.addWidget(self._build_step1())
        self._stack.addWidget(self._build_step2())
        self._stack.addWidget(self._build_step3())
        self._stack.addWidget(self._build_step4())
        self._stack.addWidget(self._build_step5())

        self._go_step(0)

    def reset(self):
        for w in (self._detect_pasta_worker, self._detect_banco_worker):
            if w and w.isRunning():
                w.quit()
                w.wait(1000)
        self._detect_pasta_worker = None
        self._detect_banco_worker = None
        self._pasta_sel = ""
        self._banco_sel = ""
        self._pastas    = []
        self._bancos    = []
        self._go_step(0)

    # -- STEP 1 ----------------------------------------------------------------

    def _build_step1(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        lay.addWidget(SectionHeader("Instalação do Futura"))
        lay.addWidget(AlertBox(
            "⚠  Execute como Administrador para parar os serviços do Firebird corretamente.",
            "warn"
        ))
        lay.addWidget(spacer(h=4))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setMaximumHeight(260)
        scroll.setMinimumHeight(40)

        self._pasta_container = QWidget()
        self._pasta_container.setStyleSheet("background: transparent;")
        self._pasta_inner_lay = QVBoxLayout(self._pasta_container)
        self._pasta_inner_lay.setContentsMargins(0, 4, 4, 4)
        self._pasta_inner_lay.setSpacing(6)
        scroll.setWidget(self._pasta_container)
        lay.addWidget(scroll)

        self._pasta_status_lbl = label("Clique em 'DETECTAR' para buscar instalações.", COLORS["text_dim"], 11)
        lay.addWidget(self._pasta_status_lbl)

        self._pasta_prog = ProgressBlock("Detectando instalações...")
        self._pasta_prog.setVisible(False)
        lay.addWidget(self._pasta_prog)

        lay.addWidget(spacer(h=8))

        btn_detectar = make_primary_btn("▶  DETECTAR INSTALAÇÕES", 200)
        btn_detectar.clicked.connect(self._detectar_pastas)
        btn_proximo = make_primary_btn("▶  PRÓXIMO", 160)
        btn_proximo.clicked.connect(self._confirm_pasta)
        lay.addWidget(btn_row(btn_detectar, btn_proximo))

        lay.addStretch()
        return w

    def _detectar_pastas(self):
        if self._detect_pasta_worker and self._detect_pasta_worker.isRunning():
            return
        self._pasta_status_lbl.setVisible(False)
        self._pasta_prog.update(0, "Detectando instalações...", "Buscando Futura.ini nos drives...")
        self._pasta_prog.setVisible(True)
        for row in self._pasta_rows:
            self._pasta_inner_lay.removeWidget(row)
            row.deleteLater()
        self._pasta_rows.clear()
        if self._pasta_group is not None:
            self._pasta_group.deleteLater()
            self._pasta_group = None
        self._detect_pasta_worker = _DetectarPastasWorker(self)
        self._detect_pasta_worker.finished.connect(
            self._on_pastas_detectadas, Qt.ConnectionType.SingleShotConnection
        )
        self._detect_pasta_worker.start()

    def _on_pastas_detectadas(self, pastas: list):
        self._pastas = pastas
        self._pasta_prog.setVisible(False)
        self._pasta_status_lbl.setVisible(True)
        if not pastas:
            self._pasta_status_lbl.setText("Nenhuma instalação encontrada. Verifique se o Futura está instalado.")
            self._pasta_status_lbl.setStyleSheet(f"color: {COLORS['warn']};")
            return
        self._pasta_status_lbl.setText(f"{len(pastas)} instalação(ões) encontrada(s).")
        self._pasta_status_lbl.setStyleSheet(f"color: {COLORS['log_ok']};")
        self._pasta_group = QButtonGroup(self)
        for i, pasta in enumerate(pastas):
            row = _PastaCard(pasta, checked=(i == 0))
            self._pasta_group.addButton(row.radio(), i)
            self._pasta_inner_lay.addWidget(row)
            self._pasta_rows.append(row)
        if self._pasta_rows:
            self._pasta_sel = pastas[0]

    def _confirm_pasta(self):
        if not self._pasta_rows:
            self._detectar_pastas()
            return
        if self._pasta_group:
            idx = self._pasta_group.checkedId()
            if 0 <= idx < len(self._pastas):
                self._pasta_sel = self._pastas[idx]
        if not self._pasta_sel:
            return
        self._detectar_bancos()
        self._go_step(1)

    # -- STEP 2 ----------------------------------------------------------------

    def _build_step2(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        lay.addWidget(SectionHeader("Banco de Dados (.fdb)"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setMaximumHeight(280)

        self._banco_container = QWidget()
        self._banco_container.setStyleSheet("background: transparent;")
        self._banco_inner_lay = QVBoxLayout(self._banco_container)
        self._banco_inner_lay.setContentsMargins(0, 0, 0, 0)
        self._banco_inner_lay.setSpacing(8)
        scroll.setWidget(self._banco_container)
        lay.addWidget(scroll)

        self._banco_status_lbl = label("Aguardando seleção da instalação...", COLORS["text_dim"], 11)
        lay.addWidget(self._banco_status_lbl)

        self._banco_prog = ProgressBlock("Detectando bancos...")
        self._banco_prog.setVisible(False)
        lay.addWidget(self._banco_prog)

        lay.addWidget(spacer(h=8))

        btn_proximo = make_primary_btn("▶  PRÓXIMO", 160)
        btn_proximo.clicked.connect(self._confirm_banco)
        lay.addWidget(btn_row(btn_proximo))

        lay.addStretch()
        return w

    def _detectar_bancos(self):
        if self._detect_banco_worker and self._detect_banco_worker.isRunning():
            return
        for row in self._banco_rows:
            self._banco_inner_lay.removeWidget(row)
            row.deleteLater()
        self._banco_rows.clear()
        if self._banco_group is not None:
            self._banco_group.deleteLater()
            self._banco_group = None
        if not self._pasta_sel:
            return
        try:
            from core.logger import log as _log
            _log.prefs.add_pasta(self._pasta_sel)
        except Exception:
            pass
        self._banco_status_lbl.setVisible(False)
        self._banco_prog.update(0, "Detectando bancos...", f"Buscando .fdb em {self._pasta_sel}")
        self._banco_prog.setVisible(True)
        self._detect_banco_worker = _DetectarBancosWorker(self._pasta_sel, self)
        self._detect_banco_worker.finished.connect(
            self._on_bancos_detectados, Qt.ConnectionType.SingleShotConnection
        )
        self._detect_banco_worker.start()

    def _on_bancos_detectados(self, bancos: list):
        self._bancos = bancos
        self._banco_prog.setVisible(False)
        self._banco_status_lbl.setVisible(True)
        if not bancos:
            self._banco_status_lbl.setText("Nenhum banco .fdb encontrado na instalação selecionada.")
            self._banco_status_lbl.setStyleSheet(f"color: {COLORS['warn']};")
            return
        self._banco_status_lbl.setText(f"{len(bancos)} banco(s) encontrado(s).")
        self._banco_status_lbl.setStyleSheet(f"color: {COLORS['log_ok']};")
        self._banco_group = QButtonGroup(self)
        for i, b in enumerate(bancos):
            desc = f"Status: {b['status']} · Fonte: {b['fonte']}"
            row  = RadioRow(b["caminho"], desc, checked=(i == 0))
            self._banco_group.addButton(row.radio(), i)
            self._banco_inner_lay.addWidget(row)
            self._banco_rows.append(row)
        if self._banco_rows:
            self._banco_sel = bancos[0]["caminho"]

    def _confirm_banco(self):
        if not self._banco_rows:
            return
        if self._banco_group:
            idx = self._banco_group.checkedId()
            if 0 <= idx < len(self._bancos):
                self._banco_sel = self._bancos[idx]["caminho"]
        if not self._banco_sel:
            return
        self._update_resumo()
        self._go_step(2)

    # -- STEP 3 ----------------------------------------------------------------

    def _build_step3(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        lay.addWidget(SectionHeader("Resumo da Operação"))

        self._warn_box_at = QWidget()
        self._warn_box_at.setObjectName("WarnBoxAt")
        self._refresh_warn_box_style()
        wb_lay = QVBoxLayout(self._warn_box_at)
        wb_lay.setContentsMargins(20, 14, 20, 14)
        wb_lay.setSpacing(4)
        warn_t = QLabel("⚠  O processo irá:")
        warn_t.setFont(QFont(FONT_MONO, 11, QFont.Weight.Bold))
        warn_t.setStyleSheet(f"color: {COLORS['warn']}; background: transparent;")
        wb_lay.addWidget(warn_t)
        for linha in [
            "1. Parar os serviços do Firebird",
            "2. Renomear o banco para _temp.fdb",
            "3. Baixar Atualizador.exe e DLLs",
            "4. Configurar PESQUISA.INI",
            "5. Abrir o Atualizador em nova janela",
        ]:
            lbl = QLabel(linha)
            lbl.setFont(QFont(FONT_MONO, 10))
            lbl.setStyleSheet(f"color: {COLORS['text_mid']}; background: transparent;")
            wb_lay.addWidget(lbl)
        lay.addWidget(self._warn_box_at)

        self._resumo_box = QWidget()
        self._resumo_box.setObjectName("ResumoBoxAt")
        self._refresh_resumo_style()
        resumo_lay = QVBoxLayout(self._resumo_box)
        resumo_lay.setContentsMargins(20, 16, 20, 16)
        resumo_lay.setSpacing(8)
        self._resumo_labels = {}
        for campo in ["Instalação", "Banco", "Firebird"]:
            row_w = QWidget()
            row_w.setStyleSheet("background: transparent;")
            row = QHBoxLayout(row_w)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(16)
            k = QLabel(campo.upper())
            k.setFont(QFont(FONT_MONO, 10))
            k.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
            k.setFixedWidth(120)
            v = QLabel("—")
            v.setFont(QFont(FONT_MONO, 12))
            v.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
            v.setWordWrap(True)
            self._resumo_labels[campo] = v
            row.addWidget(k)
            row.addWidget(v, 1)
            resumo_lay.addWidget(row_w)
        lay.addWidget(self._resumo_box)
        lay.addWidget(spacer(h=8))

        btn_confirmar = make_primary_btn("✓  CONFIRMAR E ATUALIZAR", 220)
        btn_confirmar.clicked.connect(self._confirmar_atualizacao)
        lay.addWidget(btn_row(btn_confirmar))

        lay.addStretch()
        theme_manager.theme_changed.connect(self._refresh_resumo_style)
        theme_manager.theme_changed.connect(self._refresh_warn_box_style)
        return w

    def _refresh_warn_box_style(self, _mode: str = ""):
        self._warn_box_at.setStyleSheet(
            "QWidget#WarnBoxAt {"
            f"  background: {COLORS['warn_dim']};"
            f"  border: 1px solid {COLORS['warn']};"
            "  border-radius: 8px; }"
        )

    def _refresh_resumo_style(self, _mode: str = ""):
        self._resumo_box.setStyleSheet(f"""
            QWidget#ResumoBoxAt {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)

    def _update_resumo(self):
        firebird = find_firebird_dir() or "Não detectado"
        self._resumo_labels["Instalação"].setText(self._pasta_sel)
        self._resumo_labels["Banco"].setText(self._banco_sel)
        self._resumo_labels["Firebird"].setText(firebird)
        self._refresh_resumo_style()

    # -- STEP 4 ----------------------------------------------------------------

    def _build_step4(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        lay.addWidget(SectionHeader("Executando Atualização"))
        self._prog_block = ProgressBlock("Iniciando...")
        lay.addWidget(self._prog_block)
        lay.addWidget(spacer(h=4))
        self._at_console = LogConsole(max_height=280)
        lay.addWidget(self._at_console)
        lay.addStretch()
        return w

    # -- STEP 5 ----------------------------------------------------------------

    def _build_step5(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        self._done_lay = QVBoxLayout(w)
        self._done_lay.setContentsMargins(0, 0, 0, 0)
        self._done_lay.setSpacing(12)
        self._done_lay.addStretch()
        return w

    def _show_done(self, sucesso: bool, resumo: dict):
        while self._done_lay.count():
            item = self._done_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        kind   = "success" if sucesso else "error"
        titulo = "Atualização Preparada com Sucesso" if sucesso else "Falha na Atualização"
        if sucesso:
            rows = [
                ("Instalação",  resumo.get("pasta",  "—")),
                ("Banco",       resumo.get("banco",   "—")),
                ("DLLs",        resumo.get("dlls",    "—")),
                ("INI",         resumo.get("ini",     "—")),
                ("Atualizador", "Iniciado em nova janela"),
            ]
        else:
            rows = [("Erro", resumo.get("erro", "Erro desconhecido"))]

        self._done_lay.addWidget(ResultBox(titulo, rows, kind))
        self._done_lay.addWidget(spacer(h=8))

        btns = []
        if not sucesso:
            btn_retry = make_primary_btn("↺  TENTAR NOVAMENTE", 200)
            btn_retry.clicked.connect(self.reset)
            btns.append(btn_retry)
        self._done_lay.addWidget(btn_row(*btns))
        self._done_lay.addStretch()

    # -- ATUALIZAÇÃO -----------------------------------------------------------

    def _confirmar_atualizacao(self):
        firebird = find_firebird_dir() or "Não detectado"
        dlg = ConfirmDialog(
            "⚠  Confirmar início da atualização?",
            [
                f"Instalação:  {self._pasta_sel}",
                f"Banco:       {self._banco_sel}",
                f"Firebird:    {firebird}",
                "",
                "O Firebird será parado, o banco renomeado temporariamente",
                "e o Atualizador será baixado e executado.",
            ],
            parent=self,
            largura=480,
        )
        dlg.exec()
        if dlg.confirmado():
            self._start_atualizacao()

    def _start_atualizacao(self):
        self._at_console.clear_console()
        self._prog_block.update(0, "Iniciando...", "Preparando atualização...")
        self._go_step(3)
        self._worker = AtualizacaoWorker(
            pasta_escolhida=self._pasta_sel,
            banco_escolhido=self._banco_sel,
        )
        self._worker.log_line.connect(self._at_console.append_line)
        self._worker.progress.connect(lambda p, t, s: self._prog_block.update(p, t, s))
        self._worker.precisa_pasta.connect(self._on_precisa_pasta)
        self._worker.precisa_banco.connect(self._on_precisa_banco)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_precisa_pasta(self, pastas: list[str]):
        self._pastas = pastas
        self._go_step(0)
        self._detectar_pastas()

    def _on_precisa_banco(self, bancos: list[dict]):
        self._bancos = bancos
        self._go_step(1)
        self._detectar_bancos()

    def _on_finished(self, sucesso: bool, resumo: dict):
        self._step_ind.set_step(len(STEP_NAMES))
        self._show_done(sucesso, resumo)
        self._stack.setCurrentIndex(4)

    # -- NAVEGAÇÃO -------------------------------------------------------------

    def _go_step(self, idx: int):
        self._stack.setCurrentIndex(idx)
        self._step_ind.set_step(idx)

    def _on_back_clicked(self):
        idx = self._stack.currentIndex()
        back_map = {
            0: self.go_menu.emit,
            1: lambda: self._go_step(0),
            2: lambda: self._go_step(1),
            3: self.go_menu.emit,
            4: self.go_menu.emit,
        }
        action = back_map.get(idx)
        if action:
            if callable(action): action()
            else: action.emit()

    # ── TECLADO ───────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            idx = self._stack.currentIndex()
            back_map = {
                0: self.go_menu.emit,
                1: lambda: self._go_step(0),
                2: lambda: self._go_step(1),
            }
            action = back_map.get(idx)
            if action:
                action()
        else:
            super().keyPressEvent(event)
