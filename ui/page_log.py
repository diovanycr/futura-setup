# =============================================================================
# FUTURA SETUP — Página: Ver Log v5
# Melhorias v5:
#   - LogConsole ocupa todo o espaço restante da página (sem altura fixa)
#   - Layout corrigido: content com stretch=1, footer fixo na base
#   - Removido setMinimumHeight manual (agora controlado por SizePolicy)
# =============================================================================

import subprocess
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QFileDialog, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont

from ui.widgets import PageTitle, SectionHeader, AlertBox, LogConsole, make_btn, spacer
from ui.theme import COLORS, FONT_SANS
from ui.theme_manager import theme_manager
from core.logger import log


# -- HELPERS DE BOTÃO ---------------------------------------------------------

def _make_primary_btn(text: str, min_width: int = 140) -> QPushButton:
    btn = QPushButton(text)
    btn.setMinimumWidth(min_width)
    btn.setMinimumHeight(36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
    _apply_primary(btn)
    theme_manager.theme_changed.connect(lambda _: _apply_primary(btn))
    return btn

def _make_secondary_btn(text: str, min_width: int = 120) -> QPushButton:
    btn = QPushButton(text)
    btn.setMinimumWidth(min_width)
    btn.setMinimumHeight(36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFont(QFont(FONT_SANS, 12))
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
    """)

def _apply_secondary(btn: QPushButton):
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: transparent;
            color: {COLORS["text"]};
            border: 1.5px solid {COLORS["btn_border"]};
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: {COLORS["panel_hover"]};
            border-color: {COLORS["text_dim"]};
        }}
        QPushButton:pressed {{ background-color: {COLORS["panel_press"]}; }}
    """)


class PageLog(QWidget):
    go_menu = pyqtSignal()

    _FILTER_KINDS = ["Todos", "OK", "Erro", "Aviso", "Info"]
    _FILTER_DATES = ["Tudo", "Hoje", "7 dias"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_lines: list[tuple[str, str]] = []
        self._active_filter_kind = "Todos"
        self._active_filter_date = "Tudo"
        self._active_search      = ""

        # Layout raiz: conteúdo expansível + rodapé fixo
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Área de conteúdo (expande) ────────────────────────────────────────
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(40, 36, 40, 0)
        lay.setSpacing(0)

        lay.addWidget(PageTitle("HISTÓRICO", "Log de Execuções"))

        self._alert = AlertBox(f"Arquivo: {log.log_path}", "info")
        lay.addWidget(self._alert)
        lay.addWidget(spacer(h=12))

        # -- Busca -------------------------------------------------------------
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍  Buscar no log...")
        self._search_input.setFont(QFont(FONT_SANS, 12))
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(200)
        self._filter_timer.timeout.connect(self._apply_filter)
        self._search_input.textChanged.connect(lambda _: self._filter_timer.start())
        lay.addWidget(self._search_input)
        lay.addWidget(spacer(h=8))

        # -- Filtros por tipo --------------------------------------------------
        kind_row = QHBoxLayout()
        kind_row.setSpacing(5)
        self._kind_btns: list[QPushButton] = []
        for kind in self._FILTER_KINDS:
            btn = QPushButton(kind)
            btn.setFont(QFont(FONT_SANS, 10))
            btn.setFixedHeight(26)
            btn.setMinimumWidth(52)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(kind == "Todos")
            btn.clicked.connect(lambda _, k=kind: self._set_kind_filter(k))
            self._kind_btns.append(btn)
            kind_row.addWidget(btn)
        kind_row.addStretch()
        kind_w = QWidget()
        kind_w.setLayout(kind_row)
        kind_w.setStyleSheet("background: transparent;")
        lay.addWidget(kind_w)
        lay.addWidget(spacer(h=4))

        # -- Filtros por data --------------------------------------------------
        date_row = QHBoxLayout()
        date_row.setSpacing(5)
        self._date_btns: list[QPushButton] = []
        for d in self._FILTER_DATES:
            btn = QPushButton(d)
            btn.setFont(QFont(FONT_SANS, 10))
            btn.setFixedHeight(26)
            btn.setMinimumWidth(52)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(d == "Tudo")
            btn.clicked.connect(lambda _, dd=d: self._set_date_filter(dd))
            self._date_btns.append(btn)
            date_row.addWidget(btn)
        date_row.addStretch()
        date_w = QWidget()
        date_w.setLayout(date_row)
        date_w.setStyleSheet("background: transparent;")
        lay.addWidget(date_w)
        lay.addWidget(spacer(h=8))

        lay.addWidget(SectionHeader("Conteúdo do Log"))

        # Console expande para preencher tudo que restar
        self._console = LogConsole(max_height=0)
        lay.addWidget(self._console, 1)   # stretch=1 → ocupa todo o espaço livre

        root.addWidget(content, 1)        # content também expande

        # ── Rodapé fixo ───────────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet("background: transparent;")
        footer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        footer_lay = QVBoxLayout(footer)
        footer_lay.setContentsMargins(40, 10, 40, 20)
        footer_lay.setSpacing(0)

        btns = QHBoxLayout()
        btns.setSpacing(8)

        btn_refresh = _make_primary_btn("↺  ATUALIZAR", 140)
        btn_refresh.clicked.connect(self.load_log)

        btn_export = _make_secondary_btn("↓  EXPORTAR", 130)
        btn_export.clicked.connect(self._export_log)

        btn_open = _make_secondary_btn("ABRIR EXTERNAMENTE", 190)
        btn_open.clicked.connect(self._open_external)

        btn_voltar = _make_secondary_btn("← VOLTAR", 110)
        btn_voltar.clicked.connect(self.go_menu.emit)

        btns.addWidget(btn_refresh)
        btns.addWidget(btn_export)
        btns.addWidget(btn_open)
        btns.addWidget(btn_voltar)
        btns.addStretch()

        btn_w = QWidget()
        btn_w.setLayout(btns)
        btn_w.setStyleSheet("background: transparent;")
        footer_lay.addWidget(btn_w)

        root.addWidget(footer, 0)         # footer fixo, não expande

        self._upd_filter_btns()
        theme_manager.theme_changed.connect(self._upd_filter_btns)
        theme_manager.theme_changed.connect(
            lambda _: footer.setStyleSheet("background: transparent;")
        )

    # -- ESTILO DOS BOTÕES DE FILTRO -------------------------------------------

    def _upd_filter_btns(self, _mode: str = ""):
        for btn in self._kind_btns + self._date_btns:
            if btn.isChecked():
                btn.setStyleSheet(
                    f"background: {COLORS['accent_dim']}; color: {COLORS['accent']};"
                    f"border: 1px solid {COLORS['accent']}; border-radius: 4px;"
                    f"font-weight: 600; padding: 0 10px;"
                )
            else:
                btn.setStyleSheet(
                    f"background: {COLORS['surface']}; color: {COLORS['text_mid']};"
                    f"border: 1px solid {COLORS['border']}; border-radius: 4px;"
                    f"padding: 0 10px;"
                )

    # -- FILTROS ---------------------------------------------------------------

    def _set_kind_filter(self, kind: str):
        self._active_filter_kind = kind
        for btn in self._kind_btns:
            btn.setChecked(btn.text() == kind)
        self._upd_filter_btns()
        self._apply_filter()

    def _set_date_filter(self, date: str):
        self._active_filter_date = date
        for btn in self._date_btns:
            btn.setChecked(btn.text() == date)
        self._upd_filter_btns()
        self._apply_filter()

    def _apply_filter(self):
        search = self._search_input.text().strip().lower()
        self._active_search = search
        self._console.clear_console()

        kind_map    = {"OK": "ok", "Erro": "err", "Aviso": "warn", "Info": "info"}
        target_kind = kind_map.get(self._active_filter_kind)

        now = datetime.now()
        if self._active_filter_date == "Hoje":
            min_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self._active_filter_date == "7 dias":
            min_date = now - timedelta(days=7)
        else:
            min_date = None

        for text, kind in self._all_lines:
            if target_kind and kind != target_kind:
                continue
            if search and search not in text.lower():
                continue
            if min_date:
                if len(text) >= 21 and text.startswith("["):
                    try:
                        ts = datetime.strptime(text[1:20], "%Y-%m-%d %H:%M:%S")
                        if ts < min_date:
                            continue
                    except ValueError:
                        pass
            self._console.append_line(text, kind)

    # -- CARREGAR LOG ----------------------------------------------------------

    def load_log(self):
        self._all_lines.clear()
        content = log.read_log_tail(max_lines=5000)
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            if "[OK]" in line or "CONCLUIDO" in line or "SUCESSO" in line:
                kind = "ok"
            elif "[WARNING]" in line or "[AVISO]" in line or "WARN" in line:
                kind = "warn"
            elif "[ERROR]" in line or "[ERRO]" in line:
                kind = "err"
            elif "===" in line:
                kind = "info"
            else:
                kind = "dim"
            self._all_lines.append((line, kind))

        self._apply_filter()
        total = len(self._all_lines)
        self._alert.set_text(f"Arquivo: {log.log_path}  —  {total} linha(s)")

    # -- EXPORT ----------------------------------------------------------------

    def _export_log(self):
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"futura_setup_log_{ts}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar Log", fname, "Arquivos de texto (*.txt)"
        )
        if not path:
            return
        try:
            texto = self._console.toPlainText()
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# Futura Setup — Log Exportado em {datetime.now()}\n")
                f.write(
                    f"# Filtro tipo: {self._active_filter_kind}  "
                    f"| Data: {self._active_filter_date}  "
                    f"| Busca: '{self._active_search}'\n\n"
                )
                f.write(texto)
            self._alert.set_text(f"✓ Exportado: {path}")
            self._alert._kind = "success"
            self._alert._upd()
            log.ok(f"Log exportado: {path}")
        except Exception as e:
            self._alert.set_text(f"Erro ao exportar: {e}")
            self._alert._kind = "warn"
            self._alert._upd()

    def _open_external(self):
        if not log.log_path.exists():
            self._console.append_line(
                "Arquivo de log ainda não existe — nenhum registro gravado.", "warn"
            )
            return
        try:
            subprocess.Popen(["notepad.exe", str(log.log_path)])
        except Exception as e:
            self._console.append_line(f"Erro ao abrir Notepad: {e}", "err")