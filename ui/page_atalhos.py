# =============================================================================
# FUTURA SETUP — Página: Atalhos via Rede (MODO 01)
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
    QLabel, QGridLayout, QStackedWidget, QFileDialog, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
import datetime
import platform
import os
from ui.widgets import (
    PageTitle, SectionHeader, AlertBox, ResultBox,
    LogConsole, ProgressBlock, StepIndicator,
    MiniFileItem, DestPanel, make_btn, make_btn_row, spacer, label
)
from ui.theme import COLORS, FONT_MONO
from ui.theme_manager import theme_manager
from core.network import Servidor
from core.installer import listar_executaveis, AtalhosWorker

# ── HELPERS DE BOTÃO (estilo inline garantido) ────────────────────────────────

from PyQt6.QtWidgets import QPushButton

def _make_primary_btn(text: str, min_width: int = 160) -> QPushButton:
    btn = QPushButton(text)
    btn.setMinimumWidth(min_width)
    btn.setMinimumHeight(36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    from PyQt6.QtGui import QFont as _QFont
    btn.setFont(_QFont("Segoe UI", 13, _QFont.Weight.Bold))
    _apply_primary(btn)
    theme_manager.theme_changed.connect(lambda _: _apply_primary(btn))
    return btn

def _make_secondary_btn(text: str, min_width: int = 120) -> QPushButton:
    btn = QPushButton(text)
    btn.setMinimumWidth(min_width)
    btn.setMinimumHeight(36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    _apply_secondary(btn)
    theme_manager.theme_changed.connect(lambda _: _apply_secondary(btn))
    return btn

def _apply_primary(btn: QPushButton):
    text_color = "#ffffff" if theme_manager.mode == "light" else "#001826"
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {COLORS["accent"]};
            color: {text_color};
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-weight: 700;
            font-size: 13px;
        }}
        QPushButton:hover {{ background-color: {COLORS["accent_hover"]}; }}
        QPushButton:pressed {{ background-color: {COLORS["accent_press"]}; }}
        QPushButton:disabled {{
            background-color: {COLORS["panel_hover"]};
            color: {COLORS["text_disabled"]};
        }}
    """)

def _apply_secondary(btn: QPushButton):
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: transparent;
            color: {COLORS["text"]};
            border: 1.5px solid {COLORS["btn_border"]};
            border-radius: 6px;
            padding: 8px 20px;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {COLORS["panel_hover"]};
            border-color: {COLORS["text_dim"]};
        }}
        QPushButton:pressed {{ background-color: {COLORS["panel_press"]}; }}
    """)


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

        root.addWidget(PageTitle("MODO 01", "Puxar Atalhos via Rede"))

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
        self._sel_all_btn = make_btn("☑  Selecionar Todos", min_width=150)
        self._sel_all_btn.clicked.connect(self._toggle_all)
        hdr.addWidget(self._sel_all_btn)
        hdr_w = QWidget()
        hdr_w.setLayout(hdr)
        hdr_w.setStyleSheet("background: transparent;")
        lay.addWidget(hdr_w)
        lay.addWidget(spacer(h=4))

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
        btn_proximo = _make_primary_btn("▶  PRÓXIMO", 160)
        btn_proximo.clicked.connect(self._confirm_apps)
        btn_voltar = _make_secondary_btn("← VOLTAR", 120)
        btn_voltar.clicked.connect(self.go_menu.emit)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addStretch()
        btns.addWidget(btn_proximo)
        btns.addWidget(btn_voltar)
        btns.addStretch()

        btn_w = QWidget()
        btn_w.setLayout(btns)
        btn_w.setStyleSheet("background: transparent;")
        lay.addWidget(spacer(h=16))
        lay.addWidget(btn_w)
        return w

    # ── STEP 2: Destino ───────────────────────────────────────────────────────

    def _build_step2(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        lay.addWidget(SectionHeader("Resumo da Seleção"))

        self._resumo_box = QWidget()
        self._resumo_box.setObjectName("ResumoBoxAt1")
        self._resumo_labels: dict[str, QLabel] = {}
        self._refresh_resumo_style()

        resumo_lay = QVBoxLayout(self._resumo_box)
        resumo_lay.setContentsMargins(20, 16, 20, 16)
        resumo_lay.setSpacing(8)

        for campo in ["Servidor", "Selecionados"]:
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
        lay.addWidget(spacer(h=4))

        lay.addWidget(SectionHeader("Local de Criação"))
        lay.addWidget(spacer(h=6))
        self._dest_panel = DestPanel()
        lay.addWidget(self._dest_panel)
        lay.addWidget(spacer(h=12))

        lay.addStretch()  # empurra botões para o rodapé

        btn_criar = _make_primary_btn("▶  CRIAR ATALHOS", 180)
        btn_criar.clicked.connect(self._run)
        btn_voltar = _make_secondary_btn("← VOLTAR", 120)
        btn_voltar.clicked.connect(lambda: self._go_step(0))

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addStretch()
        btns.addWidget(btn_criar)
        btns.addWidget(btn_voltar)
        btns.addStretch()

        btn_w = QWidget()
        btn_w.setLayout(btns)
        btn_w.setStyleSheet("background: transparent;")
        lay.addWidget(btn_w)

        theme_manager.theme_changed.connect(self._refresh_resumo_style)
        return w

    def _refresh_resumo_style(self, _mode: str = ""):
        self._resumo_box.setStyleSheet(f"""
            QWidget#ResumoBoxAt1 {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)

    def _update_resumo(self):
        selecionados = sum(1 for i in self._file_items if i.is_checked())
        self._resumo_labels["Servidor"].setText(
            self._servidor.display if self._servidor else "—"
        )
        self._resumo_labels["Selecionados"].setText(f"{selecionados} aplicativo(s)")
        self._refresh_resumo_style()

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
            "modo":     "01 — Puxar via Rede",
            "titulo":   titulo,
            "sucesso":  sucesso,
            "campos":   rows,
        }

        # ── Botões com estilo correto (padrão das outras telas) ──
        btn_menu = _make_primary_btn("← MENU PRINCIPAL", 200)
        btn_menu.clicked.connect(self.go_menu.emit)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addWidget(btn_menu)

        if sucesso:
            btn_relatorio = _make_secondary_btn("💾  Salvar Relatório", 180)
            btn_relatorio.clicked.connect(
                lambda: self._exportar_relatorio(self._ultimo_relatorio)
            )
            btns.addWidget(btn_relatorio)

        if not sucesso:
            btn_retry = _make_primary_btn("↺  TENTAR NOVAMENTE", 200)
            btn_retry.clicked.connect(lambda: self._go_step(0))
            btns.addWidget(btn_retry)

        btns.addStretch()

        btn_w = QWidget()
        btn_w.setLayout(btns)
        btn_w.setStyleSheet("background: transparent;")

        self._done_lay.addWidget(ResultBox(titulo, rows, kind))
        self._done_lay.addWidget(spacer(h=8))
        self._done_lay.addWidget(btn_w)
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
            item.set_checked(False)  # ← inicia desmarcado
            self._files_grid.addWidget(item, *divmod(idx, 2))
            self._file_items.append(item)

    def _toggle_all(self):
        todos = all(i.is_checked() for i in self._file_items)
        for item in self._file_items:
            item.set_checked(not todos)
        self._sel_all_btn.setText(
            "☐  Desmarcar Todos" if not todos else "☑  Selecionar Todos"
        )

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
