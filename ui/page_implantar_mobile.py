"""
ui/page_implantar_mobile.py — Pagina de implantacao do Mobile/Tablet.

Fluxo da pagina:
  Step 0 — Selecionar banco + botao Implantar Mobile
  Step 1 — Resultado (sucesso / erros por script)

Integracao com main.py:
  1. Importe PageImplantarMobile
  2. Adicione ao QStackedWidget
  3. Conecte go_menu ao _go_menu da MainWindow
  4. Adicione NavItem na sidebar
"""

from __future__ import annotations

import os
from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QApplication,
    QFrame, QFileDialog, QLineEdit,
)

from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets import (
    PageTitle, SectionHeader, AlertBox, LogConsole, make_primary_btn,
    make_secondary_btn, make_folder_btn, btn_row, spacer, label, h_line,
    BusyOverlay,
)
from core.logger import log
from core.db_mobile import (
    criar_conexao, executar_implantacao, executar_remocao,
    FDB_DISPONIVEL, SCRIPTS,
)

_DEFAULT_HOST     = "localhost"
_DEFAULT_DATABASE = ""
_DEFAULT_USER     = "sysdba"
_DEFAULT_PASSWORD = "sbofutura"


# ---------------------------------------------------------------------------
# Helpers de botao
# ---------------------------------------------------------------------------



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
        self._btn.setToolTip("Selecionar arquivo .fdb")
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
            self,
            "Selecionar banco de dados Firebird",
            "C:\\",
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
# Worker de teste de conexao
# ---------------------------------------------------------------------------

class _TestarConexaoWorker(QThread):
    sucesso = pyqtSignal(str)
    erro    = pyqtSignal(str)

    def __init__(self, host, database, user, password):
        super().__init__()
        self._host     = host
        self._database = database
        self._user     = user
        self._password = password

    def run(self):
        try:
            conn = criar_conexao(self._host, self._database, self._user, self._password)
            try:
                cur = conn.cursor()
                cur.execute("SELECT RDB$RELATION_NAME FROM RDB$RELATIONS WHERE RDB$SYSTEM_FLAG = 0 ROWS 1")
                cur.close()
                self.sucesso.emit("Conexão estabelecida com sucesso!")
            finally:
                conn.close()
        except Exception as e:
            self.erro.emit(str(e))


# ---------------------------------------------------------------------------
# Worker de implantacao
# ---------------------------------------------------------------------------

class _ImplantarWorker(QThread):
    concluido = pyqtSignal(list)   # lista de resultados por script
    erro      = pyqtSignal(str)

    def __init__(self, host, database, user, password):
        super().__init__()
        self._host     = host
        self._database = database
        self._user     = user
        self._password = password

    def run(self):
        try:
            resultados = executar_implantacao(
                self._host, self._database,
                self._user, self._password,
            )
            self.concluido.emit(resultados)
        except Exception as e:
            self.erro.emit(str(e))


# ---------------------------------------------------------------------------
# Worker de remocao
# ---------------------------------------------------------------------------

class _RemoverWorker(QThread):
    concluido = pyqtSignal(dict)
    erro      = pyqtSignal(str)

    def __init__(self, host, database, user, password):
        super().__init__()
        self._host     = host
        self._database = database
        self._user     = user
        self._password = password

    def run(self):
        try:
            resultado = executar_remocao(
                self._host, self._database,
                self._user, self._password,
            )
            self.concluido.emit(resultado)
        except Exception as e:
            self.erro.emit(str(e))


# ---------------------------------------------------------------------------
# Painel de resultado por script
# ---------------------------------------------------------------------------

class _PainelResultadoScript(QFrame):
    """Exibe o resultado de um script: nome, ok/total, lista de erros."""

    def __init__(self, resultado: dict[str, Any], parent=None):
        super().__init__(parent)
        self.setObjectName("ScriptFrame")

        nome   = resultado["nome"]
        total  = resultado["total"]
        ok     = resultado["ok"]
        erros  = resultado["erros"]
        falhas = len(erros)
        tudo_ok = falhas == 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(4)

        # Cabecalho
        header_row = QHBoxLayout()
        icone = QLabel("✓" if tudo_ok else "✗")
        icone.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        icone.setStyleSheet(
            f"color: {COLORS['accent2'] if tudo_ok else COLORS['danger']}; background: transparent;"
        )
        lbl_nome = QLabel(nome)
        lbl_nome.setFont(QFont(FONT_SANS, 10, QFont.Weight.Bold))
        lbl_nome.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")

        lbl_contagem = QLabel(f"{ok}/{total} statements OK")
        lbl_contagem.setFont(QFont(FONT_MONO, 9))
        cor_contagem = COLORS["accent2"] if tudo_ok else COLORS["warn"]
        lbl_contagem.setStyleSheet(f"color: {cor_contagem}; background: transparent;")

        header_row.addWidget(icone)
        header_row.addWidget(lbl_nome, 1)
        header_row.addWidget(lbl_contagem)
        lay.addLayout(header_row)

        # Lista de erros (se houver)
        if erros:
            for resumo, msg in erros:
                err_frame = QFrame()
                err_frame.setObjectName("ErrFrame")
                err_lay = QVBoxLayout(err_frame)
                err_lay.setContentsMargins(8, 4, 8, 4)
                err_lay.setSpacing(2)

                lbl_stmt = QLabel(f"↳ {resumo}")
                lbl_stmt.setFont(QFont(FONT_MONO, 8))
                lbl_stmt.setWordWrap(True)
                lbl_stmt.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")

                lbl_msg = QLabel(msg)
                lbl_msg.setFont(QFont(FONT_MONO, 8))
                lbl_msg.setWordWrap(True)
                lbl_msg.setStyleSheet(f"color: {COLORS['danger']}; background: transparent;")
                lbl_msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

                err_lay.addWidget(lbl_stmt)
                err_lay.addWidget(lbl_msg)
                lay.addWidget(err_frame)

                err_frame.setStyleSheet(f"""
                    QFrame#ErrFrame {{
                        background: {COLORS['surface']};
                        border: 1px solid {COLORS['danger']};
                        border-radius: 4px;
                    }}
                """)

        # Estilo do frame principal
        border_color = COLORS["accent2"] if tudo_ok else COLORS["warn"]
        self.setStyleSheet(f"""
            QFrame#ScriptFrame {{
                background: {COLORS['surface']};
                border: 1.5px solid {border_color};
                border-radius: 6px;
            }}
        """)


# ---------------------------------------------------------------------------
# Step 0 — Formulario
# ---------------------------------------------------------------------------

class _StepFormulario(QWidget):
    implantar = pyqtSignal()
    remover   = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

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

        if not FDB_DISPONIVEL:
            self._alert = AlertBox(
                "Biblioteca 'fdb' não encontrada. Execute: pip install fdb", "danger"
            )
        else:
            self._alert = AlertBox(
                "Selecione o banco de dados e clique em Implantar Mobile para executar os 3 scripts.", "info"
            )
        lay.addWidget(self._alert)

        lay.addWidget(SectionHeader("Conexão com o Banco"))

        # Campo .fdb com explorer + Botao de testar conexao na mesma linha
        db_row = QHBoxLayout()
        db_row.setSpacing(6)

        self._fld_db = _PathFieldDB()
        self._fld_db.value = _DEFAULT_DATABASE
        db_row.addWidget(self._fld_db, 1)

        # Botao testar conexao nivelado
        btn_testar_wrap = QWidget()
        btn_testar_wrap.setStyleSheet("background: transparent;")
        btn_testar_wrap_lay = QVBoxLayout(btn_testar_wrap)
        btn_testar_wrap_lay.setContentsMargins(0, 0, 0, 0)
        btn_testar_wrap_lay.setSpacing(3)
        btn_testar_wrap_lay.addWidget(QLabel("")) # Spacer para nivelar
        self._btn_testar = make_secondary_btn("TESTAR", 80)
        self._btn_testar.clicked.connect(self._on_testar)
        self._btn_testar.setEnabled(FDB_DISPONIVEL)
        btn_testar_wrap_lay.addWidget(self._btn_testar)

        db_row.addWidget(btn_testar_wrap)
        lay.addLayout(db_row)

        lay.addWidget(spacer(h=4))

        # Resumo dos scripts que serao rodados
        lay.addWidget(SectionHeader("Scripts que serão executados"))
        for i, (nome_script, stmts) in enumerate(SCRIPTS, 1):
            linha = QLabel(f"  {i}.  {nome_script}  ({len(stmts)} statements)")
            linha.setFont(QFont(FONT_SANS, 9))
            linha.setStyleSheet(f"color: {COLORS['text_dim']};")
            lay.addWidget(linha)

        lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # Footer
        footer   = QWidget()
        foot_lay = QVBoxLayout(footer)
        foot_lay.setContentsMargins(0, 5, 0, 0)
        foot_lay.setSpacing(4)

        self._btn_implantar = make_primary_btn("IMPLANTAR MOBILE", 180)
        self._btn_implantar.clicked.connect(self._on_implantar)
        self._btn_implantar.setEnabled(FDB_DISPONIVEL)

        self._btn_remover = make_secondary_btn("REMOVER CHANGE_TABLET", 200)
        self._btn_remover.clicked.connect(self._on_remover)
        self._btn_remover.setEnabled(True)

        foot_lay.addWidget(h_line())
        foot_lay.addWidget(btn_row(self._btn_implantar, self._btn_remover))
        root.addWidget(footer, 0)

    # --- Testar conexao ---

    def _on_testar(self):
        self._btn_testar.setEnabled(False)
        self._btn_testar.setText("Testando...")
        self._alert.set_text("Testando conexão com o banco...")
        self._alert.set_kind("info")

        self._worker_teste = _TestarConexaoWorker(
            _DEFAULT_HOST, self._fld_db.value,
            _DEFAULT_USER, _DEFAULT_PASSWORD,
        )
        self._worker_teste.sucesso.connect(self._on_teste_ok)
        self._worker_teste.erro.connect(self._on_teste_erro)
        self._worker_teste.finished.connect(
            lambda: self._btn_testar.setText("TESTAR")
        )
        self._worker_teste.start()

    def _on_teste_ok(self, msg: str):
        self._alert.set_text(f"✓ {msg}")
        self._alert.set_kind("success")
        self._btn_testar.setEnabled(True)

    def _on_teste_erro(self, msg: str):
        self._alert.set_text(f"Falha na conexão: {msg}")
        self._alert.set_kind("danger")
        self._btn_testar.setEnabled(True)
        self._btn_testar.setText("TESTAR CONEXÃO")

    # --- Implantar ---

    def _on_implantar(self):
        if not self._fld_db.value:
            self._alert.set_text("Informe o caminho do banco de dados.")
            self._alert.set_kind("danger")
            return
        self._btn_implantar.setEnabled(False)
        self._btn_testar.setEnabled(False)
        self._alert.set_text("Parando Firebird e executando scripts... aguarde.")
        self._alert.set_kind("info")
        self.implantar.emit()

    def _on_remover(self):
        if not self._fld_db.value:
            self._alert.set_text("Informe o caminho do banco de dados.")
            self._alert.set_kind("danger")
            return
        # Verifica se esta rodando como Administrador
        try:
            import ctypes
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            is_admin = False

        if not is_admin:
            # Relanca o executavel com elevacao UAC
            import sys, os
            try:
                exe = sys.executable
                args = " ".join(f'"{a}"' for a in sys.argv)
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", exe, args, None, 1
                )
            except Exception as e:
                self._alert.set_text(f"Erro ao solicitar elevação: {e}")
                self._alert.set_kind("danger")
            return

        self._btn_remover.setEnabled(False)
        self._btn_implantar.setEnabled(False)
        self._btn_testar.setEnabled(False)
        self._alert.set_text("Parando Firebird e removendo CHANGE_TABLET... aguarde.")
        self._alert.set_kind("info")
        self.remover.emit()

    def reabilitar(self):
        self._btn_implantar.setEnabled(FDB_DISPONIVEL)
        self._btn_remover.setEnabled(True)
        self._btn_testar.setEnabled(FDB_DISPONIVEL)
        self._alert.set_text(
            "Selecione o banco de dados e clique em Implantar Mobile para executar os 3 scripts."
        )
        self._alert.set_kind("info")

    def set_erro(self, msg: str):
        self._alert.set_text(f"Erro ao conectar: {msg}")
        self._alert.set_kind("danger")
        self._btn_implantar.setEnabled(FDB_DISPONIVEL)
        self._btn_remover.setEnabled(True)
        self._btn_testar.setEnabled(FDB_DISPONIVEL)

    @property
    def database(self) -> str:
        return self._fld_db.value


# ---------------------------------------------------------------------------
# Step 1 — Resultado
# ---------------------------------------------------------------------------

class _StepResultado(QWidget):
    go_menu     = pyqtSignal()
    nova_implantacao = pyqtSignal()

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

        self._btn_nova = make_primary_btn("NOVA IMPLANTAÇÃO", 180)
        self._btn_menu = make_secondary_btn("MENU PRINCIPAL", 160)
        self._btn_nova.clicked.connect(self.nova_implantacao.emit)
        self._btn_menu.clicked.connect(self.go_menu.emit)

        self._root_lay.addWidget(btn_row(self._btn_nova, self._btn_menu))

    def set_resultado(self, resultados: list[dict[str, Any]]):
        # Limpa paineis anteriores
        while self._scroll_lay.count():
            item = self._scroll_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total_erros = sum(len(r["erros"]) for r in resultados)
        total_ok    = sum(r["ok"] for r in resultados)
        total_stmts = sum(r["total"] for r in resultados)

        if total_erros == 0:
            self._alert.set_text(
                f"Implantação concluída com sucesso! {total_ok}/{total_stmts} statements executados."
            )
            self._alert.set_kind("success")
        else:
            self._alert.set_text(
                f"Implantação concluída com {total_erros} erro(s). "
                f"{total_ok}/{total_stmts} statements OK."
            )
            self._alert.set_kind("warn")

        for resultado in resultados:
            painel = _PainelResultadoScript(resultado)
            self._scroll_lay.addWidget(painel)

        self._scroll_lay.addStretch()

        log.info(
            f"[ImplantarMobile] Resultado: {total_ok}/{total_stmts} OK, "
            f"{total_erros} erros."
        )


# ---------------------------------------------------------------------------
# PageImplantarMobile — pagina principal
# ---------------------------------------------------------------------------

from PyQt6.QtWidgets import QStackedWidget


class PageImplantarMobile(QWidget):
    go_menu = pyqtSignal()

    _IDX_FORM   = 0
    _IDX_RESULT = 1

    def __init__(self, parent=None):
        super().__init__(parent)

        self._worker: QThread | None = None
        self._database: str = _DEFAULT_DATABASE

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 14)
        root.setSpacing(6)

        root.addWidget(PageTitle("", "Implantar Mobile"))

        self._stack = QStackedWidget()

        self._form   = _StepFormulario()
        self._result = _StepResultado()

        self._stack.addWidget(self._form)    # 0
        self._stack.addWidget(self._result)  # 1

        root.addWidget(self._stack, 1)
        self._overlay = BusyOverlay(self)

        # Conexoes
        self._form.implantar.connect(self._on_implantar)
        self._form.remover.connect(self._on_remover)
        self._result.go_menu.connect(self.go_menu.emit)
        self._result.nova_implantacao.connect(self._go_form)

    # ── Navegacao ────────────────────────────────────────────────────────────

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

    # ── Implantacao ──────────────────────────────────────────────────────────

    def _on_implantar(self):
        self._database = self._form.database

        worker = _ImplantarWorker(
            _DEFAULT_HOST, self._database,
            _DEFAULT_USER, _DEFAULT_PASSWORD,
        )
        worker.concluido.connect(self._on_concluido)
        worker.erro.connect(self._on_erro)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()
        self._overlay.show_with("Implantando Mobile… aguarde.")

        log.info(f"[ImplantarMobile] Iniciando implantacao em {self._database}...")

    def _on_concluido(self, resultados: list):
        self._overlay.hide_spinner()
        self._result.set_resultado(resultados)
        self._stack.setCurrentIndex(self._IDX_RESULT)

    def _on_erro(self, msg: str):
        self._overlay.hide_spinner()
        self._form.set_erro(msg)
        log.error(f"[ImplantarMobile] Erro: {msg}")

    def _on_remover(self):
        self._database = self._form.database

        worker = _RemoverWorker(
            _DEFAULT_HOST, self._database,
            _DEFAULT_USER, _DEFAULT_PASSWORD,
        )
        worker.concluido.connect(self._on_remocao_concluida)
        worker.erro.connect(self._on_remocao_erro)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()
        self._overlay.show_with("Removendo CHANGE_TABLET… aguarde.")

        log.info(f"[ImplantarMobile] Removendo CHANGE_TABLET em {self._database}...")

    def _on_remocao_concluida(self, resultado: dict):
        self._overlay.hide_spinner()
        self._result.set_resultado([resultado])
        self._stack.setCurrentIndex(self._IDX_RESULT)
        total_erros = len(resultado["erros"])
        if total_erros == 0:
            log.ok("[ImplantarMobile] CHANGE_TABLET removida com sucesso.")
        else:
            log.warn(f"[ImplantarMobile] Remocao concluida com {total_erros} erro(s).")

    def _on_remocao_erro(self, msg: str):
        self._overlay.hide_spinner()
        self._form.set_erro(msg)
        log.error(f"[ImplantarMobile] Erro na remocao: {msg}")

    # ── Util ─────────────────────────────────────────────────────────────────

    def _limpar_worker(self, worker: QThread):
        if self._worker is worker:
            self._worker = None