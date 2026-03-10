# =============================================================================
# FUTURA SETUP — Página: Atalhos via Rede
# Melhorias v2:
#   - theme_manager importado no topo (sem import tardio dentro de _build_step2)
#   - theme_changed conectado com self._refresh_resumo_style diretamente
#   - QVBoxLayout / QHBoxLayout importados no topo (sem alias interno _VL/_HL)
# Melhorias v3:
#   - Step1: scroll de aplicativos expande para preencher espaço disponível
#   - Step1: botões fixos no rodapé (mesmo padrão da tela de resultados do scan)
# Melhorias v4:
#   - _carregar_executaveis: itens iniciam desmarcados (set_checked(False))
#   - _toggle_all: texto do botão alterna entre "Selecionar Todos"/"Desmarcar Todos"
#   - _show_done: botões usam _make_primary_btn/_make_secondary_btn (padrão visual correto)
# =============================================================================

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QGridLayout, QStackedWidget, QFileDialog, QSizePolicy, QLineEdit, QFrame,
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QFont
import datetime
import platform
import os
from ui.widgets import (
    PageTitle, SectionHeader, AlertBox, ResultBox,
    LogConsole, ProgressBlock, StepIndicator,
    MiniFileItem, DestPanel, make_primary_btn, make_secondary_btn,
    btn_row, spacer, label
)
from ui.theme import COLORS, FONT_MONO
from ui.theme_manager import theme_manager
from core.network import Servidor
from core.installer import listar_executaveis, AtalhosWorker



STEP_NAMES = ["Aplicativos", "Destino", "Executando", "Concluído"]


class PageAtalhos(QWidget):
    go_menu = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._servidor: Servidor | None      = None
        self._file_items: list[MiniFileItem] = []
        self._worker: AtalhosWorker | None   = None

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 36)
        root.setSpacing(0)

        self._search_text = ""

        root.addWidget(PageTitle("ATALHOS", "Puxar Atalhos via Rede"))

        self._step_ind = StepIndicator(STEP_NAMES)
        root.addWidget(self._step_ind)
        root.addWidget(spacer(h=12))

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        root.addWidget(self._stack)

        self._stack.addWidget(self._build_step1())  # 0 — Aplicativos
        self._stack.addWidget(self._build_step2())  # 1 — Destino
        self._stack.addWidget(self._build_step3())  # 2 — Executando
        self._stack.addWidget(self._build_step4())  # 3 — Concluído

        self._go_step(0)

    # ── STEP 1: Aplicativos ───────────────────────────────────────────────────

    def _build_step1(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._alert = AlertBox("Selecione o servidor primeiro.", "info")
        lay.addWidget(self._alert)
        lay.addWidget(spacer(h=16))

        hdr = QHBoxLayout()
        hdr.addWidget(SectionHeader("Aplicativos Disponíveis"))
        hdr.addStretch()
        self._sel_all_btn = make_secondary_btn("☐  Selecionar Todos", min_width=150)
        self._sel_all_btn.clicked.connect(self._toggle_all)
        hdr.addWidget(self._sel_all_btn)
        hdr_w = QWidget()
        hdr_w.setLayout(hdr)
        hdr_w.setStyleSheet("background: transparent;")
        lay.addWidget(hdr_w)
        lay.addWidget(spacer(h=12))

        # Search and Counter Row
        search_lay = QHBoxLayout()
        search_lay.setSpacing(12)
        
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍  Buscar aplicativo...")
        self._search_input.setMinimumHeight(32)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
                color: {COLORS['text']};
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """)
        self._search_input.textChanged.connect(self._on_search)
        
        self._counter_lbl = QLabel("0 selecionados")
        self._counter_lbl.setFont(QFont(FONT_MONO, 10, QFont.Weight.Bold))
        self._counter_lbl.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        
        search_lay.addWidget(self._search_input, 1)
        search_lay.addWidget(self._counter_lbl)
        
        search_w = QWidget()
        search_w.setLayout(search_lay)
        lay.addWidget(search_w)
        lay.addWidget(spacer(h=8))

        # Scroll expande para ocupar todo espaço disponível acima dos botões
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._files_container = QWidget()
        self._files_container.setStyleSheet("background: transparent;")
        self._files_grid = QGridLayout(self._files_container)
        self._files_grid.setContentsMargins(0, 0, 4, 0)
        self._files_grid.setHorizontalSpacing(6)
        self._files_grid.setVerticalSpacing(6)
        self._files_grid.setColumnStretch(0, 1)
        self._files_grid.setColumnStretch(1, 1)
        scroll.setWidget(self._files_container)
        lay.addWidget(scroll, 1)  # stretch=1 — ocupa todo espaço restante

        # Botões fixos no rodapé
        btn_proximo = make_primary_btn("▶  PRÓXIMO", 160)
        btn_proximo.clicked.connect(self._confirm_apps)
        btn_voltar = make_secondary_btn("← VOLTAR", 120)
        btn_voltar.clicked.connect(self.go_menu.emit)

        lay.addWidget(spacer(h=16))
        lay.addWidget(btn_row(btn_proximo, btn_voltar))
        return w

    # ── STEP 2: Destino ───────────────────────────────────────────────────────

    def _build_step2(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        lay.addWidget(SectionHeader("Resumo da Seleção"))

        self._res_card = QFrame()
        self._res_card.setObjectName("ResumoCardAt")
        self._res_card.setStyleSheet(f"""
            QFrame#ResumoCardAt {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        gl = QGridLayout(self._res_card)
        gl.setContentsMargins(24, 20, 24, 20)
        gl.setSpacing(16)

        self._resumo_labels = {}
        for i, campo in enumerate(["Servidor", "Selecionados"]):
            k = QLabel(campo.upper())
            k.setFont(QFont(FONT_MONO, 10, QFont.Weight.Bold))
            k.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
            v = QLabel("—")
            v.setFont(QFont(FONT_MONO, 11))
            v.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
            v.setWordWrap(True)
            gl.addWidget(k, i, 0)
            gl.addWidget(v, i, 1)
            self._resumo_labels[campo] = v

        lay.addWidget(self._res_card)
        lay.addWidget(spacer(h=12))

        lay.addWidget(SectionHeader("Local de Criação"))
        lay.addWidget(spacer(h=6))
        self._dest_panel = DestPanel()
        lay.addWidget(self._dest_panel)
        lay.addWidget(spacer(h=16))

        btn_criar = make_primary_btn("▶  CRIAR ATALHOS", 180)
        btn_criar.clicked.connect(self._run)
        btn_voltar = make_secondary_btn("← VOLTAR", 120)
        btn_voltar.clicked.connect(lambda: self._go_step(0))

        lay.addWidget(btn_row(btn_criar, btn_voltar))
        lay.addStretch()
        return w

    def _update_resumo(self):
        selecionados = sum(1 for i in self._file_items if i.is_checked())
        self._resumo_labels["Servidor"].setText(
            self._servidor.hostname if self._servidor else "—"
        )
        self._resumo_labels["Selecionados"].setText(f"{selecionados} aplicativo(s)")

    # ── STEP 3: Executando ────────────────────────────────────────────────────

    def _build_step3(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        lay.addWidget(SectionHeader("Criando Atalhos..."))

        self._prog_block = ProgressBlock("Criando atalhos...")
        lay.addWidget(self._prog_block)
        lay.addWidget(spacer(h=4))

        self._console = LogConsole(max_height=280)
        lay.addWidget(self._console)
        lay.addStretch()
        return w

    # ── STEP 4: Concluído ─────────────────────────────────────────────────────

    def _build_step4(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        self._done_lay = QVBoxLayout(w)
        self._done_lay.setContentsMargins(0, 0, 0, 0)
        self._done_lay.setSpacing(12)
        self._done_lay.addStretch()
        return w

    def _show_done(self, sucesso: bool, criados: int, falhos: int, cancelado: bool = False):
        while self._done_lay.count():
            item = self._done_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        dest_id  = self._dest_panel.selected_id()
        dest_txt = {0: "Desktop + Menu Iniciar", 1: "Desktop", 2: "Menu Iniciar"}.get(dest_id, "—")
        kind   = "success" if sucesso else "warn" if cancelado else "error"
        titulo = ("Atalhos Criados com Sucesso" if sucesso
                  else "Operação Cancelada" if cancelado
                  else "Falha ao Criar Atalhos")
        rows   = [
            ("Servidor",   self._servidor.display if self._servidor else "—"),
            ("Criados",    f"{criados} atalho(s)"),
            ("Falhos",     str(falhos)),
            ("Destino",    dest_txt),
        ]

        self._ultimo_relatorio = {
            "modo":     "Atalhos via Rede",
            "titulo":   titulo,
            "sucesso":  sucesso,
            "campos":   rows,
        }

        # ── Botões ──
        btn_menu = make_primary_btn("← MENU PRINCIPAL", 200)
        btn_menu.clicked.connect(self.go_menu.emit)

        if sucesso:
            btn_relatorio = make_secondary_btn("💾  Salvar Relatório", 180)
            btn_relatorio.clicked.connect(
                lambda: self._exportar_relatorio(self._ultimo_relatorio)
            )
        else:
            btn_relatorio = None

        if not sucesso and not cancelado:
            btn_retry = make_primary_btn("↺  TENTAR NOVAMENTE", 200)
            btn_retry.clicked.connect(lambda: self._go_step(0))
        else:
            btn_retry = None

        self._done_lay.addWidget(ResultBox(titulo, rows, kind))
        self._done_lay.addWidget(spacer(h=8))
        self._done_lay.addWidget(btn_row(btn_menu, *([btn_relatorio] if btn_relatorio else []), *([btn_retry] if btn_retry else [])))
        self._done_lay.addStretch()

    def _exportar_relatorio(self, dados: dict):
        now      = datetime.datetime.now()
        hostname = platform.node()
        nome_sug = f"relatorio_atalhos_{now.strftime('%Y%m%d_%H%M%S')}.txt"

        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Relatório", nome_sug, "Texto (*.txt)"
        )
        if not path:
            return

        linhas = [
            "=" * 60,
            "  FUTURA SETUP — Relatório de Operação",
            "=" * 60,
            f"  Modo:        {dados.get('modo', '—')}",
            f"  Data/Hora:   {now.strftime('%d/%m/%Y %H:%M:%S')}",
            f"  Máquina:     {hostname}",
            f"  Resultado:   {'SUCESSO' if dados.get('sucesso') else 'FALHA/CANCELADO'}",
            "",
            "  Detalhes:",
        ]
        for chave, valor in dados.get("campos", []):
            if chave:
                linhas.append(f"    {chave:<18} {valor}")
            else:
                linhas.append(f"    {valor}")
        linhas += ["", "=" * 60, ""]

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(linhas))
        except Exception:
            pass

    # ── SERVIDOR / ARQUIVOS ───────────────────────────────────────────────────

    def set_servidor(self, srv: Servidor):
        self._servidor = srv
        self._alert.set_text(
            f"Servidor: <b>{srv.hostname}</b> — IP: {srv.ip} — {srv.path}"
        )
        self._carregar_executaveis()
        self._go_step(0)

    def _carregar_executaveis(self):
        while self._files_grid.count():
            w = self._files_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._file_items.clear()

        if not self._servidor:
            return

        exes = listar_executaveis(self._servidor.path)
        if not exes:
            self._files_grid.addWidget(
                label("Nenhum executável encontrado.", COLORS["warn"], 11), 0, 0, 1, 2
            )
            return

        for idx, exe in enumerate(exes):
            item = MiniFileItem(exe["nome"])
            item.set_checked(False)
            item.toggled.connect(self._update_counter)
            self._files_grid.addWidget(item, *divmod(idx, 2))
            self._file_items.append(item)
        
        self._update_counter()

    def _on_search(self, text: str):
        self._search_text = text.lower()
        self._refiltrar_grid()

    def _refiltrar_grid(self):
        # Remove todos do grid
        for i in range(self._files_grid.count()):
            self._files_grid.itemAt(i).widget().hide()
        
        # Filtra e readiciona
        visiveis = [i for i in self._file_items if self._search_text in i.name.lower()]
        
        for idx, item in enumerate(visiveis):
            self._files_grid.addWidget(item, *divmod(idx, 2))
            item.show()

    def _update_counter(self):
        sel = sum(1 for i in self._file_items if i.is_checked())
        self._counter_lbl.setText(f"{sel} selecionado(s)")
        
        # Se a lista estiver vazia, ou nem todos marcados: icon '☐', text 'Selecionar'
        # Se todos marcados (e lista não-vazia): icon '☑', text 'Desmarcar'
        todos = all(i.is_checked() for i in self._file_items) if self._file_items else False
        
        self._sel_all_btn.setText(
            "☑  Desmarcar Todos" if todos else "☐  Selecionar Todos"
        )

    def _toggle_all(self):
        if not self._file_items: return
        todos = all(i.is_checked() for i in self._file_items)
        # Se já estavam todos marcados, vamos desmarcar. Senão, marca tudo.
        for item in self._file_items:
            item.set_checked(not todos)
        self._update_counter()

    def _confirm_apps(self):
        if not any(i.is_checked() for i in self._file_items):
            self._alert.set_text("⚠  Selecione ao menos um aplicativo para continuar.")
            self._alert.set_kind("warn")
            return
        self._alert.set_kind("info")
        self._update_resumo()
        self._go_step(1)

    # ── EXECUTAR ──────────────────────────────────────────────────────────────

    def _run(self):
        if not self._servidor:
            return

        exes    = listar_executaveis(self._servidor.path)
        exe_map = {e["nome"]: e for e in exes}
        selecionados = [
            exe_map[item.name]
            for item in self._file_items
            if item.is_checked() and item.name in exe_map
        ]

        if not selecionados:
            return

        dest_id = self._dest_panel.selected_id()
        desktop = dest_id in (0, 1)
        start_m = dest_id in (0, 2)

        self._console.clear_console()
        self._prog_block.update(0, "Iniciando...", "Preparando criação de atalhos...")
        self._go_step(2)

        self._worker = AtalhosWorker(selecionados, desktop, start_m)
        self._worker.log_line.connect(self._console.append_line)
        self._worker.progress.connect(
            lambda pct, nome, sub: self._prog_block.update(pct, nome, sub)
        )
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, sucesso: bool, criados: int, falhos: int):
        self._worker = None
        self._step_ind.set_step(len(STEP_NAMES))
        cancelado = not sucesso and criados == 0 and falhos == 0
        self._show_done(sucesso, criados, falhos, cancelado)
        self._stack.setCurrentIndex(3)

    # ── NAVEGAÇÃO ─────────────────────────────────────────────────────────────

    def _go_step(self, idx: int):
        self._stack.setCurrentIndex(idx)
        self._step_ind.set_step(idx)

    # ── TECLADO ───────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            idx = self._stack.currentIndex()
            if idx == 0:
                self.go_menu.emit()
            elif idx == 1:
                self._go_step(0)
        else:
            super().keyPressEvent(event)
