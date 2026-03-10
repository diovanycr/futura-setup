"""
ui/page_shutdown_online.py — Página: Shutdown / Online do banco Firebird.

Fluxo da pagina:
  Step 0 — Selecionar banco + botoes Shutdown / Online
  Step 1 — Resultado do comando executado
"""

from __future__ import annotations

import os
import subprocess

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QApplication,
    QFrame, QFileDialog, QLineEdit, QStackedWidget,
)

from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets import (
    PageTitle, SectionHeader, AlertBox, make_primary_btn, 
    make_secondary_btn, make_folder_btn, btn_row, spacer, label, h_line
)
from core.logger import log


# ---------------------------------------------------------------------------
# Localizar gfix.exe / gstat.exe
# ---------------------------------------------------------------------------

_GFIX_CANDIDATES = [
    r"C:\Program Files\Firebird\Firebird_5_0\gfix.exe",
    r"C:\Program Files\Firebird\Firebird_4_0\gfix.exe",
    r"C:\Program Files\Firebird\Firebird_3_0\gfix.exe",
    r"C:\Program Files\Firebird\Firebird_2_5\gfix.exe",
    r"C:\Program Files (x86)\Firebird\Firebird_5_0\gfix.exe",
    r"C:\Program Files (x86)\Firebird\Firebird_4_0\gfix.exe",
    r"C:\Program Files (x86)\Firebird\Firebird_3_0\gfix.exe",
    r"C:\Program Files (x86)\Firebird\Firebird_2_5\gfix.exe",
    r"C:\Firebird\gfix.exe",
]


def _encontrar_gfix() -> str | None:
    for path in _GFIX_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


def _encontrar_gstat() -> str | None:
    gfix = _encontrar_gfix()
    if gfix:
        gstat = os.path.join(os.path.dirname(gfix), "gstat.exe")
        if os.path.isfile(gstat):
            return gstat
    return None


def _verificar_status_banco(gstat: str, banco: str) -> str:
    """Roda gstat -h e extrai o status do banco."""
    try:
        if not (banco.startswith("localhost:") or banco.startswith("127.0.0.1:")):
            banco = f"localhost:{banco}"
        proc = subprocess.run(
            [gstat, "-user", "SYSDBA", "-pass", "sbofutura", banco, "-h"],
            capture_output=True, text=True, encoding="oem", timeout=15,
        )
        saida = (proc.stdout or "") + (proc.stderr or "")
        for linha in saida.splitlines():
            if "Attributes" in linha:
                linha_lower = linha.lower()
                if "shutdown" in linha_lower:
                    return "shutdown"
                if "single" in linha_lower:
                    return "single-user"
                return "online"
        return "online"
    except Exception as e:
        return f"erro: {e}"


# ---------------------------------------------------------------------------
# Helpers de botao
# ---------------------------------------------------------------------------

def make_danger_btn(text: str, min_width: int = 120) -> QPushButton:
    btn = QPushButton(text)
    btn.setMinimumWidth(min_width)
    btn.setMinimumHeight(35)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
    _apply_danger(btn)
    theme_manager.theme_changed.connect(lambda _: _apply_danger(btn))
    return btn

def _apply_danger(btn: QPushButton):
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {COLORS['danger']};
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-weight: 700;
            font-size: 13px;
        }}
        QPushButton:hover {{ background-color: {COLORS['danger']}; opacity: 0.9; }}
        QPushButton:pressed {{ background-color: {COLORS['danger']}; opacity: 0.8; }}
        QPushButton:disabled {{
            background-color: {COLORS['panel_hover']};
            color: {COLORS['text_disabled']};
        }}
    """)


# ---------------------------------------------------------------------------
# Campo .fdb com botao explorer
# ---------------------------------------------------------------------------

class _PathFieldDB(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self._lbl  = QLabel("Caminho do banco de dados (.fdb)")
        self._edit = QLineEdit()
        self._edit.setPlaceholderText(r"Ex: C:\Futura\Dados\DADOS.fdb")
        self._btn = make_folder_btn(self)
        self._btn.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(self._edit, 1)
        row.addWidget(self._btn)
        lay.addWidget(self._lbl)
        lay.addLayout(row)
        theme_manager.theme_changed.connect(self._upd)
        self._upd()

    def _upd(self, _mode: str = ""):
        self._lbl.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 10px; font-weight: 600;"
            f" font-family: {FONT_SANS};"
        )
        self._edit.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1.5px solid {COLORS['border']};
                border-radius: 5px;
                padding: 4px 12px;
                font-size: 11px;
            }}
            QLineEdit:focus {{ border-color: {COLORS['accent']}; }}
        """)


    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar banco de dados Firebird", "C:\\",
            "Banco Firebird (*.fdb);;Todos os arquivos (*.*)",
        )
        if path:
            self._edit.setText(os.path.normpath(path))

    @property
    def value(self) -> str:
        return self._edit.text().strip()

    @value.setter
    def value(self, v: str):
        self._edit.setText(v)


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

class _StatusWorker(QThread):
    concluido = pyqtSignal(str)

    def __init__(self, gstat: str, banco: str):
        super().__init__()
        self._gstat = gstat
        self._banco = banco

    def run(self):
        self.concluido.emit(_verificar_status_banco(self._gstat, self._banco))


class _GfixWorker(QThread):
    concluido = pyqtSignal(bool, str, str)
    erro      = pyqtSignal(str)

    def __init__(self, gfix: str, banco: str, modo: str):
        super().__init__()
        self._gfix  = gfix
        self._banco = banco
        self._modo  = modo

    def run(self):
        user  = "SYSDBA"
        pwd   = "sbofutura"
        banco = self._banco
        if not (banco.startswith("localhost:") or banco.startswith("127.0.0.1:")):
            banco = f"localhost:{banco}"

        if self._modo == "shutdown":
            args = [self._gfix, "-user", user, "-pass", pwd,
                    "-shut", "full", "-force", "0", banco]
        else:
            args = [self._gfix, "-user", user, "-pass", pwd, banco, "-online"]

        cmd_str = " ".join(f'"{a}"' if " " in a else a for a in args)
        try:
            proc = subprocess.run(
                args, capture_output=True, text=True, encoding="oem", timeout=60,
            )
            saida = (proc.stdout or "").strip()
            if proc.stderr.strip():
                saida = (saida + "\n" + proc.stderr.strip()).strip()
            saida = saida or "(sem saída)"
            self.concluido.emit(proc.returncode == 0, cmd_str, saida)
        except subprocess.TimeoutExpired:
            self.erro.emit("Timeout: o comando demorou mais de 60s.")
        except Exception as e:
            self.erro.emit(str(e))


# ---------------------------------------------------------------------------
# Painel de resultado do comando
# ---------------------------------------------------------------------------

class _PainelResultado(QFrame):
    def __init__(self, sucesso: bool, modo: str, cmd: str, saida: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ResultFrame")
        op = "Shutdown" if modo == "shutdown" else "Online"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(6)

        header_row = QHBoxLayout()
        icone = QLabel("✓" if sucesso else "✗")
        icone.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        icone.setStyleSheet(
            f"color: {COLORS['accent2'] if sucesso else COLORS['danger']}; background: transparent;"
        )
        lbl_nome = QLabel(f"{op} — {'sucesso' if sucesso else 'falha'}")
        lbl_nome.setFont(QFont(FONT_SANS, 10, QFont.Weight.Bold))
        lbl_nome.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        header_row.addWidget(icone)
        header_row.addWidget(lbl_nome, 1)
        lay.addLayout(header_row)

        lbl_cmd_t = QLabel("Comando executado")
        lbl_cmd_t.setFont(QFont(FONT_SANS, 9))
        lbl_cmd_t.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
        lay.addWidget(lbl_cmd_t)

        lbl_cmd = QLabel(cmd)
        lbl_cmd.setFont(QFont(FONT_MONO, 9))
        lbl_cmd.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        lbl_cmd.setWordWrap(True)
        lbl_cmd.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(lbl_cmd)

        if saida and saida != "(sem saída)":
            lbl_out_t = QLabel("Saída do gfix")
            lbl_out_t.setFont(QFont(FONT_SANS, 9))
            lbl_out_t.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
            lay.addWidget(lbl_out_t)
            lbl_out = QLabel(saida)
            lbl_out.setFont(QFont(FONT_MONO, 9))
            lbl_out.setStyleSheet(
                f"color: {COLORS['danger'] if not sucesso else COLORS['text_dim']}; background: transparent;"
            )
            lbl_out.setWordWrap(True)
            lbl_out.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lay.addWidget(lbl_out)

        border_color = COLORS["accent2"] if sucesso else COLORS["danger"]
        self.setStyleSheet(f"""
            QFrame#ResultFrame {{
                background: {COLORS['surface']};
                border: 1.5px solid {border_color};
                border-radius: 6px;
            }}
        """)


# ---------------------------------------------------------------------------
# Step 0 — Formulario
# ---------------------------------------------------------------------------

class _StepFormulario(QWidget):
    executar = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._gfix_path  = _encontrar_gfix()
        self._gstat_path = _encontrar_gstat()
        self._worker_status: QThread | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        lay   = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 10, 0)
        lay.setSpacing(7)

        if not self._gfix_path:
            self._alert = AlertBox(
                "gfix.exe não encontrado nos caminhos padrão do Firebird.", "danger"
            )
        else:
            self._alert = AlertBox(
                "Selecione o banco e escolha a operação.", "info"
            )
        lay.addWidget(self._alert)

        lay.addWidget(SectionHeader("Banco de Dados"))
        self._fld_db = _PathFieldDB()
        lay.addWidget(self._fld_db)

        lay.addWidget(SectionHeader("Status do Banco"))
        status_row = QHBoxLayout()
        self._btn_status = make_secondary_btn("🔍  VERIFICAR STATUS", 148)
        self._btn_status.clicked.connect(self._on_verificar_status)
        self._btn_status.setEnabled(bool(self._gstat_path))
        self._status_badge = label("—", COLORS["text_dim"], 10)
        self._status_badge.setFont(QFont(FONT_MONO, 10, QFont.Weight.Bold))
        self._status_badge.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._atualizar_badge("—")
        lay.addWidget(btn_row(self._btn_status, self._status_badge))

        lay.addWidget(SectionHeader("Comandos"))
        for titulo, desc, cor in [
            (
                "Shutdown (full)",
                "gfix ... -shut full -force 0 localhost:<banco>\nDesconecta todos os usuários imediatamente.",
                COLORS["danger"],
            ),
            (
                "Online",
                "gfix ... localhost:<banco> -online\nRetorna o banco ao modo normal de operação.",
                COLORS["accent2"],
            ),
        ]:
            frame = QFrame()
            frame.setStyleSheet(f"""
                QFrame {{
                    background: {COLORS['surface']};
                    border: 1.5px solid {cor};
                    border-radius: 6px;
                }}
            """)
            f_lay = QVBoxLayout(frame)
            f_lay.setContentsMargins(10, 6, 10, 6)
            f_lay.setSpacing(2)
            lbl_t = QLabel(titulo)
            lbl_t.setFont(QFont(FONT_SANS, 10, QFont.Weight.Bold))
            lbl_t.setStyleSheet(f"color: {cor}; background: transparent;")
            lbl_d = QLabel(desc)
            lbl_d.setFont(QFont(FONT_MONO, 8))
            lbl_d.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
            lbl_d.setWordWrap(True)
            f_lay.addWidget(lbl_t)
            f_lay.addWidget(lbl_d)
            lay.addWidget(frame)

        lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        footer   = QWidget()
        foot_lay = QVBoxLayout(footer)
        foot_lay.setContentsMargins(0, 5, 0, 0)
        foot_lay.setSpacing(4)

        self._btn_shutdown = make_danger_btn("⏻  SHUTDOWN", 120)
        self._btn_online   = make_primary_btn("▶  ONLINE",  120)
        self._btn_shutdown.clicked.connect(lambda: self._on_executar("shutdown"))
        self._btn_online.clicked.connect(lambda: self._on_executar("online"))
        self._set_enabled(bool(self._gfix_path))

        foot_lay.addWidget(h_line())
        foot_lay.addWidget(btn_row(self._btn_shutdown, self._btn_online))
        root.addWidget(footer, 0)

    def _atualizar_badge(self, status: str):
        mapa = {
            "online":      ("● Online",      COLORS["accent2"]),
            "shutdown":    ("● Shutdown",     COLORS["danger"]),
            "single-user": ("● Single-user",  COLORS["warn"]),
            "—":           ("—",              COLORS["text_dim"]),
        }
        if status.startswith("erro:"):
            texto, cor = f"⚠ {status}", COLORS["warn"]
        else:
            texto, cor = mapa.get(status, (f"● {status}", COLORS["text_dim"]))
        self._status_badge.setText(texto)
        self._status_badge.setStyleSheet(f"color: {cor}; background: transparent;")

    def _on_verificar_status(self):
        if not self._fld_db.value:
            self._alert.set_text("Informe o caminho do banco de dados.")
            self._alert.set_kind("danger")
            return
        self._btn_status.setEnabled(False)
        self._btn_status.setText("Verificando...")
        self._atualizar_badge("—")
        self._worker_status = _StatusWorker(self._gstat_path, self._fld_db.value)
        self._worker_status.concluido.connect(self._on_status_concluido)
        self._worker_status.start()

    def _on_status_concluido(self, status: str):
        self._atualizar_badge(status)
        self._btn_status.setEnabled(bool(self._gstat_path))
        self._btn_status.setText("🔍  Verificar Status")

    def _set_enabled(self, v: bool):
        self._btn_shutdown.setEnabled(v)
        self._btn_online.setEnabled(v)

    def _on_executar(self, modo: str):
        if not self._fld_db.value:
            self._alert.set_text("Informe o caminho do banco de dados.")
            self._alert.set_kind("danger")
            return
        self._set_enabled(False)
        self._btn_status.setEnabled(False)
        op = "Shutdown" if modo == "shutdown" else "Online"
        self._alert.set_text(f"Executando {op}... aguarde.")
        self._alert.set_kind("info")
        self.executar.emit(modo)

    def reabilitar(self):
        self._set_enabled(bool(self._gfix_path))
        self._btn_status.setEnabled(bool(self._gstat_path))
        self._btn_status.setText("🔍  Verificar Status")
        self._alert.set_text("Selecione o banco e escolha a operação.")
        self._alert.set_kind("info")

    def set_erro(self, msg: str):
        self._alert.set_text(f"Erro: {msg}")
        self._alert.set_kind("danger")
        self._set_enabled(bool(self._gfix_path))
        self._btn_status.setEnabled(bool(self._gstat_path))

    @property
    def banco(self) -> str:
        return self._fld_db.value

    @property
    def gfix(self) -> str:
        return self._gfix_path or ""

    @property
    def gstat(self) -> str:
        return self._gstat_path or ""


# ---------------------------------------------------------------------------
# Step 1 — Resultado
# ---------------------------------------------------------------------------

class _StepResultado(QWidget):
    go_menu = pyqtSignal()
    nova_op = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._root_lay = QVBoxLayout(self)
        self._root_lay.setContentsMargins(0, 0, 0, 0)
        self._root_lay.setSpacing(7)

        self._alert = AlertBox("", "success")
        self._root_lay.addWidget(self._alert)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_inner = QWidget()
        self._scroll_lay   = QVBoxLayout(self._scroll_inner)
        self._scroll_lay.setContentsMargins(0, 0, 10, 0)
        self._scroll_lay.setSpacing(6)
        self._scroll_lay.addStretch()
        self._scroll.setWidget(self._scroll_inner)
        self._root_lay.addWidget(self._scroll, 1)

        self._root_lay.addWidget(h_line())

        self._btn_nova = make_primary_btn("NOVA OPERAÇÃO", 160)
        self._btn_menu = make_secondary_btn("MENU PRINCIPAL", 160)
        self._btn_nova.clicked.connect(self.nova_op.emit)
        self._btn_menu.clicked.connect(self.go_menu.emit)
        self._root_lay.addWidget(btn_row(self._btn_nova, self._btn_menu))

    def set_resultado(self, sucesso: bool, modo: str, cmd: str, saida: str):
        while self._scroll_lay.count():
            item = self._scroll_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        op = "Shutdown" if modo == "shutdown" else "Online"
        if sucesso:
            self._alert.set_text(f"✓  {op} executado com sucesso.")
            self._alert.set_kind("success")
        else:
            self._alert.set_text(f"✗  {op} falhou. Verifique a saída abaixo.")
            self._alert.set_kind("danger")

        painel = _PainelResultado(sucesso, modo, cmd, saida)
        self._scroll_lay.addWidget(painel)
        self._scroll_lay.addStretch()


# ---------------------------------------------------------------------------
# PageShutdownOnline — pagina principal
# ---------------------------------------------------------------------------

class PageShutdownOnline(QWidget):
    go_menu = pyqtSignal()

    _IDX_FORM   = 0
    _IDX_RESULT = 1

    def __init__(self, parent=None):
        super().__init__(parent)

        self._worker: QThread | None = None
        self._modo_atual: str = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 14)
        root.setSpacing(6)

        root.addWidget(PageTitle("", "Shutdown / Online"))

        self._stack = QStackedWidget()
        self._form   = _StepFormulario()
        self._result = _StepResultado()
        self._stack.addWidget(self._form)    # 0
        self._stack.addWidget(self._result)  # 1
        root.addWidget(self._stack, 1)

        self._form.executar.connect(self._on_executar)
        self._result.go_menu.connect(self.go_menu.emit)
        self._result.nova_op.connect(self._go_form)

    def reset(self):
        self._go_form()

    def _go_form(self):
        self._form.reabilitar()
        self._stack.setCurrentIndex(self._IDX_FORM)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.go_menu.emit()
        else:
            super().keyPressEvent(event)

    def _on_executar(self, modo: str):
        self._modo_atual = modo
        worker = _GfixWorker(self._form.gfix, self._form.banco, modo)
        worker.concluido.connect(self._on_concluido)
        worker.erro.connect(self._on_erro)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()
        log.info(f"[ShutdownOnline] {modo.upper()} em '{self._form.banco}'")

    def _on_concluido(self, sucesso: bool, cmd: str, saida: str):
        self._result.set_resultado(sucesso, self._modo_atual, cmd, saida)
        self._stack.setCurrentIndex(self._IDX_RESULT)
        nivel = "ok" if sucesso else "error"
        getattr(log, nivel)(
            f"[ShutdownOnline] {self._modo_atual.upper()} — "
            f"{'sucesso' if sucesso else 'falha'}: {saida[:120]}"
        )
        if sucesso and self._form.gstat:
            self._form._on_verificar_status()

    def _on_erro(self, msg: str):
        self._form.set_erro(msg)
        log.error(f"[ShutdownOnline] Erro: {msg}")

    def _limpar_worker(self, worker: QThread):
        if self._worker is worker:
            self._worker = None