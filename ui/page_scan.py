# =============================================================================
# FUTURA SETUP — Página: Escaneamento de Rede
# Melhorias v2:
#   - ToggleRow.set_checked_silent(): encapsula blockSignals
#   - Usa MetodoScan (NamedTuple) — acesso por .key/.nome/.descricao
#   - ServerItem.selected (pyqtSignal)
# Melhorias v3:
#   - Histórico de servidores recentes clicável
#   - _build_hist_section(), _usar_servidor_hist()
# Melhorias v4:
#   - ToggleRow altura reduzida; QScrollArea
# Melhorias v5:
#   - Grid 2x2 com MethodCard
# Melhorias v6:
#   - Botões centralizados
# Melhorias v7:
#   - Botões com estilo inline garantido (primary azul, secondary com borda)
#   - 5º card (Sequencial Rede Lenta) corrigido: toggle à direita
#   - _make_primary_btn / _make_secondary_btn: helpers com estilo aplicado diretamente
# =============================================================================

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QStackedWidget, QScrollArea, QGridLayout, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QFont, QPainter, QColor, QBrush

from ui.widgets import (
    PageTitle, SectionHeader, AlertBox, LogConsole,
    ServerItem, spacer
)
from ui.theme import COLORS, FONT_MONO, FONT_SANS
from ui.theme_manager import theme_manager
from core.network import ScanWorker, Servidor


# ── HELPERS DE BOTÃO ─────────────────────────────────────────────────────────
# Aplicam estilo inline para garantir que primary/secondary sejam visíveis
# independente de herança ou ordem do stylesheet global.

def _make_primary_btn(text: str, min_width: int = 160) -> QPushButton:
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
    btn.setFont(QFont(FONT_SANS, 13))
    _apply_secondary(btn)
    theme_manager.theme_changed.connect(lambda _: _apply_secondary(btn))
    return btn

def _apply_primary(btn: QPushButton):
    accent        = COLORS["accent"]
    accent_hover  = COLORS["accent_hover"]
    accent_press  = COLORS["accent_press"]
    text_color    = "#ffffff" if theme_manager.mode == "light" else "#001826"
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {accent};
            color: {text_color};
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-weight: 700;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {accent_hover};
        }}
        QPushButton:pressed {{
            background-color: {accent_press};
        }}
        QPushButton:disabled {{
            background-color: {COLORS['panel_hover']};
            color: {COLORS['text_disabled']};
        }}
    """)

def _apply_secondary(btn: QPushButton):
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: transparent;
            color: {COLORS['text']};
            border: 1.5px solid {COLORS['btn_border']};
            border-radius: 6px;
            padding: 8px 20px;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {COLORS['panel_hover']};
            border-color: {COLORS['text_dim']};
        }}
        QPushButton:pressed {{
            background-color: {COLORS['panel_press']};
        }}
    """)


# ── TOGGLE SWITCH ─────────────────────────────────────────────────────────────

class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked  = checked
        self.__thumb_x = 22 if checked else 2
        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._anim = QPropertyAnimation(self, b"thumb_x")
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        theme_manager.theme_changed.connect(lambda _: self.update())

    @pyqtProperty(int)
    def thumb_x(self):
        return self.__thumb_x

    @thumb_x.setter
    def thumb_x(self, v):
        self.__thumb_x = v
        self.update()

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, v: bool, emit: bool = True):
        if v == self._checked:
            return
        self._checked = v
        self._anim.stop()
        self._anim.setStartValue(self.__thumb_x)
        self._anim.setEndValue(22 if v else 2)
        self._anim.start()
        if emit:
            self.toggled.emit(v)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QColor(COLORS["accent"]) if self._checked else QColor(COLORS["border"])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(track))
        p.drawRoundedRect(0, 4, 44, 16, 8, 8)
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(self.__thumb_x, 2, 20, 20)
        p.end()


# ── METHOD CARD (grid 2x2) ────────────────────────────────────────────────────

class MethodCard(QWidget):
    """Card compacto para o grid 2x2 de métodos de escaneamento."""

    def __init__(self, name: str, desc: str, checked: bool = False, parent=None):
        super().__init__(parent)
        self._state = "normal"
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(64)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 12, 0)
        lay.setSpacing(8)

        # Texto (esquerda)
        txt_w = QWidget()
        txt_w.setObjectName("card_txt")
        txt_w.setStyleSheet("background: transparent;")
        txt = QVBoxLayout(txt_w)
        txt.setSpacing(1)
        txt.setContentsMargins(0, 0, 0, 0)

        self._name_lbl = QLabel(name)
        self._name_lbl.setObjectName("card_name")
        self._name_lbl.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))

        self._desc_lbl = QLabel(desc)
        self._desc_lbl.setObjectName("card_desc")
        self._desc_lbl.setFont(QFont(FONT_SANS, 9))
        self._desc_lbl.setWordWrap(True)

        txt.addStretch()
        txt.addWidget(self._name_lbl)
        txt.addWidget(self._desc_lbl)
        txt.addStretch()

        # Toggle — wrapper com largura fixa garante posição à direita
        # mesmo quando o card ocupa as 2 colunas do grid
        self._toggle = ToggleSwitch(checked)
        self._toggle.toggled.connect(self._upd)

        toggle_w = QWidget()
        toggle_w.setFixedWidth(60)
        toggle_w.setStyleSheet("background: transparent;")
        toggle_lay = QHBoxLayout(toggle_w)
        toggle_lay.setContentsMargins(0, 0, 8, 0)
        toggle_lay.addStretch()
        toggle_lay.addWidget(self._toggle, 0, Qt.AlignmentFlag.AlignVCenter)

        lay.addWidget(txt_w, 1)
        lay.addWidget(toggle_w)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._toggle.setChecked(not self._toggle.isChecked())

    def enterEvent(self, e):
        self._state = "hover"
        self._upd()

    def leaveEvent(self, e):
        self._state = "normal"
        self._upd()

    def _upd(self, _=None):
        checked = self._toggle.isChecked()
        if checked:
            bg, border = COLORS["accent_dim"], COLORS["accent"]
        elif self._state == "hover":
            bg, border = COLORS["panel_hover"], COLORS["border"]
        else:
            bg, border = COLORS["surface"], COLORS["border"]

        self.setStyleSheet(f"""
            MethodCard {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 8px;
            }}
            QWidget#card_txt  {{ border: none; background: transparent; }}
            QLabel#card_name  {{ color: {COLORS['text']}; border: none; background: transparent; }}
            QLabel#card_desc  {{ color: {COLORS['text_mid']}; border: none; background: transparent; }}
        """)

    def isChecked(self) -> bool:
        return self._toggle.isChecked()

    def setChecked(self, v: bool):
        self._toggle.setChecked(v)

    def set_checked_silent(self, v: bool):
        self._toggle.setChecked(v, emit=False)
        self._upd()


# ── PAGE SCAN ─────────────────────────────────────────────────────────────────

class PageScan(QWidget):
    servidor_selecionado = pyqtSignal(object)
    cancelado            = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._servidores: list[Servidor] = []
        self._worker: ScanWorker | None  = None
        self._server_widgets: list[ServerItem] = []
        self._selected_servidor: Servidor | None = None
        self._toggle_rows: list[MethodCard] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 36, 40, 36)
        lay.setSpacing(0)

        lay.addWidget(PageTitle("DESCOBERTA", "Escaneamento de Rede"))

        self._stack = QStackedWidget()
        lay.addWidget(self._stack)

        self._stack.addWidget(self._build_method_page())
        self._stack.addWidget(self._build_scanning_page())
        self._stack.addWidget(self._build_results_page())

    # ── BUILD ──────────────────────────────────────────────────────────────────

    def _build_method_page(self) -> QWidget:
        outer = QWidget()
        outer.setStyleSheet("background: transparent;")
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 16)
        lay.setSpacing(10)

        lay.addWidget(SectionHeader("Método de Escaneamento"))

        # ── Grid 2x2 + 5º card em linha inteira ──────────────────────────────
        grid_w = QWidget()
        grid_w.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        metodos = ScanWorker.METODOS
        for i, metodo in enumerate(metodos):
            card = MethodCard(metodo.nome, metodo.descricao, checked=(i == 0))
            card._toggle.toggled.connect(lambda v, idx=i: self._on_toggle(idx, v))
            self._toggle_rows.append(card)

            # Todos no grid — 5 métodos: linhas 0 e 1 completas + linha 2 col 0
            grid.addWidget(card, i // 2, i % 2)
        lay.addWidget(grid_w)
        lay.addWidget(spacer(h=8))

        # ── Botões centralizados ──────────────────────────────────────────────
        self._btn_scan = _make_primary_btn("▶  Iniciar Escaneamento", 210)
        self._btn_scan.clicked.connect(self._start_scan)

        self._btn_cancel = _make_secondary_btn("Cancelar", 110)
        self._btn_cancel.clicked.connect(self.cancelado.emit)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addStretch()
        btns.addWidget(self._btn_scan)
        btns.addWidget(self._btn_cancel)
        btns.addStretch()

        btn_w = QWidget()
        btn_w.setLayout(btns)
        btn_w.setStyleSheet("background: transparent;")
        lay.addWidget(btn_w)

        lay.addWidget(spacer(h=8))

        # ── Histórico ─────────────────────────────────────────────────────────
        self._hist_section = QWidget()
        self._hist_section.setStyleSheet("background: transparent;")
        self._hist_lay = QVBoxLayout(self._hist_section)
        self._hist_lay.setContentsMargins(0, 0, 0, 0)
        self._hist_lay.setSpacing(6)
        lay.addWidget(self._hist_section)

        lay.addStretch()
        scroll.setWidget(w)
        outer_lay.addWidget(scroll)
        return outer

    def _build_hist_section(self):
        """Reconstrói o painel de histórico de servidores a partir das prefs."""
        while self._hist_lay.count():
            item = self._hist_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        from core.logger import log as _log
        hist = _log.prefs.servidores_hist
        if not hist:
            self._hist_section.setVisible(False)
            return

        self._hist_section.setVisible(True)
        self._hist_lay.addWidget(SectionHeader("Servidores Recentes"))

        for entry in hist[:5]:
            ip       = entry.get("ip", "")
            hostname = entry.get("hostname", ip)
            path     = entry.get("path", f"\\\\{hostname}\\Futura")
            version  = entry.get("version", "")
            item = ServerItem(hostname, ip, path, version)
            item.selected.connect(self._usar_servidor_hist)
            self._hist_lay.addWidget(item)

    def _usar_servidor_hist(self, item: "ServerItem"):
        srv = Servidor(ip=item.ip, hostname=item.hostname, path=item.path)
        self.servidor_selecionado.emit(srv)

    def _on_toggle(self, idx: int, checked: bool):
        if checked:
            for i, card in enumerate(self._toggle_rows):
                if i != idx and card.isChecked():
                    card.set_checked_silent(False)

    def _get_selected_idx(self) -> int:
        for i, card in enumerate(self._toggle_rows):
            if card.isChecked():
                return i
        return 0

    def _build_scanning_page(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        status_box = QWidget()
        status_box.setObjectName("status_box")
        status_box.setStyleSheet(
            f"QWidget#status_box {{"
            f"  background: {COLORS['surface']};"
            f"  border: 1px solid {COLORS['border']};"
            f"  border-radius: 8px;"
            f"}}"
        )
        status_lay = QVBoxLayout(status_box)
        status_lay.setContentsMargins(24, 20, 24, 20)
        status_lay.setSpacing(8)

        self._spin_lbl = QLabel("◌")
        self._spin_lbl.setFont(QFont(FONT_MONO, 28))
        self._spin_lbl.setStyleSheet(f"color: {COLORS['accent']}; background: transparent; border: none;")
        self._spin_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._status_lbl = QLabel("ESCANEANDO REDE...")
        self._status_lbl.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
        self._status_lbl.setStyleSheet(f"color: {COLORS['text']}; background: transparent; border: none;")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._status_sub = QLabel("Aguardando resultados...")
        self._status_sub.setFont(QFont(FONT_SANS, 10))
        self._status_sub.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent; border: none;")
        self._status_sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        status_lay.addWidget(self._spin_lbl)
        status_lay.addWidget(self._status_lbl)
        status_lay.addWidget(self._status_sub)

        self._scan_console = LogConsole(max_height=220)

        btn_stop = _make_secondary_btn("⊗  Parar", 140)
        btn_stop.clicked.connect(self._stop_scan)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_stop)
        btn_row.addStretch()
        btn_row_w = QWidget()
        btn_row_w.setLayout(btn_row)
        btn_row_w.setStyleSheet("background: transparent;")

        lay.addWidget(status_box)
        lay.addWidget(self._scan_console)
        lay.addWidget(btn_row_w)
        lay.addStretch()

        self._spin_chars = ["◐", "◓", "◑", "◒"]
        self._spin_idx   = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._tick_spinner)
        return w

    def _build_results_page(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        self._result_alert = AlertBox("Servidores encontrados.", "info")
        lay.addWidget(self._result_alert)
        lay.addWidget(SectionHeader("Servidores Encontrados"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        # Expande para ocupar todo o espaço disponível entre header e botões
        from PyQt6.QtWidgets import QSizePolicy
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._server_container = QWidget()
        self._server_container.setStyleSheet("background: transparent;")
        self._server_list_lay  = QVBoxLayout(self._server_container)
        self._server_list_lay.setContentsMargins(0, 0, 0, 0)
        self._server_list_lay.setSpacing(8)
        self._server_list_lay.addStretch()
        scroll.setWidget(self._server_container)
        lay.addWidget(scroll, 1)  # stretch=1 — ocupa todo espaço restante

        self._btn_usar = _make_primary_btn("Usar Servidor Selecionado", 220)
        self._btn_usar.clicked.connect(self._confirm_server)

        btn_novo = _make_secondary_btn("← Novo Escaneamento", 180)
        btn_novo.clicked.connect(lambda: self._stack.setCurrentIndex(0))

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addStretch()
        btns.addWidget(self._btn_usar)
        btns.addWidget(btn_novo)
        btns.addStretch()

        btn_w = QWidget()
        btn_w.setLayout(btns)
        btn_w.setStyleSheet("background: transparent;")
        lay.addWidget(btn_w)
        return w

    # ── AÇÕES ─────────────────────────────────────────────────────────────────

    def reset(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        self._spin_timer.stop()
        self._build_hist_section()
        self._stack.setCurrentIndex(0)

    def _start_scan(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)

        idx    = self._get_selected_idx()
        metodo = ScanWorker.METODOS[idx]
        self._scan_console.clear_console()
        self._status_lbl.setText("ESCANEANDO REDE...")
        self._status_sub.setText(f"Método: {metodo.nome}")
        self._stack.setCurrentIndex(1)
        self._spin_timer.start(180)

        self._worker = ScanWorker(metodo=metodo.key)
        self._worker.log_line.connect(self._scan_console.append_line)
        self._worker.status_text.connect(self._status_sub.setText)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.start()

    def _stop_scan(self):
        if self._worker:
            self._worker.stop()
        self._spin_timer.stop()
        self._stack.setCurrentIndex(0)

    def _tick_spinner(self):
        self._spin_lbl.setText(self._spin_chars[self._spin_idx % len(self._spin_chars)])
        self._spin_idx += 1

    def _on_scan_finished(self, servidores: list):
        self._spin_timer.stop()
        self._servidores = servidores
        if not servidores:
            self._status_lbl.setText("NENHUM SERVIDOR ENCONTRADO")
            self._status_sub.setText("Verifique a rede e tente novamente")
            return
        self._status_lbl.setText(f"{len(servidores)} SERVIDOR(ES) ENCONTRADO(S)")
        self._result_alert.set_text(
            f"{len(servidores)} servidor(es) Futura encontrado(s) na rede."
        )
        for w in self._server_widgets:
            self._server_list_lay.removeWidget(w)
            w.deleteLater()
        self._server_widgets.clear()
        self._selected_servidor = None

        for srv in servidores:
            item = ServerItem(srv.hostname, srv.ip, srv.path, srv.version)
            item.selected.connect(self._select_server)
            self._server_list_lay.insertWidget(self._server_list_lay.count() - 1, item)
            self._server_widgets.append(item)

        if self._server_widgets:
            self._select_server(self._server_widgets[0])
        self._stack.setCurrentIndex(2)

    def _select_server(self, clicked_item: ServerItem):
        for w in self._server_widgets:
            w.set_selected(False)
        clicked_item.set_selected(True)
        for srv in self._servidores:
            if srv.ip == clicked_item.ip:
                self._selected_servidor = srv
                break

    def _confirm_server(self):
        if self._selected_servidor:
            self.servidor_selecionado.emit(self._selected_servidor)
