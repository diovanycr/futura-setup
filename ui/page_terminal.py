# =============================================================================
# FUTURA SETUP — Página: Novo Terminal
# Melhorias v2:
#   - AlertBox importado no topo (sem import tardio dentro de _start_install)
#   - os.path.join / os.path.exists / os.path.basename → Path (consistente)
#   - theme_changed conectado com self._refresh_resumo_style diretamente
#   - _upd_custom_style conectado a theme_changed para seguir troca de tema
# Melhorias v5:
#   - Botões substituídos por _make_primary_btn/_make_secondary_btn (padrão visual correto)
#   - Posicionamento dos botões alinhado com as demais telas
# Melhorias v6:
#   - Botão de pasta 📁 substituiu o radio button visível na opção "Outro caminho"
#   - Radio button mantido invisível no grupo para controle lógico
# =============================================================================

from pathlib import Path
import datetime
import platform
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QLineEdit, QScrollArea, QButtonGroup, QRadioButton,
    QGridLayout, QFileDialog, QPushButton, QFrame, QDialog,
)
from PyQt6.QtCore import pyqtSignal, Qt, QByteArray, QRectF, pyqtProperty, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer

from ui.widgets import (
    PageTitle, SectionHeader, AlertBox, ResultBox, ProgressBlock,
    LogConsole, StepIndicator, MiniFileItem, DestPanel, RadioRow,
    CustomPathCard, ProcessCard, FadeStackedWidget, make_primary_btn,
    make_secondary_btn, btn_row, spacer, label, card_style
)
from ui.theme import COLORS, FONT_MONO, FONT_SANS
from ui.theme_manager import theme_manager
from core.network import Servidor
from core.installer import (
    InstalacaoWorker, listar_executaveis, listar_processos_na_pasta,
    encerrar_processos, espaco_livre_mb, formatar_tamanho
)


STEP_NAMES = ["Pasta", "Resumo", "Processos", "Backup", "Servidor",
              "Arquivos", "DLLs", "Atalhos"]




class PageTerminal(QWidget):
    go_menu = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._servidor: Servidor | None       = None
        self._pasta       = "C:\\FUTURA"
        self._file_items: list[MiniFileItem] = []
        self._worker: InstalacaoWorker | None = None
        self._processos: list[dict]           = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 36, 40, 36)
        lay.setSpacing(0)

        lay.addWidget(PageTitle("TERMINAL", "Novo Terminal"))
        self._search_text = ""

        self._step_ind = StepIndicator(STEP_NAMES)
        lay.addWidget(self._step_ind)
        lay.addWidget(spacer(h=12))

        self._stack = FadeStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        lay.addWidget(self._stack)

        self._stack.addWidget(self._build_step1())  # 0 — Pasta
        self._stack.addWidget(self._build_step2())  # 1 — Resumo
        self._stack.addWidget(self._build_step3())  # 2 — Processos
        self._stack.addWidget(self._build_step4())  # 3 — Arquivos
        self._stack.addWidget(self._build_step5())  # 4 — Progresso
        self._stack.addWidget(self._build_step6())  # 5 — Concluído

        self._go_step(0)

    def set_servidor(self, srv: Servidor):
        self._servidor = srv
        self._go_step(0)

    # ── STEP 1: Pasta de Instalação ───────────────────────────────────────────

    def _build_step1(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        lay.addWidget(SectionHeader("Pasta de Instalação"))

        self._pasta_group  = QButtonGroup(w)
        self._radio_rows: list[RadioRow] = []

        for i, (path, desc) in enumerate([
            ("C:\\FUTURA",         "Padrão recomendado"),
            ("C:\\FuturaTerminal", "Alternativa padrão"),
        ]):
            row = RadioRow(path, desc, checked=(i == 0))
            self._pasta_group.addButton(row.radio(), i)
            lay.addWidget(row)
            self._radio_rows.append(row)

        lay.addWidget(spacer(h=4))

        # Opção personalizada
        self._custom_card = CustomPathCard("Outro caminho")
        self._pasta_group.addButton(self._custom_card.radio(), 2)
        self._custom_card.btn_folder().clicked.connect(self._abrir_explorer)
        self._custom_card.input_field().mousePressEvent = lambda _: self._abrir_explorer()
        lay.addWidget(self._custom_card)

        lay.addWidget(spacer(h=24))

        # Botões
        btn_proximo = make_primary_btn("▶  PRÓXIMO", 180)
        btn_proximo.clicked.connect(self._confirm_pasta)
        btn_voltar = make_secondary_btn("← VOLTAR", 120)
        btn_voltar.clicked.connect(self.go_menu.emit)

        lay.addWidget(btn_row(btn_proximo, btn_voltar))
        lay.addStretch()
        return w

    def _abrir_explorer(self):
        self._custom_card.radio().setChecked(True)
        pasta_atual = self._custom_card.path().strip() or "C:\\"
        pasta = QFileDialog.getExistingDirectory(None, "Selecionar pasta de instalação", pasta_atual)
        if pasta:
            self._custom_card.set_path(pasta.replace("/", "\\"))



    def _confirm_pasta(self):
        idx = self._pasta_group.checkedId()
        if idx == 0:
            self._pasta = "C:\\FUTURA"
        elif idx == 1:
            self._pasta = "C:\\FuturaTerminal"
        else:
            custom = self._custom_card.path().strip()
            if not custom:
                self._abrir_explorer()
                custom = self._custom_card.path().strip()
                if not custom: return
            self._pasta = custom.rstrip("\\")
        self._update_resumo()
        self._go_step(1)

    # ── STEP 2: Resumo ────────────────────────────────────────────────────────

    def _build_step2(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        lay.addWidget(SectionHeader("Resumo da Operação"))

        self._resumo_card = QFrame()
        self._resumo_card.setObjectName("ResumoCard")
        self._resumo_card.setStyleSheet(f"""
            QFrame#ResumoCard {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        
        res_lay = QGridLayout(self._resumo_card)
        res_lay.setContentsMargins(24, 20, 24, 20)
        res_lay.setSpacing(16)

        self._resumo_labels = {}
        campos = [
            ("Modo", "TERMINAL"),
            ("Servidor", "—"),
            ("Caminho", "—"),
            ("Pasta", "—"),
            ("Espaço Livre", "—"),
        ]

        for i, (k, v_init) in enumerate(campos):
            kl = QLabel(k.upper())
            kl.setFont(QFont(FONT_MONO, 10, QFont.Weight.Bold))
            kl.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
            
            vl = QLabel(v_init)
            vl.setFont(QFont(FONT_MONO, 11))
            vl.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
            vl.setWordWrap(True)
            
            res_lay.addWidget(kl, i, 0)
            res_lay.addWidget(vl, i, 1)
            self._resumo_labels[k] = vl

        lay.addWidget(self._resumo_card)
        lay.addWidget(spacer(h=16))

        # Botões
        btn_proximo = make_primary_btn("▶  INICIAR INSTALAÇÃO", 220)
        btn_proximo.clicked.connect(lambda: self._go_step(2))
        btn_voltar = make_secondary_btn("← VOLTAR", 120)
        btn_voltar.clicked.connect(lambda: self._go_step(0))

        lay.addWidget(btn_row(btn_proximo, btn_voltar))
        lay.addStretch()

        return w


    def _update_resumo(self):
        if not self._servidor:
            return
        espaco = espaco_livre_mb(self._pasta)
        aviso  = "  ⚠ Pouco espaço!" if espaco < 500 else ""
        self._resumo_labels["Servidor"].setText(self._servidor.nome)
        self._resumo_labels["Caminho"].setText(self._servidor.caminho)
        self._resumo_labels["Pasta"].setText(self._pasta)
        self._resumo_labels["Espaço Livre"].setText(f"{espaco:.1f} MB disponíveis{aviso}")

    # ── STEP 3: Processos em Execução ─────────────────────────────────────────

    def _build_step3(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        self._step3_lay = QVBoxLayout(w)
        self._step3_lay.setContentsMargins(0, 0, 0, 0)
        self._step3_lay.setSpacing(8)
        self._step3_lay.addStretch()
        return w

    def _check_processos(self):
        while self._step3_lay.count():
            item = self._step3_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._processos = listar_processos_na_pasta(self._pasta)
        self._step3_lay.addWidget(SectionHeader("Processos em Execução"))

        if not self._processos:
            box = ResultBox("Nenhum Processo Ativo", [
                ("Status", "Nenhum processo Futura em execução na pasta de destino.")
            ], "success")
            self._step3_lay.addWidget(box)
            self._step3_lay.addWidget(spacer(h=16))

            btn_proximo = _make_primary_btn("▶  PRÓXIMO", 180)
            btn_proximo.clicked.connect(lambda: self._go_step(3))
            btn_voltar = _make_secondary_btn("← VOLTAR", 120)
            btn_voltar.clicked.connect(lambda: self._go_step(1))
            self._step3_lay.addWidget(_btn_row(btn_proximo, btn_voltar))
        else:
            alert = AlertBox(
                f"{len(self._processos)} processo(s) em execução na pasta de destino. "
                "Eles serão encerrados antes de continuar.",
                "warn"
            )
            self._step3_lay.addWidget(alert)
            self._step3_lay.addWidget(spacer(h=4))

            for proc in self._processos:
                card = ProcessCard(
                    str(proc.get('pid', '?')),
                    proc.get("name", proc.get("nome", "—")),
                    proc.get("exe", "")
                )
                self._step3_lay.addWidget(card)

            self._step3_lay.addWidget(spacer(h=16))

            btn_encerrar = make_primary_btn("⊗  ENCERRAR E CONTINUAR", 220)
            btn_encerrar.clicked.connect(self._encerrar_e_continuar)
            btn_voltar = make_secondary_btn("← VOLTAR", 120)
            btn_voltar.clicked.connect(lambda: self._go_step(1))
            self._step3_lay.addWidget(btn_row(btn_encerrar, btn_voltar))

        self._step3_lay.addStretch()

    def _encerrar_e_continuar(self):
        pids = [p["pid"] for p in self._processos]
        encerrar_processos(pids)
        self._go_step(3)

    # ── STEP 4: Selecionar Arquivos ────────────────────────────────────────────

    def _build_step4(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.addWidget(SectionHeader("Arquivos para Copiar"))
        hdr.addStretch()
        self._btn_all_files = make_secondary_btn("☐  Selecionar Todos", min_width=150)
        self._btn_all_files.clicked.connect(self._toggle_all_files)
        hdr.addWidget(self._btn_all_files)
        hdr_w = QWidget()
        hdr_w.setLayout(hdr)
        hdr_w.setStyleSheet("background: transparent;")
        lay.addWidget(hdr_w)
        lay.addWidget(spacer(h=12))

        # Search and Counter Row
        search_lay = QHBoxLayout()
        search_lay.setSpacing(12)
        
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍  Buscar arquivo...")
        self._search_input.setMinimumHeight(32)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 0 12px;
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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setMaximumHeight(200)
        scroll.setMinimumHeight(60)

        self._files_container = QWidget()
        self._files_container.setStyleSheet("background: transparent;")
        self._files_grid = QGridLayout(self._files_container)
        self._files_grid.setContentsMargins(0, 0, 4, 0)
        self._files_grid.setHorizontalSpacing(6)
        self._files_grid.setVerticalSpacing(6)
        self._files_grid.setColumnStretch(0, 1)
        self._files_grid.setColumnStretch(1, 1)
        scroll.setWidget(self._files_container)
        lay.addWidget(scroll)
        lay.addWidget(spacer(h=16))

        lay.addWidget(SectionHeader("Destino dos Atalhos"))
        lay.addWidget(spacer(h=6))
        self._dest_panel = DestPanel()
        lay.addWidget(self._dest_panel)
        lay.addWidget(spacer(h=16))

        btn_copiar = make_primary_btn("▶  COPIAR ARQUIVOS", 200)
        btn_copiar.clicked.connect(self._start_install)
        btn_voltar = make_secondary_btn("← VOLTAR", 120)
        btn_voltar.clicked.connect(lambda: self._go_step(2))
        lay.addWidget(btn_row(btn_copiar, btn_voltar))

        lay.addStretch()
        return w

    def _get_arquivos_servidor(self) -> list[dict]:
        if not self._servidor:
            return []
        exes = listar_executaveis(self._servidor.path)
        ini_path = Path(self._servidor.path) / "Futura.ini"
        if ini_path.exists():
            exes.append({
                "nome":      "Futura.ini",
                "descricao": "Configuração de Conexão",
                "caminho":   str(ini_path),
                "tamanho":   ini_path.stat().st_size,
            })
        return exes

    def _load_files(self):
        while self._files_grid.count():
            w = self._files_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._file_items.clear()

        if not self._servidor:
            return

        exes = self._get_arquivos_servidor()

        if not exes:
            self._files_grid.addWidget(
                label("Nenhum arquivo encontrado.", COLORS["warn"], 11), 0, 0, 1, 2
            )
            return

        for idx, exe in enumerate(exes):
            item = MiniFileItem(exe["nome"], formatar_tamanho(exe["tamanho"]))
            item.toggled.connect(self._update_counter)
            self._files_grid.addWidget(item, *divmod(idx, 2))
            self._file_items.append(item)
            
        self._update_counter()

    def _on_search(self, text: str):
        self._search_text = text.lower()
        self._refiltrar_grid()

    def _refiltrar_grid(self):
        for i in range(self._files_grid.count()):
            self._files_grid.itemAt(i).widget().hide()
            
        visiveis = [i for i in self._file_items if self._search_text in i.name.lower()]
        for idx, item in enumerate(visiveis):
            self._files_grid.addWidget(item, *divmod(idx, 2))
            item.show()

    def _update_counter(self):
        sel = sum(1 for i in self._file_items if i.is_checked())
        self._counter_lbl.setText(f"{sel} selecionado(s)")
        todos = all(i.is_checked() for i in self._file_items) if self._file_items else False
        self._btn_all_files.setText(
            "☑  Desmarcar Todos" if todos else "☐  Selecionar Todos"
        )

    def _toggle_all_files(self):
        if not self._file_items: return
        todos = all(i.is_checked() for i in self._file_items)
        for item in self._file_items:
            item.set_checked(not todos)
        self._update_counter()

    # ── STEP 5: Progresso ─────────────────────────────────────────────────────

    def _build_step5(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        lay.addWidget(SectionHeader("Executando Instalação"))

        self._prog_files = ProgressBlock("Arquivos")
        self._prog_dlls  = ProgressBlock("DLLs do Sistema")
        self._prog_dlls.setVisible(False)
        lay.addWidget(self._prog_files)
        lay.addWidget(self._prog_dlls)
        lay.addWidget(spacer(h=4))

        self._install_console = LogConsole(max_height=220)
        lay.addWidget(self._install_console)
        lay.addStretch()
        return w

    # ── STEP 6: Concluído ─────────────────────────────────────────────────────

    def _build_step6(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        self._done_lay = QVBoxLayout(w)
        self._done_lay.setContentsMargins(0, 0, 0, 0)
        self._done_lay.setSpacing(12)
        self._done_lay.addStretch()
        return w

    def _show_done(self, sucesso, resumo):
        while self._done_lay.count():
            item = self._done_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        dest_id  = self._dest_panel.selected_id()
        dest_txt = {0: "Desktop + Menu Iniciar", 1: "Desktop", 2: "Menu Iniciar"}.get(dest_id, "—")
        n_atl    = resumo.get("atalhos", 0)
        nomes    = resumo.get("atalhos_nomes", [])
        atalhos_txt = f"{n_atl} criado(s) — {dest_txt}"

        cancelado = resumo.get("cancelado", False)
        kind   = "success" if sucesso else "warn" if cancelado else "error"
        titulo = ("Instalação Concluída" if sucesso
                  else "Instalação Cancelada" if cancelado
                  else "Falha na Instalação")
        rows   = [
            ("Pasta",    resumo.get("pasta", "—")),
            ("Servidor", resumo.get("servidor", "—")),
            ("Arquivos", f"{resumo.get('copiados', 0)} copiado(s)"),
            ("Atalhos",  atalhos_txt),
            ("DLLs",     "Instaladas" if resumo.get("dlls") else "Não instaladas"),
            ("Backup",   resumo.get("backup", "—")),
        ]
        if nomes:
            for nome in nomes:
                rows.append(("", f"  • {nome}"))

        self._ultimo_relatorio = {
            "modo":    "Novo Terminal",
            "titulo":  titulo,
            "sucesso": sucesso,
            "campos":  rows,
        }

        btn_menu = make_primary_btn("← MENU PRINCIPAL", 200)
        btn_menu.clicked.connect(self.go_menu.emit)

        btns = [btn_menu]
        if sucesso:
            btn_rel = _make_secondary_btn("💾  Salvar Relatório", 180)
            btn_rel.clicked.connect(lambda: self._exportar_relatorio(self._ultimo_relatorio))
            btns.append(btn_rel)

        self._done_lay.addWidget(ResultBox(titulo, rows, kind))
        self._done_lay.addWidget(spacer(h=8))
        self._done_lay.addWidget(_btn_row(*btns))
        self._done_lay.addStretch()

    def _exportar_relatorio(self, dados: dict):
        now      = datetime.datetime.now()
        hostname = platform.node()
        nome_sug = f"relatorio_instalacao_{now.strftime('%Y%m%d_%H%M%S')}.txt"

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

    # ── INSTALAÇÃO ────────────────────────────────────────────────────────────

    def _start_install(self):
        if not self._servidor:
            return

        exes     = self._get_arquivos_servidor()
        exe_map  = {e["nome"]: e["caminho"] for e in exes}

        selecionados_origem = [
            exe_map[item.name]
            for item in self._file_items
            if item.is_checked() and item.name in exe_map
        ]

        if not selecionados_origem:
            if not hasattr(self, '_no_file_alert'):
                self._no_file_alert = AlertBox(
                    "⚠  Selecione ao menos um arquivo para continuar.", "warn"
                )
                step4_widget = self._stack.widget(3)
                step4_widget.layout().insertWidget(0, self._no_file_alert)
            else:
                self._no_file_alert.setVisible(True)
            return

        if hasattr(self, '_no_file_alert'):
            self._no_file_alert.setVisible(False)

        exes_para_copiar = [p for p in selecionados_origem if p.endswith(".exe")]
        exes_atalho_dest = [
            str(Path(self._pasta) / Path(p).name)
            for p in exes_para_copiar
        ]

        dest_id     = self._dest_panel.selected_id()
        atalho_desk = dest_id in (0, 1)
        atalho_menu = dest_id in (0, 2)

        self._install_console.clear_console()
        self._prog_files.update(0, "Iniciando...", "Preparando instalação...")
        self._prog_dlls.setVisible(False)
        self._go_step(4)

        self._worker = InstalacaoWorker(
            servidor             = self._servidor,
            pasta                = self._pasta,
            exes                 = exes_para_copiar,
            criar_atalho_desktop = atalho_desk,
            criar_atalho_menu    = atalho_menu,
            exes_atalho          = exes_atalho_dest,
        )
        self._worker.log_line.connect(self._install_console.append_line)
        self._worker.progress.connect(self._on_progress)
        self._worker.step_done.connect(self._step_ind.set_step)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, pct, nome, sub):
        if "DLL" in nome or "dll" in nome.lower():
            self._prog_dlls.setVisible(True)
            self._prog_dlls.update(pct, nome, sub)
        else:
            self._prog_files.update(pct, nome, sub)

    def _on_finished(self, sucesso, resumo):
        self._step_ind.set_step(len(STEP_NAMES))
        self._show_done(sucesso, resumo)
        self._stack.setCurrentIndex(5)

    # ── NAVEGAÇÃO ─────────────────────────────────────────────────────────────

    def _go_step(self, idx: int):
        self._stack.setCurrentIndex(idx)
        self._step_ind.set_step(idx)
        if idx == 2:
            self._check_processos()
        elif idx == 3:
            self._load_files()

    # ── TECLADO ───────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            idx = self._stack.currentIndex()
            back_map = {
                0: self.go_menu.emit,
                1: lambda: self._go_step(0),
                2: lambda: self._go_step(1),
                3: lambda: self._go_step(1),
                4: lambda: self._go_step(2),
            }
            action = back_map.get(idx)
            if action:
                action()
        else:
            super().keyPressEvent(event)
