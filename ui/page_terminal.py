# =============================================================================
# FUTURA SETUP — Página: Novo Terminal (MODO 02)
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
    QGridLayout, QFileDialog, QPushButton,
)
from PyQt6.QtCore import pyqtSignal, Qt, QByteArray, QRectF
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer

from ui.widgets import (
    PageTitle, SectionHeader, AlertBox, ResultBox, ProgressBlock,
    LogConsole, StepIndicator, MiniFileItem, DestPanel, RadioRow,
    make_btn, spacer, label
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


# ── HELPERS DE BOTÃO ─────────────────────────────────────────────────────────

def _make_primary_btn(text: str, min_width: int = 180) -> QPushButton:
    btn = QPushButton(text)
    btn.setMinimumWidth(min_width)
    btn.setMinimumHeight(36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
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

def _btn_row(*btns) -> QWidget:
    """Cria uma linha de botões alinhada à esquerda."""
    row = QHBoxLayout()
    row.setSpacing(10)
    for btn in btns:
        row.addWidget(btn)
    row.addStretch()
    w = QWidget()
    w.setLayout(row)
    w.setStyleSheet("background: transparent;")
    return w


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

        lay.addWidget(PageTitle("MODO 02", "Novo Terminal"))

        self._step_ind = StepIndicator(STEP_NAMES)
        lay.addWidget(self._step_ind)
        lay.addWidget(spacer(h=12))

        self._stack = QStackedWidget()
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

        # Opção personalizada
        self._custom_row = QWidget()
        self._custom_row.setObjectName("CustomRow")
        self._upd_custom_style(False)

        c_lay = QHBoxLayout(self._custom_row)
        c_lay.setContentsMargins(20, 12, 16, 12)
        c_lay.setSpacing(14)

        custom_info_lay = QVBoxLayout()
        custom_info_lay.setSpacing(4)
        custom_title = QLabel("Outro caminho")
        custom_title.setFont(QFont(FONT_MONO, 12, QFont.Weight.Bold))
        custom_title.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        self._custom_input = QLineEdit()
        self._custom_input.setPlaceholderText("Clique para selecionar a pasta...")
        self._custom_input.setMaximumWidth(340)
        self._custom_input.setReadOnly(True)
        self._custom_input.setCursor(Qt.CursorShape.PointingHandCursor)

        def _abrir_explorer():
            self._custom_radio.setChecked(True)
            pasta_atual = self._custom_input.text().strip() or "C:\\"
            pasta = QFileDialog.getExistingDirectory(None, "Selecionar pasta de instalação", pasta_atual)
            if pasta:
                self._custom_input.setText(pasta.replace("/", "\\"))

        _orig_press = self._custom_input.mousePressEvent
        def _custom_press(e):
            if e.button() == Qt.MouseButton.LeftButton:
                _abrir_explorer()
            else:
                _orig_press(e)
        self._custom_input.mousePressEvent = _custom_press

        custom_info_lay.addWidget(custom_title)
        custom_info_lay.addWidget(self._custom_input)
        custom_info_w = QWidget()
        custom_info_w.setLayout(custom_info_lay)
        custom_info_w.setStyleSheet("background: transparent;")

        # Radio button mantido invisível para controle lógico do grupo
        self._custom_radio = QRadioButton()
        self._custom_radio.setVisible(False)
        self._pasta_group.addButton(self._custom_radio, 2)
        self._custom_radio.toggled.connect(self._upd_custom_style)

        # Botão de pasta visível substituindo o radio button
        self._btn_pasta = QPushButton()
        self._btn_pasta.setFixedSize(40, 40)
        self._btn_pasta.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pasta.setToolTip("Selecionar pasta de instalação")
        self._apply_btn_pasta_style()
        self._btn_pasta.clicked.connect(_abrir_explorer)
        theme_manager.theme_changed.connect(lambda _: self._apply_btn_pasta_style())

        c_lay.addWidget(custom_info_w, 1)
        c_lay.addWidget(self._custom_radio)  # invisível, mantido no layout
        c_lay.addWidget(self._btn_pasta)
        lay.addWidget(self._custom_row)

        lay.addWidget(spacer(h=16))

        btn_proximo = _make_primary_btn("▶  PRÓXIMO", 180)
        btn_proximo.clicked.connect(self._confirm_pasta)
        btn_voltar = _make_secondary_btn("← VOLTAR", 120)
        btn_voltar.clicked.connect(self.go_menu.emit)

        # Botões centralizados logo abaixo do "Outro caminho"
        btns_lay = QHBoxLayout()
        btns_lay.setSpacing(10)
        btns_lay.addStretch()
        btns_lay.addWidget(btn_proximo)
        btns_lay.addWidget(btn_voltar)
        btns_lay.addStretch()
        btns_w = QWidget()
        btns_w.setLayout(btns_lay)
        btns_w.setStyleSheet("background: transparent;")
        lay.addWidget(btns_w)
        lay.addStretch()

        theme_manager.theme_changed.connect(
            lambda _: self._upd_custom_style(self._custom_radio.isChecked())
        )
        return w

    def _apply_btn_pasta_style(self):
        # SVG de pasta limpo, cor branca
        svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
              stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>"""
        renderer = QSvgRenderer(QByteArray(svg))
        pixmap = QPixmap(28, 28)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter, QRectF(0, 0, 28, 28))
        painter.end()
        self._btn_pasta.setIcon(QIcon(pixmap))
        self._btn_pasta.setIconSize(pixmap.size())
        self._btn_pasta.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                border: none;
                border-radius: 8px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background: {COLORS['accent_hover']};
            }}
            QPushButton:pressed {{
                background: {COLORS['accent_press']};
            }}
        """)

    def _upd_custom_style(self, checked):
        bg     = COLORS["accent_dim"] if checked else COLORS["surface"]
        border = COLORS["accent"]     if checked else COLORS["border"]
        self._custom_row.setStyleSheet(
            f"QWidget#CustomRow {{"
            f"  background: {bg};"
            f"  border: 1.5px solid {border};"
            f"  border-radius: 8px;"
            f"}}"
        )

    def _confirm_pasta(self):
        idx = self._pasta_group.checkedId()
        if idx == 0:
            self._pasta = "C:\\FUTURA"
        elif idx == 1:
            self._pasta = "C:\\FuturaTerminal"
        else:
            custom = self._custom_input.text().strip()
            if not custom:
                pasta = QFileDialog.getExistingDirectory(None, "Selecionar pasta de instalação", "C:\\")
                if not pasta:
                    return
                custom = pasta.replace("/", "\\")
                self._custom_input.setText(custom)
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

        self._resumo_box = QWidget()
        self._resumo_box.setObjectName("ResumoBox")
        self._refresh_resumo_style()

        resumo_lay = QVBoxLayout(self._resumo_box)
        resumo_lay.setContentsMargins(20, 16, 20, 16)
        resumo_lay.setSpacing(8)

        self._resumo_labels = {}
        for campo in ["Modo", "Servidor", "Caminho", "Pasta", "Espaço Livre"]:
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
        lay.addWidget(spacer(h=16))

        btn_confirmar = _make_primary_btn("✓  CONFIRMAR E CONTINUAR", 220)
        btn_confirmar.clicked.connect(lambda: self._go_step(2))
        btn_voltar = _make_secondary_btn("← VOLTAR", 120)
        btn_voltar.clicked.connect(lambda: self._go_step(0))
        lay.addWidget(_btn_row(btn_confirmar, btn_voltar))

        lay.addStretch()

        theme_manager.theme_changed.connect(self._refresh_resumo_style)
        return w

    def _refresh_resumo_style(self, _mode: str = ""):
        self._resumo_box.setStyleSheet(f"""
            QWidget#ResumoBox {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)

    def _update_resumo(self):
        if not self._servidor:
            return
        espaco = espaco_livre_mb(self._pasta)
        aviso  = "  ⚠ Pouco espaço!" if espaco < 500 else ""
        self._resumo_labels["Modo"].setText("Novo Terminal")
        self._resumo_labels["Servidor"].setText(self._servidor.display)
        self._resumo_labels["Caminho"].setText(self._servidor.path)
        self._resumo_labels["Pasta"].setText(self._pasta)
        self._resumo_labels["Espaço Livre"].setText(f"{espaco:.1f} MB disponíveis{aviso}")
        self._refresh_resumo_style()

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
                card = QWidget()
                card.setObjectName("ProcCard")
                card.setFixedHeight(54)
                card.setStyleSheet(f"""
                    QWidget#ProcCard {{
                        background: {COLORS['surface']};
                        border: 1.5px solid {COLORS['border']};
                        border-radius: 8px;
                    }}
                """)
                c_lay = QHBoxLayout(card)
                c_lay.setContentsMargins(16, 0, 16, 0)
                c_lay.setSpacing(12)

                dot = QWidget()
                dot.setFixedSize(8, 8)
                dot.setStyleSheet(
                    f"background: {COLORS['warn']}; border-radius: 4px; border: none;"
                )

                pid_lbl = QLabel(f"PID {proc.get('pid', '?')}")
                pid_lbl.setFont(QFont(FONT_MONO, 10))
                pid_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
                pid_lbl.setFixedWidth(72)

                info_lay = QVBoxLayout()
                info_lay.setSpacing(1)
                info_lay.setContentsMargins(0, 0, 0, 0)
                name_lbl = QLabel(proc.get("name", proc.get("nome", "—")))
                name_lbl.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
                name_lbl.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
                path_lbl = QLabel(proc.get("exe", ""))
                path_lbl.setFont(QFont(FONT_MONO, 9))
                path_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
                info_lay.addStretch()
                info_lay.addWidget(name_lbl)
                info_lay.addWidget(path_lbl)
                info_lay.addStretch()
                info_w = QWidget()
                info_w.setLayout(info_lay)
                info_w.setStyleSheet("background: transparent;")

                c_lay.addWidget(dot)
                c_lay.addWidget(pid_lbl)
                c_lay.addWidget(info_w, 1)
                self._step3_lay.addWidget(card)

            self._step3_lay.addWidget(spacer(h=16))

            btn_encerrar = _make_primary_btn("⊗  ENCERRAR E CONTINUAR", 220)
            btn_encerrar.clicked.connect(self._encerrar_e_continuar)
            btn_voltar = _make_secondary_btn("← VOLTAR", 120)
            btn_voltar.clicked.connect(lambda: self._go_step(1))
            self._step3_lay.addWidget(_btn_row(btn_encerrar, btn_voltar))

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
        btn_all = make_btn("☑  Selecionar Todos", min_width=160)
        btn_all.clicked.connect(self._toggle_all_files)
        hdr.addWidget(btn_all)
        hdr_w = QWidget()
        hdr_w.setLayout(hdr)
        hdr_w.setStyleSheet("background: transparent;")
        lay.addWidget(hdr_w)
        lay.addWidget(spacer(h=4))

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

        btn_copiar = _make_primary_btn("▶  COPIAR ARQUIVOS", 200)
        btn_copiar.clicked.connect(self._start_install)
        btn_voltar = _make_secondary_btn("← VOLTAR", 120)
        btn_voltar.clicked.connect(lambda: self._go_step(2))
        lay.addWidget(_btn_row(btn_copiar, btn_voltar))

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
            self._files_grid.addWidget(item, *divmod(idx, 2))
            self._file_items.append(item)

    def _toggle_all_files(self):
        todos = all(i.is_checked() for i in self._file_items)
        for item in self._file_items:
            item.set_checked(not todos)

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
            "modo":    "02 — Novo Terminal",
            "titulo":  titulo,
            "sucesso": sucesso,
            "campos":  rows,
        }

        btn_menu = _make_primary_btn("← MENU PRINCIPAL", 200)
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
