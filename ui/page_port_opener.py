"""
ui/page_port_opener.py — Página de Abertura de Portas no Firewall (Modo 07)

Fluxo:
  Step 0 — Configuração (adicionar portas, protocolo, direção)
  Step 1 — Execução (LogConsole + ProgressBlock)
  Step 2 — Resultado

Registrar em main.py:
  _IDX_PORT_OPENER = 8
  self._page_port_opener = PagePortOpener()
  self._stack.addWidget(self._page_port_opener)
  self._page_port_opener.go_menu.connect(self._go_menu)
  # sidebar nav_port_opener
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QScrollArea, QStackedWidget, QSizePolicy, QGridLayout, QFrame, QPushButton,
)
from PyQt6.QtGui import QFont

from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets import (
    PageTitle, SectionHeader, AlertBox, LogConsole,
    ProgressBlock, ResultBox, make_btn, make_btn_row,
    spacer, h_line, label, ConfirmDialog,
)
from core.logger import log
from core.port_opener import (
    PortOpenerWorker,
    KNOWN_PORTS,
    is_admin,
)

# ---------------------------------------------------------------------------
# Portas sugeridas (rápido acesso)
# ---------------------------------------------------------------------------
QUICK_PORTS = [
    (80,    "HTTP"),
    (443,   "HTTPS"),
    (3050,  "Firebird"),
    (3306,  "MySQL"),
    (3389,  "RDP"),
    (5432,  "Postgres"),
    (8080,  "HTTP Alt"),
    (22,    "SSH"),
    (6379,  "Redis"),
    (27017, "MongoDB"),
    (1433,  "SQL Server"),
    (5000,  "Flask"),
]


# ---------------------------------------------------------------------------
# Widget: chip de porta selecionada
# ---------------------------------------------------------------------------
class _PortChip(QWidget):
    removed = pyqtSignal(int)

    def __init__(self, port: int, label_text: str = "", parent=None):
        super().__init__(parent)
        self._port = port
        self.setObjectName("PortChip")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 3, 4, 3)
        lay.setSpacing(4)

        self._num_lbl = QLabel(str(port))
        self._num_lbl.setObjectName("chip_num")
        self._num_lbl.setFont(QFont(FONT_MONO, 12, QFont.Weight.Medium))

        self._name_lbl = QLabel(label_text)
        self._name_lbl.setObjectName("chip_name")
        self._name_lbl.setFont(QFont(FONT_SANS, 10))

        self._btn_x = QPushButton("×")
        self._btn_x.setObjectName("chip_x")
        self._btn_x.setFixedSize(18, 18)
        self._btn_x.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
        self._btn_x.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_x.clicked.connect(lambda: self.removed.emit(self._port))

        lay.addWidget(self._num_lbl)
        if label_text:
            lay.addWidget(self._name_lbl)
        lay.addWidget(self._btn_x)

        theme_manager.theme_changed.connect(self._upd)
        self._upd()

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(f"""
            QWidget#PortChip {{
                background: {COLORS['accent_dim']};
                border: 1px solid {COLORS['accent']};
                border-radius: 6px;
            }}
            QLabel#chip_num {{
                color: {COLORS['accent']};
                background: transparent;
                border: none;
            }}
            QLabel#chip_name {{
                color: {COLORS['text_dim']};
                background: transparent;
                border: none;
                font-size: 10px;
            }}
            QPushButton#chip_x {{
                background: transparent;
                color: {COLORS['accent']};
                border: none;
                border-radius: 9px;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton#chip_x:hover {{
                background: {COLORS['accent']};
                color: #ffffff;
            }}
        """)


# ---------------------------------------------------------------------------
# Widget: botão de porta rápida
# ---------------------------------------------------------------------------
class _QuickPortBtn(QWidget):
    toggled = pyqtSignal(int, str, bool)   # (port, label, added)

    def __init__(self, port: int, label_text: str, parent=None):
        super().__init__(parent)
        self._port  = port
        self._label = label_text
        self._added = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)          # ← compactado
        self.setMinimumWidth(60)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 1, 4, 1)   # ← compactado
        lay.setSpacing(0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._num_lbl  = QLabel(str(port))
        self._num_lbl.setFont(QFont(FONT_MONO, 10, QFont.Weight.Medium))  # ← menor
        self._num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._name_lbl = QLabel(label_text)
        self._name_lbl.setFont(QFont(FONT_SANS, 8))   # ← menor
        self._name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(self._num_lbl)
        lay.addWidget(self._name_lbl)

        theme_manager.theme_changed.connect(self._upd)
        self._upd()

    def set_added(self, v: bool):
        self._added = v
        self._upd()

    def _upd(self, _mode: str = ""):
        if self._added:
            bg     = COLORS["accent_dim"]
            border = COLORS["accent"]
            num_c  = COLORS["accent"]
        else:
            bg     = COLORS["surface"]
            border = COLORS["border"] if "border" in COLORS else COLORS["text_dim"]
            num_c  = COLORS["text"]
        self.setStyleSheet(
            f"background:{bg}; border:1px solid {border}; border-radius:7px;"
        )
        self._num_lbl.setStyleSheet(
            f"color:{num_c}; background:transparent; border:none;"
        )
        self._name_lbl.setStyleSheet(
            f"color:{COLORS['text_dim']}; background:transparent; border:none;"
        )

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._added = not self._added
            self._upd()
            self.toggled.emit(self._port, self._label, self._added)


# ---------------------------------------------------------------------------
# Widget: segmented control (protocolo / direção)
# Segue o mesmo padrão visual do DestPanel em ui/widgets.py
# ---------------------------------------------------------------------------
class _SegControl(QWidget):
    changed = pyqtSignal(str)

    def __init__(self, options: list[tuple[str, str]], default: str = "", parent=None):
        """options: [(valor, label), ...]"""
        super().__init__(parent)
        self._value = default if default else options[0][0]
        self._options = options
        self.setObjectName("SegControl")
        self.setFixedHeight(32)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._btns: list[tuple[str, QPushButton]] = []
        for i, (val, lbl) in enumerate(options):
            btn = QPushButton(lbl)
            btn.setObjectName(f"seg_btn_{i}")
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(QFont(FONT_SANS, 11))
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _, v=val: self._pick(v))
            self._btns.append((val, btn))
            lay.addWidget(btn)

            # divisor vertical entre botões (igual ao DestPanel)
            if i < len(options) - 1:
                div = QFrame()
                div.setFrameShape(QFrame.Shape.VLine)
                div.setFixedWidth(1)
                div.setObjectName("seg_div")
                lay.addWidget(div)

        theme_manager.theme_changed.connect(self._upd)
        self._upd()

    def _pick(self, val: str):
        self._value = val
        self._upd()
        self.changed.emit(val)

    def _upd(self, _mode: str = ""):
        n = len(self._btns)
        # container com borda e border-radius igual ao DestPanel
        self.setStyleSheet(f"""
            QWidget#SegControl {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['btn_border']};
                border-radius: 6px;
            }}
            QFrame#seg_div {{
                background: {COLORS['border']};
                border: none;
            }}
        """)
        for i, (val, btn) in enumerate(self._btns):
            selected = (val == self._value)
            # border-radius nas pontas
            if n == 1:
                radius = "6px"
            elif i == 0:
                radius = "5px 0 0 5px"
            elif i == n - 1:
                radius = "0 5px 5px 0"
            else:
                radius = "0"

            if selected:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {COLORS['accent']};
                        color: #ffffff;
                        border: none;
                        border-radius: {radius};
                        font-weight: 600;
                        padding: 0 12px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: {COLORS['text_mid']};
                        border: none;
                        border-radius: {radius};
                        font-weight: normal;
                        padding: 0 12px;
                    }}
                    QPushButton:hover {{
                        background: {COLORS['panel_hover']};
                        color: {COLORS['text']};
                    }}
                """)

    @property
    def value(self) -> str:
        return self._value


# ---------------------------------------------------------------------------
# Step 0 — Configuração
# ---------------------------------------------------------------------------
class _StepConfig(QWidget):
    go_abrir   = pyqtSignal()
    go_remover = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ports: dict[int, str] = {}   # port → label
        self._quick_btns: dict[int, _QuickPortBtn] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 16, 0)
        lay.setSpacing(6)   # ← compactado

        # Alerta admin
        self._alert_admin = AlertBox(
            "⚠ O programa não está rodando como Administrador. "
            "A abertura de portas pode falhar.",
            "warn",
        )
        self._alert_admin.setVisible(not is_admin())
        lay.addWidget(self._alert_admin)

        # ── Campo de entrada de porta ─────────────────────────────────────
        lay.addWidget(SectionHeader("Portas"))

        self._alert_field = AlertBox("", "danger")
        self._alert_field.setVisible(False)
        lay.addWidget(self._alert_field)

        # Campo de texto
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self._port_input = QLineEdit()
        self._port_input.setPlaceholderText("Digite a porta (ex: 3050) e pressione Enter ou ＋")
        self._port_input.setMinimumHeight(32)   # ← compactado
        self._port_input.setFont(QFont(FONT_MONO, 12))   # ← menor
        self._port_input.returnPressed.connect(self._add_from_input)

        self._btn_add = make_btn("＋ Adicionar", "primary", min_width=120)
        self._btn_add.clicked.connect(self._add_from_input)

        input_row.addWidget(self._port_input, 1)
        input_row.addWidget(self._btn_add)
        lay.addLayout(input_row)

        # ── Portas selecionadas (chips com botão remover) ────────────────
        self._chips_hint = label("Clique nas portas abaixo para selecionar", COLORS["text_dim"], 11)
        lay.addWidget(self._chips_hint)

        self._chips_wrap = QWidget()
        self._chips_wrap.setMinimumHeight(36)
        self._chips_lay  = QHBoxLayout(self._chips_wrap)
        self._chips_lay.setContentsMargins(0, 2, 0, 2)
        self._chips_lay.setSpacing(6)
        self._chips_lay.addStretch()
        lay.addWidget(self._chips_wrap)

        # ── Portas rápidas ────────────────────────────────────────────────
        lay.addWidget(h_line())
        lay.addWidget(SectionHeader("Portas comuns"))

        quick_wrap = QWidget()
        quick_grid = QGridLayout(quick_wrap)
        quick_grid.setContentsMargins(0, 0, 0, 0)
        quick_grid.setSpacing(4)   # ← compactado

        for idx, (port, lbl) in enumerate(QUICK_PORTS):
            btn = _QuickPortBtn(port, lbl)
            btn.toggled.connect(self._on_quick_toggle)
            self._quick_btns[port] = btn
            quick_grid.addWidget(btn, idx // 6, idx % 6)

        lay.addWidget(quick_wrap)

        # ── Opções ────────────────────────────────────────────────────────
        lay.addWidget(h_line())
        lay.addWidget(SectionHeader("Opções"))

        opts_row = QHBoxLayout()
        opts_row.setSpacing(8)

        opts_row.addWidget(label("Protocolo:", COLORS["text_mid"], 12))
        self._seg_proto = _SegControl([("TCP","TCP"), ("UDP","UDP"), ("BOTH","Ambos")], default="BOTH")
        self._seg_proto.setFixedWidth(195)
        opts_row.addWidget(self._seg_proto)

        opts_row.addSpacing(20)

        opts_row.addWidget(label("Direção:", COLORS["text_mid"], 12))
        self._seg_dir = _SegControl([("in","Entrada"), ("out","Saída"), ("both","Ambas")], default="both")
        self._seg_dir.setFixedWidth(230)
        opts_row.addWidget(self._seg_dir)

        opts_row.addStretch()
        lay.addLayout(opts_row)

        # ── Histórico de portas ───────────────────────────────────────────
        lay.addWidget(h_line())
        lay.addWidget(SectionHeader("Usadas recentemente"))

        self._hist_wrap = QWidget()
        self._hist_lay  = QHBoxLayout(self._hist_wrap)
        self._hist_lay.setContentsMargins(0, 0, 0, 0)
        self._hist_lay.setSpacing(6)
        self._hist_lay.addStretch()
        lay.addWidget(self._hist_wrap)
        self._carregar_historico()

        lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # ── Rodapé ────────────────────────────────────────────────────────
        footer = QWidget()
        f_lay  = QVBoxLayout(footer)
        f_lay.setContentsMargins(0, 6, 0, 0)
        f_lay.setSpacing(6)
        f_lay.addWidget(h_line())

        self._btn_abrir   = make_btn("▶  Abrir Portas no Firewall", "primary",   min_width=220)
        self._btn_remover = make_btn("✕  Remover Regras",           "secondary", min_width=160)
        self._btn_abrir.clicked.connect(self._on_abrir)
        self._btn_remover.clicked.connect(self._on_remover)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addWidget(self._btn_abrir)
        btn_row.addWidget(self._btn_remover)
        btn_row.addStretch()
        f_lay.addLayout(btn_row)

        root.addWidget(footer, 0)

        theme_manager.theme_changed.connect(self._upd)
        self._upd()

    def _upd(self, _mode: str = ""):
        self._port_input.setStyleSheet(
            f"background:{COLORS['surface']}; color:{COLORS['text']};"
            f"border:1px solid {COLORS['text_dim']}; border-radius:6px; padding:4px 10px;"
        )

    # ------------------------------------------------------------------
    def _add_from_input(self):
        raw = self._port_input.text().strip()
        self._port_input.clear()
        if not raw:
            return
        try:
            port = int(raw)
            assert 1 <= port <= 65535
        except (ValueError, AssertionError):
            self._show_field_error(f"Porta inválida: '{raw}'. Use um número entre 1 e 65535.")
            return
        self._add_port(port)

    def _add_port(self, port: int, label_text: str = ""):
        if port in self._ports:
            return
        lbl = label_text or KNOWN_PORTS.get(port, "")
        self._ports[port] = lbl

        chip = _PortChip(port, lbl)
        chip.removed.connect(self._remove_port)
        # Inserir antes do stretch
        self._chips_lay.insertWidget(self._chips_lay.count() - 1, chip)

        if port in self._quick_btns:
            self._quick_btns[port].set_added(True)

        self._alert_field.setVisible(False)
        self._upd_chips_hint()

    def _remove_port(self, port: int):
        self._ports.pop(port, None)
        # Remover chip
        for i in range(self._chips_lay.count()):
            item = self._chips_lay.itemAt(i)
            if item and isinstance(item.widget(), _PortChip):
                chip = item.widget()
                if chip._port == port:
                    self._chips_lay.removeWidget(chip)
                    chip.deleteLater()
                    break
        if port in self._quick_btns:
            self._quick_btns[port].set_added(False)
        self._upd_chips_hint()

    def _on_quick_toggle(self, port: int, lbl: str, added: bool):
        if added:
            self._add_port(port, lbl)
        else:
            self._remove_port(port)

    def _upd_chips_hint(self):
        if self._ports:
            self._chips_hint.setText(f"{len(self._ports)} porta(s) selecionada(s) — clique no × para remover")
            self._chips_hint.setStyleSheet(f"color:{COLORS['accent']}; font-size:11px; background:transparent; border:none;")
        else:
            self._chips_hint.setText("Clique nas portas abaixo para selecionar")
            self._chips_hint.setStyleSheet(f"color:{COLORS['text_dim']}; font-size:11px; background:transparent; border:none;")

    def _show_field_error(self, msg: str):
        self._alert_field.set_text(msg)
        self._alert_field.set_kind("danger")
        self._alert_field.setVisible(True)

    def _validar(self) -> bool:
        if not self._ports:
            self._show_field_error("Adicione ao menos uma porta antes de continuar.")
            return False
        return True

    def _on_abrir(self):
        if not self._validar():
            return
        ports     = list(self._ports.keys())
        proto     = self._seg_proto.value
        direction = self._seg_dir.value
        dir_label = {"in": "Entrada", "out": "Saída", "both": "Entrada + Saída"}.get(direction, direction)
        nomes = [f"{p} ({KNOWN_PORTS.get(p, 'porta')})" for p in ports]
        dlg = ConfirmDialog(
            "Abrir portas no Firewall do Windows",
            [
                f"Portas: {', '.join(nomes)}",
                f"Protocolo: {proto}    Direção: {dir_label}",
                "",
                "As regras serão criadas no Firewall do Windows.",
                "Esta operação requer privilégios de Administrador.",
            ],
            self,
        )
        dlg.exec()
        if dlg.confirmado():
            self.go_abrir.emit()

    def _on_remover(self):
        if not self._validar():
            return
        ports = list(self._ports.keys())
        nomes = [f"{p} ({KNOWN_PORTS.get(p, 'porta')})" for p in ports]
        dlg = ConfirmDialog(
            "Remover regras do Firewall do Windows",
            [
                f"Portas: {', '.join(nomes)}",
                "",
                "As regras criadas pelo Futura Setup serão removidas.",
                "Esta operação requer privilégios de Administrador.",
            ],
            self,
        )
        dlg.exec()
        if dlg.confirmado():
            self.go_remover.emit()

    def _carregar_historico(self):
        """Popula o painel de histórico a partir do prefs."""
        # Limpar widgets existentes (exceto stretch)
        while self._hist_lay.count() > 1:
            item = self._hist_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        hist = log.prefs.portas_hist
        if not hist:
            lbl = label("Nenhuma porta usada ainda.", COLORS["text_dim"], 11)
            self._hist_lay.insertWidget(0, lbl)
            return

        for entry in hist[:5]:
            ports     = entry.get("ports", [])
            proto     = entry.get("proto", "TCP")
            direction = entry.get("direction", "in")
            ts        = entry.get("ts", "")
            dir_s     = {"in": "↓", "out": "↑", "both": "↕"}.get(direction, "↕")
            texto     = f"{', '.join(str(p) for p in ports)}  {proto} {dir_s}"
            tooltip   = f"{ts}  ·  {proto}  ·  {direction}"

            btn = make_btn(texto, "secondary", min_width=0)
            btn.setToolTip(tooltip)
            btn.setFixedHeight(26)   # ← compactado
            btn.setStyleSheet(
                f"background:{COLORS['surface2']}; color:{COLORS['text_mid']};"
                f"border:1px solid {COLORS['border']}; border-radius:6px;"
                f"font-size:11px; padding:0 8px;"
            )
            # Ao clicar, restaura as portas e configurações
            btn.clicked.connect(lambda _, e=entry: self._restaurar_historico(e))
            self._hist_lay.insertWidget(self._hist_lay.count() - 1, btn)

    def _restaurar_historico(self, entry: dict):
        """Carrega uma entrada do histórico na UI."""
        # Limpar portas atuais
        for port in list(self._ports.keys()):
            self._remove_port(port)
        self._ports.clear()

        for port in entry.get("ports", []):
            self._add_port(port)

        proto = entry.get("proto", "TCP")
        direction = entry.get("direction", "in")
        self._seg_proto._pick(proto)
        self._seg_dir._pick(direction)

    def reset(self):
        for port in list(self._ports.keys()):
            self._remove_port(port)
        self._ports.clear()
        self._alert_field.setVisible(False)
        self._alert_admin.setVisible(not is_admin())
        self._carregar_historico()

    @property
    def ports(self) -> list[int]:
        return list(self._ports.keys())

    @property
    def proto(self) -> str:
        return self._seg_proto.value

    @property
    def direction(self) -> str:
        return self._seg_dir.value


# ---------------------------------------------------------------------------
# Step 1 — Execução
# ---------------------------------------------------------------------------
class _StepExecucao(QWidget):
    finished = pyqtSignal(bool, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: PortOpenerWorker | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._progress = ProgressBlock("Configurando Firewall...")
        lay.addWidget(self._progress)

        self._console = LogConsole(max_height=0)
        lay.addWidget(self._console, 1)

        footer = QWidget()
        f_lay  = QHBoxLayout(footer)
        f_lay.setContentsMargins(0, 8, 0, 0)
        self._btn_cancel = make_btn("✕  Cancelar", "secondary", min_width=140)
        self._btn_cancel.clicked.connect(self._cancelar)
        f_lay.addStretch()
        f_lay.addWidget(self._btn_cancel)

        lay.addWidget(h_line())
        lay.addWidget(footer, 0)

    def iniciar(self, ports, proto, direction, action):
        self._console.clear_console()
        self._progress.set_progress(0, "Iniciando...")
        self._btn_cancel.setEnabled(True)

        self._worker = PortOpenerWorker(ports, proto, direction, action)
        self._worker.log_line.connect(self._console.append_line)
        self._worker.progress.connect(
            lambda pct, t, d: self._progress.set_progress(pct, f"{t}  {d}".strip())
        )
        self._worker.finished.connect(self.finished)
        self._worker.start()

    def _cancelar(self):
        if self._worker:
            self._btn_cancel.setEnabled(False)
            self._worker.stop()
            self._worker.wait(3000)


# ---------------------------------------------------------------------------
# Step 2 — Resultado
# ---------------------------------------------------------------------------
class _StepResultado(QWidget):
    go_menu   = pyqtSignal()
    go_config = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        self._alert = AlertBox("", "success")
        lay.addWidget(self._alert)

        self._info_lbl = label("", COLORS["text_mid"], 12)
        self._info_lbl.setWordWrap(True)
        lay.addWidget(self._info_lbl)

        lay.addStretch()

        lay.addWidget(h_line())
        lay.addWidget(make_btn_row(
            [("Nova operação", "secondary", self.go_config.emit)],
            back=self.go_menu.emit,
        ))

        theme_manager.theme_changed.connect(self._upd)
        self._upd()

    def _upd(self, _mode: str = ""):
        self._info_lbl.setStyleSheet(f"color:{COLORS['text_mid']}; font-size:12px;")

    def set_resultado(self, sucesso: bool, info: dict):
        action   = info.get("action", "add")
        ports    = info.get("ports", [])
        ok_count = len(info.get("ok", []))
        fl_count = len(info.get("fail", []))
        verb     = "abertas" if action == "add" else "removidas"

        if sucesso:
            self._alert.set_text(f"✔ {ok_count} regra(s) {verb} com sucesso!")
            self._alert.set_kind("success")
            nomes = [KNOWN_PORTS.get(p, str(p)) for p in ports]
            self._info_lbl.setText(
                f"Portas configuradas: {', '.join(str(p) for p in ports)}\n"
                f"Serviços: {', '.join(nomes)}"
            )
        elif info.get("cancelado"):
            self._alert.set_text("⚠ Operação cancelada.")
            self._alert.set_kind("warn")
            self._info_lbl.setText("")
        else:
            self._alert.set_text(
                f"⚠ Concluído com falhas: {ok_count} OK, {fl_count} falha(s). "
                f"Verifique o log acima."
            )
            self._alert.set_kind("warn" if ok_count > 0 else "danger")
            self._info_lbl.setText(
                "Certifique-se de que o programa está sendo executado como Administrador."
            )


# ---------------------------------------------------------------------------
# PagePortOpener — página principal
# ---------------------------------------------------------------------------
class PagePortOpener(QWidget):
    go_menu = pyqtSignal()

    _IDX_CONFIG  = 0
    _IDX_EXEC    = 1
    _IDX_RESULT  = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: PortOpenerWorker | None = None
        self._action = "add"

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 10, 24, 10)   # ← margens compactadas
        root.setSpacing(6)                          # ← compactado

        root.addWidget(PageTitle("", "Firewall — Abrir / Remover Portas"))  # ← "07" removido

        self._stack = QStackedWidget()
        self._cfg   = _StepConfig()
        self._exec  = _StepExecucao()
        self._res   = _StepResultado()

        self._stack.addWidget(self._cfg)   # 0
        self._stack.addWidget(self._exec)  # 1
        self._stack.addWidget(self._res)   # 2

        root.addWidget(self._stack, 1)

        # Conexões
        self._cfg.go_abrir.connect(lambda: self._iniciar("add"))
        self._cfg.go_remover.connect(lambda: self._iniciar("delete"))

        self._exec.finished.connect(self._on_finished)

        self._res.go_menu.connect(self.go_menu)
        self._res.go_config.connect(lambda: self._stack.setCurrentIndex(self._IDX_CONFIG))

    # ------------------------------------------------------------------
    def reset(self):
        self._cfg.reset()
        self._stack.setCurrentIndex(self._IDX_CONFIG)

    def keyPressEvent(self, event):
        """Escape no step de config volta ao menu; execução ignora (worker ativo)."""
        if event.key() == Qt.Key.Key_Escape:
            if self._stack.currentIndex() == self._IDX_CONFIG:
                self.go_menu.emit()
        else:
            super().keyPressEvent(event)

    def _iniciar(self, action: str):
        self._action = action
        ports     = self._cfg.ports
        proto     = self._cfg.proto
        direction = self._cfg.direction

        self._stack.setCurrentIndex(self._IDX_EXEC)
        self._exec.iniciar(ports, proto, direction, action)
        self._worker = self._exec._worker

    def _on_finished(self, sucesso: bool, info: dict):
        self._worker = None
        # Salvar no histórico se foi uma abertura bem-sucedida
        if sucesso and info.get("action") == "add":
            try:
                log.prefs.add_portas(
                    info.get("ports", []),
                    self._cfg.proto,
                    self._cfg.direction,
                )
            except Exception:
                pass
        self._res.set_resultado(sucesso, info)
        self._stack.setCurrentIndex(self._IDX_RESULT)
