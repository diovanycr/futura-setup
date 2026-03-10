# =============================================================================
# FUTURA SETUP — Página: Diagnóstico de Conectividade (MODO 08)
# Melhorias v2:
#   - Botões substituídos por _make_primary_btn/_make_secondary_btn (padrão visual correto)
# Correções v3:
#   - _DiagCard._COLORS: "success" → "accent2" (chave correta em COLORS do tema)
# =============================================================================

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QStackedWidget, QPushButton,
)
from PyQt6.QtGui import QFont

from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets import (
    PageTitle, SectionHeader, AlertBox, make_primary_btn, make_secondary_btn,
    btn_row, spacer, h_line, label,
)
from core.diagnostico import DiagnosticoWorker, DiagItem




# ── CARD DE RESULTADO DE TESTE ─────────────────────────────────────────────────

class _DiagCard(QWidget):
    _ICONS  = {"ok": "✔", "warn": "⚠", "error": "✕", "running": "…"}

    # FIX: "success" não existe em COLORS — a chave correta para verde é "accent2".
    _COLORS = {
        "ok":      ("accent2", "text"),
        "warn":    ("warn",    "text_mid"),
        "error":   ("danger",  "text_mid"),
        "running": ("accent",  "text_dim"),
    }

    def __init__(self, item: DiagItem, parent=None):
        super().__init__(parent)
        self.setObjectName("DiagCard")
        self._item = item

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(14)

        self._icon_lbl = QLabel(self._ICONS.get(item.status, "…"))
        self._icon_lbl.setObjectName("dc_icon")
        self._icon_lbl.setFont(QFont(FONT_SANS, 14, QFont.Weight.Bold))
        self._icon_lbl.setFixedWidth(22)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        txt_w = QWidget()
        txt_w.setObjectName("dc_txt")
        txt = QVBoxLayout(txt_w)
        txt.setContentsMargins(0, 0, 0, 0)
        txt.setSpacing(3)

        self._nome_lbl = QLabel(item.nome)
        self._nome_lbl.setObjectName("dc_nome")
        self._nome_lbl.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))

        self._detalhe_lbl = QLabel(item.detalhe or "Aguardando…")
        self._detalhe_lbl.setObjectName("dc_detalhe")
        self._detalhe_lbl.setFont(QFont(FONT_MONO, 10))
        self._detalhe_lbl.setWordWrap(True)

        txt.addWidget(self._nome_lbl)
        txt.addWidget(self._detalhe_lbl)

        lay.addWidget(self._icon_lbl)
        lay.addWidget(txt_w, 1)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def atualizar(self, item: DiagItem):
        self._item = item
        self._icon_lbl.setText(self._ICONS.get(item.status, "…"))
        self._detalhe_lbl.setText(item.detalhe or "Aguardando…")
        self._upd()

    def _upd(self, _mode: str = ""):
        icon_key, txt_key = self._COLORS.get(self._item.status, ("accent", "text_dim"))
        self.setStyleSheet(f"""
            QWidget#DiagCard {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            QWidget#dc_txt    {{ background: transparent; border: none; }}
            QLabel#dc_icon    {{ color: {COLORS[icon_key]}; background: transparent; border: none; }}
            QLabel#dc_nome    {{ color: {COLORS['text']}; background: transparent; border: none; }}
            QLabel#dc_detalhe {{ color: {COLORS[txt_key]}; background: transparent; border: none; }}
        """)


# ── PÁGINA PRINCIPAL ───────────────────────────────────────────────────────────

class PageDiagnostico(QWidget):
    go_menu = pyqtSignal()

    _IDX_CONFIG    = 0
    _IDX_RUNNING   = 1
    _IDX_RESULTADO = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: DiagnosticoWorker | None = None
        self._alvo   = ""
        self._cards: list[_DiagCard] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 36, 40, 36)
        lay.setSpacing(0)

        lay.addWidget(PageTitle("DIAGNÓSTICO", "Conectividade com Servidor"))

        self._stack = QStackedWidget()
        lay.addWidget(self._stack)

        self._stack.addWidget(self._build_config())
        self._stack.addWidget(self._build_running())
        self._stack.addWidget(self._build_resultado())

        self._go_step(self._IDX_CONFIG)

    def reset(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        self._worker = None
        self._campo_alvo.clear()
        self._alert_config.set_text("")
        self._alert_config.setVisible(False)
        self._go_step(self._IDX_CONFIG)

    # ── BUILD ──────────────────────────────────────────────────────────────────

    def _build_config(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self._alert_config = AlertBox("", "warn")
        self._alert_config.setVisible(False)
        lay.addWidget(self._alert_config)

        lay.addWidget(SectionHeader("Servidor a diagnosticar"))

        desc = label(
            "Digite o IP ou hostname do servidor Futura. "
            "Serão testados: ping, resolução de nome, acesso ao share, "
            "porta do Firebird e leitura da versão.",
            COLORS["text_mid"], 11,
        )
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addWidget(spacer(h=4))

        self._campo_alvo = QLineEdit()
        self._campo_alvo.setPlaceholderText("Ex: 192.168.1.10  ou  SERVIDOR-01")
        self._campo_alvo.returnPressed.connect(self._iniciar)
        self._campo_alvo.setObjectName("campo_alvo")
        lay.addWidget(self._campo_alvo)

        lay.addWidget(spacer(h=8))
        lay.addWidget(h_line())
        lay.addWidget(spacer(h=8))

        btn_iniciar = make_primary_btn("🔍  INICIAR DIAGNÓSTICO", 160)
        btn_iniciar.clicked.connect(self._iniciar)
        btn_voltar = make_secondary_btn("← VOLTAR", 80)
        btn_voltar.clicked.connect(self.go_menu.emit)
        lay.addWidget(btn_row(btn_iniciar, btn_voltar))

        lay.addStretch()

        self._upd_config()
        theme_manager.theme_changed.connect(self._upd_config)
        return w

    def _upd_config(self, _mode: str = ""):
        self._campo_alvo.setStyleSheet(f"""
            QLineEdit#campo_alvo {{
                background: {COLORS['surface']};
                border: 1.5px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 12px;
                color: {COLORS['text']};
                font-size: 11px;
            }}
            QLineEdit#campo_alvo:focus {{
                border-color: {COLORS['accent']};
            }}
        """)

    def _build_running(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self._running_titulo = label("Testando…", COLORS["text"], 13)
        self._running_titulo.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
        lay.addWidget(self._running_titulo)

        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background: transparent;")
        self._cards_lay = QVBoxLayout(self._cards_container)
        self._cards_lay.setContentsMargins(0, 0, 0, 0)
        self._cards_lay.setSpacing(8)
        lay.addWidget(self._cards_container)

        lay.addStretch()
        return w

    def _build_resultado(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self._res_alert = AlertBox("", "success")
        lay.addWidget(self._res_alert)

        self._res_cards_container = QWidget()
        self._res_cards_container.setStyleSheet("background: transparent;")
        self._res_cards_lay = QVBoxLayout(self._res_cards_container)
        self._res_cards_lay.setContentsMargins(0, 0, 0, 0)
        self._res_cards_lay.setSpacing(8)
        lay.addWidget(self._res_cards_container)

        lay.addWidget(spacer(h=4))
        lay.addWidget(h_line())
        lay.addWidget(spacer(h=8))

        btn_novo = make_secondary_btn("🔄  NOVO DIAGNÓSTICO", 160)
        btn_novo.clicked.connect(self._go_novo)
        btn_voltar = make_secondary_btn("← VOLTAR", 80)
        btn_voltar.clicked.connect(self.go_menu.emit)
        lay.addWidget(btn_row(btn_novo, btn_voltar))

        lay.addStretch()
        return w

    # ── AÇÕES ──────────────────────────────────────────────────────────────────

    def _iniciar(self):
        alvo = self._campo_alvo.text().strip()
        if not alvo:
            self._alert_config.set_text("⚠  Digite o IP ou hostname do servidor.")
            self._alert_config.setVisible(True)
            return

        self._alvo = alvo
        self._alert_config.setVisible(False)

        while self._cards_lay.count():
            item = self._cards_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        nomes = [
            "Ping (ICMP)",
            "Resolução de hostname",
            f"Share \\\\{alvo}\\Futura",
            "Porta 3050 (Firebird)",
            "Versão do Futura",
        ]
        for nome in nomes:
            card = _DiagCard(DiagItem(nome, "running"))
            self._cards.append(card)
            self._cards_lay.addWidget(card)

        self._running_titulo.setText(f"Testando {alvo}…")
        self._go_step(self._IDX_RUNNING)

        self._worker = DiagnosticoWorker(alvo)
        self._worker.item_pronto.connect(self._on_item_pronto)
        self._worker.finalizado.connect(self._on_finalizado)
        self._worker.start()

    def _on_item_pronto(self, idx: int, item: DiagItem):
        if idx < len(self._cards):
            self._cards[idx].atualizar(item)

    def _on_finalizado(self, itens: list[DiagItem]):
        self._worker = None

        while self._res_cards_lay.count():
            i = self._res_cards_lay.takeAt(0)
            if i.widget():
                i.widget().deleteLater()

        errors = sum(1 for it in itens if it.status == "error")
        warns  = sum(1 for it in itens if it.status == "warn")

        if errors == 0 and warns == 0:
            resumo = f"✔ Todos os testes passaram — {self._alvo} está acessível."
            kind   = "success"
        elif errors == 0:
            resumo = f"⚠ {warns} aviso(s) encontrado(s) — {self._alvo} parcialmente acessível."
            kind   = "warn"
        else:
            resumo = f"✕ {errors} erro(s) encontrado(s) — {self._alvo} pode ter problemas de conectividade."
            kind   = "error"

        self._res_alert.set_text(resumo)
        self._res_alert.set_kind(kind)

        for item in itens:
            card = _DiagCard(item)
            self._res_cards_lay.addWidget(card)

        self._go_step(self._IDX_RESULTADO)

    def _go_novo(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(1000)
        self._worker = None
        self._go_step(self._IDX_CONFIG)

    def _go_step(self, idx: int):
        self._stack.setCurrentIndex(idx)

    # ── TECLADO ────────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            idx = self._stack.currentIndex()
            if idx == self._IDX_CONFIG:
                self.go_menu.emit()
            elif idx == self._IDX_RESULTADO:
                self._go_novo()
        else:
            super().keyPressEvent(event)
