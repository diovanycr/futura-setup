"""
ui/page_editar_funcionario.py — Pagina de edicao de cadastro de funcionario.

Fluxo da pagina:
  Step 0 — Configuracao da conexao + entrada de FK_CADASTRO e novo PIS
  Step 1 — Confirmacao: exibe dados do funcionario encontrado antes de salvar
  Step 2 — Resultado (sucesso ou erro)

Integracao com main.py:
  1. Importe PageEditarFuncionario
  2. Adicione ao QStackedWidget
  3. Conecte go_menu ao _go_menu da MainWindow
  4. Adicione NavItem na sidebar
"""

from __future__ import annotations

import os
import re
from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QApplication,
    QFrame, QFileDialog,
)

from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets import (
    PageTitle, SectionHeader, AlertBox, ResultBox,
    make_primary_btn, make_secondary_btn, make_folder_btn, btn_row,
    h_line, label, spacer,
    ProgressBlock, BusyOverlay,
)
from core.logger import log
from core.db_funcionario import (
    criar_conexao, buscar_funcionario, atualizar_pis,
    FDB_DISPONIVEL, COLUNAS_EXIBIR,
)

# ---------------------------------------------------------------------------
# Defaults de conexao — ajuste conforme o ambiente
# ---------------------------------------------------------------------------
_DEFAULT_HOST     = "localhost"
_DEFAULT_DATABASE = ""
_DEFAULT_USER     = "sysdba"
_DEFAULT_PASSWORD = "sbofutura"


# ---------------------------------------------------------------------------
# Helpers de botao (mesmo padrao do projeto)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Campo de formulario reutilizavel
# ---------------------------------------------------------------------------

class _FormField(QWidget):
    """Label + QLineEdit estilizado no padrao do projeto."""

    def __init__(
        self,
        label_text: str,
        placeholder: str = "",
        input_type: str = "text",   # "text" | "number" | "pis"
        parent=None,
    ):
        super().__init__(parent)
        self._input_type = input_type

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        self._lbl  = QLabel(label_text)
        self._edit = QLineEdit()
        self._edit.setPlaceholderText(placeholder)

        if input_type == "number":
            # Aceita apenas digitos
            from PyQt6.QtCore import QRegularExpression
            rx  = QRegularExpression(r"^\d+$")
            val = QRegularExpressionValidator(rx)
            self._edit.setValidator(val)

        elif input_type == "pis":
            # PIS: 11 digitos, mascara XXXX.XXXXX.XX/X
            self._edit.setMaxLength(15)  # 12 digitos + 3 separadores (2 pontos + 1 barra)
            self._edit.textChanged.connect(self._mascara_pis)

        lay.addWidget(self._lbl)
        lay.addWidget(self._edit)

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
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
            QLineEdit:disabled {{
                color: {COLORS['text_disabled']};
                background: {COLORS['panel_hover']};
            }}
        """)

    def _mascara_pis(self, text: str):
        """Aplica mascara XXXX.XXXXX.XX/X conforme digita.

        Formato com 12 digitos: XXXX.XXXXX.XX/X
          4 digitos . 5 digitos . 2 digitos / 1 digito
        """
        digits = re.sub(r"\D", "", text)[:12]
        n = len(digits)

        if n <= 4:
            masked = digits
        elif n <= 9:
            masked = digits[:4] + "." + digits[4:]
        elif n <= 11:
            masked = digits[:4] + "." + digits[4:9] + "." + digits[9:]
        else:  # n == 12
            masked = digits[:4] + "." + digits[4:9] + "." + digits[9:11] + "/" + digits[11]

        self._edit.blockSignals(True)
        self._edit.setText(masked)
        self._edit.blockSignals(False)

    @property
    def value(self) -> str:
        return self._edit.text().strip()

    @value.setter
    def value(self, v: str):
        self._edit.setText(str(v) if v is not None else "")

    def clear(self):
        self._edit.clear()

    def set_enabled(self, v: bool):
        self._edit.setEnabled(v)

    def set_focus(self):
        self._edit.setFocus()

    def pis_digits(self) -> str:
        """Retorna apenas os digitos do PIS (sem mascara). Esperado: 12 digitos."""
        return re.sub(r"\D", "", self.value)


# ---------------------------------------------------------------------------
# Worker de pesquisa de nome na tabela CADASTRO
# ---------------------------------------------------------------------------

class _PesquisarNomeWorker(QThread):
    resultado = pyqtSignal(str)   # RAZAO_SOCIAL encontrado
    erro      = pyqtSignal(str)

    def __init__(self, host, database, user, password, fk_cadastro):
        super().__init__()
        self._host        = host
        self._database    = database
        self._user        = user
        self._password    = password
        self._fk_cadastro = fk_cadastro

    def run(self):
        try:
            conn = criar_conexao(self._host, self._database, self._user, self._password)
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT RAZAO_SOCIAL, FANTASIA FROM CADASTRO WHERE ID = ?",
                    (int(self._fk_cadastro),)
                )
                row = cur.fetchone()
                cur.close()
                if row is None:
                    self.resultado.emit("")
                else:
                    razao, fantasia = row
                    nome = str(razao or fantasia or "").strip()
                    self.resultado.emit(nome)
            finally:
                conn.close()
        except Exception as e:
            self.erro.emit(str(e))


# ---------------------------------------------------------------------------
# Worker de busca por nome (LIKE) na tabela CADASTRO
# ---------------------------------------------------------------------------

class _BuscarPorNomeWorker(QThread):
    # lista de (ID, RAZAO_SOCIAL)
    resultado = pyqtSignal(list)
    erro      = pyqtSignal(str)

    def __init__(self, host, database, user, password, nome):
        super().__init__()
        self._host     = host
        self._database = database
        self._user     = user
        self._password = password
        self._nome     = nome

    def run(self):
        try:
            conn = criar_conexao(self._host, self._database, self._user, self._password)
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT FIRST 30 c.ID, c.RAZAO_SOCIAL, c.FANTASIA
                    FROM CADASTRO c
                    WHERE c.CHK_FUNCIONARIO = 'S'
                      AND (UPPER(c.RAZAO_SOCIAL) CONTAINING UPPER(?)
                           OR UPPER(c.FANTASIA)   CONTAINING UPPER(?))
                    ORDER BY c.RAZAO_SOCIAL
                    """,
                    (self._nome, self._nome),
                )
                rows = cur.fetchall()
                cur.close()
                resultado = []
                for row in rows:
                    cid, razao, fantasia = row
                    nome = str(razao or fantasia or "").strip()
                    resultado.append((int(cid), nome))
                self.resultado.emit(resultado)
            finally:
                conn.close()
        except Exception as e:
            self.erro.emit(str(e))


# ---------------------------------------------------------------------------
# Worker de busca (roda em background para nao travar a UI)
# ---------------------------------------------------------------------------

class _BuscarWorker(QThread):
    resultado = pyqtSignal(object)   # dict | None
    erro      = pyqtSignal(str)

    def __init__(self, host, database, user, password, fk_cadastro):
        super().__init__()
        self._host        = host
        self._database    = database
        self._user        = user
        self._password    = password
        self._fk_cadastro = fk_cadastro

    def run(self):
        try:
            conn = criar_conexao(self._host, self._database, self._user, self._password)
            try:
                dados = buscar_funcionario(conn, self._fk_cadastro)
                self.resultado.emit(dados)
            finally:
                conn.close()
        except Exception as e:
            self.erro.emit(str(e))


# ---------------------------------------------------------------------------
# Worker de gravacao
# ---------------------------------------------------------------------------

class _GravarWorker(QThread):
    concluido = pyqtSignal(str)   # emite o pis_digits gravado
    erro      = pyqtSignal(str)

    def __init__(self, host, database, user, password, fk_cadastro, novo_pis):
        super().__init__()
        self._host        = host
        self._database    = database
        self._user        = user
        self._password    = password
        self._fk_cadastro = fk_cadastro
        self._novo_pis    = novo_pis

    def run(self):
        import re
        pis_digits = re.sub(r"\D", "", self._novo_pis.strip())
        log.info(
            f"[GravarWorker] Conectando em {self._host} / {self._database} "
            f"| FK_CADASTRO={self._fk_cadastro} | PIS digits={pis_digits}"
        )
        try:
            conn = criar_conexao(self._host, self._database, self._user, self._password)
            try:
                atualizar_pis(conn, self._fk_cadastro, self._novo_pis)
                log.ok(f"[GravarWorker] PIS gravado com sucesso: {pis_digits}")
                self.concluido.emit(pis_digits)
            finally:
                conn.close()
        except Exception as e:
            log.error(f"[GravarWorker] Erro: {e}")
            self.erro.emit(str(e))


# ---------------------------------------------------------------------------
# Painel de dados do funcionario (exibido na confirmacao)
# ---------------------------------------------------------------------------

class _PainelFuncionario(QWidget):
    """Exibe as colunas do funcionario em formato de grade label: valor."""

    _LABELS = {
        "ID":                    "ID interno",
        "FK_CADASTRO":           "FK Cadastro",
        "MATRICULA":             "Matrícula",
        "DATA_ADMISSAO":         "Admissão",
        "DATA_DEMISSAO":         "Demissão",
        "FK_FUNCAO":             "Função (FK)",
        "FK_DEPARTAMENTO":       "Departamento (FK)",
        "PIS":                   "PIS atual",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: dict[str, QLabel] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._frame = QFrame()
        self._frame.setObjectName("FuncFrame")
        frame_lay = QVBoxLayout(self._frame)
        frame_lay.setContentsMargins(8, 6, 8, 6)
        frame_lay.setSpacing(3)

        for col in COLUNAS_EXIBIR:
            if col not in self._LABELS:
                continue
            row_w = QWidget()
            row_w.setStyleSheet("background: transparent;")
            row_lay = QHBoxLayout(row_w)
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.setSpacing(3)

            lbl_key = QLabel(self._LABELS[col] + ":")
            lbl_key.setFixedWidth(120)
            lbl_key.setFont(QFont(FONT_SANS, 9))

            lbl_val = QLabel("—")
            lbl_val.setFont(QFont(FONT_MONO, 9))
            lbl_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            row_lay.addWidget(lbl_key)
            row_lay.addWidget(lbl_val, 1)
            frame_lay.addWidget(row_w)

            self._rows[col] = lbl_val

        outer.addWidget(self._frame)
        theme_manager.theme_changed.connect(self._upd)
        self._upd()

    def _upd(self, _mode: str = ""):
        self._frame.setStyleSheet(f"""
            QFrame#FuncFrame {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
            }}
        """)
        for col, lbl_val in self._rows.items():
            lbl_key = lbl_val.parent().layout().itemAt(0).widget()
            lbl_key.setStyleSheet(
                f"color: {COLORS['text_dim']}; background: transparent;"
            )
            cor_val = COLORS["accent"] if col == "PIS" else COLORS["text"]
            lbl_val.setStyleSheet(
                f"color: {cor_val}; background: transparent;"
            )

    def carregar(self, dados: dict[str, Any], novo_pis: str = ""):
        for col, lbl in self._rows.items():
            val = dados.get(col)
            texto = str(val) if val not in (None, "") else "—"
            lbl.setText(texto)

        # Destaca o novo PIS em verde, exibindo no formato XXXX.XXXXX.XX/X
        if "PIS" in self._rows and novo_pis:
            pis_atual = dados.get('PIS') or '—'
            novo_pis_fmt = _formatar_pis(novo_pis)
            self._rows["PIS"].setText(f"{pis_atual}  →  {novo_pis_fmt}")
            self._rows["PIS"].setStyleSheet(
                f"color: {COLORS['accent2']}; background: transparent; font-weight: 700;"
            )


# ---------------------------------------------------------------------------
# Utilitario: formata PIS no padrao XXXX.XXXXX.XX/X a partir de digitos ou
# string ja mascarada
# ---------------------------------------------------------------------------

def _formatar_pis(pis: str) -> str:
    """Recebe PIS em qualquer formato e retorna no padrao XXXX.XXXXX.XX/X."""
    digits = re.sub(r"\D", "", pis)[:12]
    if len(digits) < 12:
        return pis  # devolve como esta se incompleto
    return f"{digits[:4]}.{digits[4:9]}.{digits[9:11]}/{digits[11]}"


# ---------------------------------------------------------------------------
# Campo de caminho com botao de explorer (label + edit + botao pasta)
# ---------------------------------------------------------------------------

class _PathFieldDB(QWidget):
    """Campo de caminho .fdb com botao de seleção de arquivo."""

    def __init__(self, parent=None):
        super().__init__(parent)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        self._lbl  = QLabel("Caminho do banco de dados (.fdb)")
        self._edit = QLineEdit()
        self._edit.setPlaceholderText(r"Ex: C:\Futura\Dados\DADOS.fdb")

        self._btn = make_folder_btn(self)
        self._btn.setToolTip("Selecionar arquivo .fdb")
        self._btn.clicked.connect(self._browse)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
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
    sucesso = pyqtSignal(str)   # versao/info do servidor
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
# Step 0 — Formulario de entrada
# ---------------------------------------------------------------------------

class _StepFormulario(QWidget):
    buscar          = pyqtSignal(str, str)   # fk_cadastro, novo_pis
    testar_conexao  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._worker_teste: _TestarConexaoWorker | None = None

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

        # Aviso se fdb nao instalado
        if not FDB_DISPONIVEL:
            self._alert = AlertBox(
                "Biblioteca 'fdb' não encontrada. Execute: pip install fdb", "danger"
            )
            lay.addWidget(self._alert)
        else:
            self._alert = AlertBox(
                "Informe o ID do funcionário e o novo PIS para atualizar.", "info"
            )
            lay.addWidget(self._alert)

        # --- Conexao ---
        lay.addWidget(SectionHeader("Conexão com o Banco"))

        # Campo .fdb com explorer + Botao de testar conexao na mesma linha
        db_row = QHBoxLayout()
        db_row.setSpacing(6)
        
        self._fld_db = _PathFieldDB()
        self._fld_db.value = _DEFAULT_DATABASE
        db_row.addWidget(self._fld_db, 1)

        # Botao testar conexao (nivelado com o QLineEdit usando um label vazio)
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

        # --- Localizar Funcionário ---
        lay.addWidget(SectionHeader("Localizar Funcionário"))

        # -- Busca por nome --
        self._fld_busca_nome = _FormField(
            "Buscar por nome (opcional)",
            "Digite parte do nome e pressione Enter ou clique Buscar",
        )
        self._fld_busca_nome._edit.returnPressed.connect(self._on_buscar_nome)

        btn_busca_wrap = QWidget()
        btn_busca_wrap.setStyleSheet("background: transparent;")
        btn_busca_wrap_lay = QVBoxLayout(btn_busca_wrap)
        btn_busca_wrap_lay.setContentsMargins(0, 0, 0, 0)
        btn_busca_wrap_lay.setSpacing(3)
        btn_busca_wrap_lay.addWidget(QLabel(""))
        self._btn_buscar_nome = make_secondary_btn("BUSCAR", 60)
        self._btn_buscar_nome.clicked.connect(self._on_buscar_nome)
        self._btn_buscar_nome.setEnabled(FDB_DISPONIVEL)
        btn_busca_wrap_lay.addWidget(self._btn_buscar_nome)

        nome_busca_row = QHBoxLayout()
        nome_busca_row.setSpacing(3)
        nome_busca_row.addWidget(self._fld_busca_nome, 1)
        nome_busca_row.addWidget(btn_busca_wrap)
        lay.addLayout(nome_busca_row)

        # Lista de resultados da busca por nome
        self._lista_frame = QFrame()
        self._lista_frame.setObjectName("ListaFrame")
        self._lista_frame.setVisible(False)
        lista_lay = QVBoxLayout(self._lista_frame)
        lista_lay.setContentsMargins(4, 4, 4, 4)
        lista_lay.setSpacing(2)
        self._lista_header = QLabel("Selecione o funcionário:")
        self._lista_header.setFont(QFont(FONT_SANS, 9))
        lista_lay.addWidget(self._lista_header)
        self._lista_itens_lay = QVBoxLayout()
        self._lista_itens_lay.setSpacing(2)
        lista_lay.addLayout(self._lista_itens_lay)
        lay.addWidget(self._lista_frame)
        theme_manager.theme_changed.connect(self._upd_lista_frame)
        self._upd_lista_frame()

        # FK_CADASTRO + botao pesquisar lado a lado
        id_row = QHBoxLayout()
        id_row.setSpacing(3)
        self._fld_id = _FormField(
            "FK_CADASTRO  (ID do funcionário)",
            "Ex: 42",
            input_type="number",
        )
        self._btn_pesquisar_id = make_secondary_btn("PESQUISAR ID", 100)
        self._btn_pesquisar_id.clicked.connect(self._on_pesquisar_id)
        self._btn_pesquisar_id.setEnabled(FDB_DISPONIVEL)
        # Alinha o botao verticalmente com o campo (adiciona label vazio para compensar)
        btn_id_wrap = QWidget()
        btn_id_wrap.setStyleSheet("background: transparent;")
        btn_id_wrap_lay = QVBoxLayout(btn_id_wrap)
        btn_id_wrap_lay.setContentsMargins(0, 0, 0, 0)
        btn_id_wrap_lay.setSpacing(3)
        btn_id_wrap_lay.addWidget(QLabel(""))   # espaco do label do campo
        btn_id_wrap_lay.addWidget(self._btn_pesquisar_id)

        id_row.addWidget(self._fld_id, 1)
        id_row.addWidget(btn_id_wrap)
        lay.addLayout(id_row)

        # Label que exibe o nome encontrado
        self._nome_frame = QFrame()
        self._nome_frame.setObjectName("NomeFrame")
        self._nome_frame.setVisible(False)
        nome_lay = QHBoxLayout(self._nome_frame)
        nome_lay.setContentsMargins(8, 6, 8, 6)
        nome_lay.setSpacing(3)
        self._nome_icone = QLabel("👤")
        self._nome_icone.setFont(QFont(FONT_SANS, 10))
        self._nome_label = QLabel("")
        self._nome_label.setFont(QFont(FONT_SANS, 10, QFont.Weight.Bold))
        self._nome_label.setWordWrap(True)
        nome_lay.addWidget(self._nome_icone)
        nome_lay.addWidget(self._nome_label, 1)
        lay.addWidget(self._nome_frame)
        theme_manager.theme_changed.connect(self._upd_nome_frame)
        self._upd_nome_frame()

        lay.addWidget(spacer(h=4))

        # --- Alterar Dados ---
        lay.addWidget(SectionHeader("Atualização de Cadastro"))

        self._fld_pis = _FormField(
            "Novo PIS",
            "Ex: 1234.56789.01/2",
            input_type="pis",
        )
        lay.addWidget(self._fld_pis)

        lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # --- Footer ---
        footer   = QWidget()
        foot_lay = QVBoxLayout(footer)
        foot_lay.setContentsMargins(0, 5, 0, 0)
        foot_lay.setSpacing(3)

        self._btn_alterar = make_primary_btn("ALTERAR PIS", 120)
        self._btn_alterar.clicked.connect(self._on_buscar)
        self._btn_alterar.setEnabled(FDB_DISPONIVEL)

        foot_lay.addWidget(h_line())
        foot_lay.addWidget(btn_row(self._btn_alterar))
        root.addWidget(footer, 0)

    def _upd_lista_frame(self, _mode: str = ""):
        self._lista_frame.setStyleSheet(f"""
            QFrame#ListaFrame {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
            }}
        """)
        self._lista_header.setStyleSheet(
            f"color: {COLORS['text_dim']}; background: transparent; padding: 2px 4px;"
        )

    def _upd_nome_frame(self, _mode: str = ""):
        self._nome_frame.setStyleSheet(f"""
            QFrame#NomeFrame {{
                background: {COLORS['surface']};
                border: 1.5px solid {COLORS['accent']};
                border-radius: 5px;
            }}
        """)
        self._nome_label.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        self._nome_icone.setStyleSheet("background: transparent;")

    # --- Buscar por nome ---

    def _on_buscar_nome(self):
        nome = self._fld_busca_nome.value
        if not nome:
            self._alert.set_text("Digite parte do nome para buscar.")
            self._alert.set_kind("danger")
            return
        if not self._fld_db.value:
            self._alert.set_text("Informe o caminho do banco de dados.")
            self._alert.set_kind("danger")
            return

        self._btn_buscar_nome.setEnabled(False)
        self._btn_buscar_nome.setText("...")
        self._lista_frame.setVisible(False)

        self._worker_busca_nome = _BuscarPorNomeWorker(
            _DEFAULT_HOST,
            self._fld_db.value,
            _DEFAULT_USER,
            _DEFAULT_PASSWORD,
            nome,
        )
        self._worker_busca_nome.resultado.connect(self._on_lista_nome_ok)
        self._worker_busca_nome.erro.connect(self._on_lista_nome_erro)
        self._worker_busca_nome.finished.connect(
            lambda: (
                self._btn_buscar_nome.setEnabled(FDB_DISPONIVEL),
                self._btn_buscar_nome.setText("BUSCAR"),
            )
        )
        self._worker_busca_nome.start()

    def _on_lista_nome_ok(self, resultados: list):
        # Limpa itens anteriores
        while self._lista_itens_lay.count():
            item = self._lista_itens_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not resultados:
            self._alert.set_text("Nenhum funcionário encontrado com esse nome.")
            self._alert.set_kind("warn")
            self._lista_frame.setVisible(False)
            return

        # Se encontrou apenas 1, seleciona automaticamente
        if len(resultados) == 1:
            cid, nome = resultados[0]
            self._selecionar_funcionario(cid, nome)
            return

        for cid, nome in resultados:
            btn = QPushButton(f"  {cid}  —  {nome}")
            btn.setMinimumHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(QFont(FONT_MONO, 9))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS['text']};
                    border: none;
                    border-radius: 4px;
                    text-align: left;
                    padding: 1px 6px;
                }}
                QPushButton:hover {{
                    background: {COLORS['accent_dim']};
                    color: {COLORS['accent']};
                }}
                QPushButton:pressed {{
                    background: {COLORS['panel_press']};
                }}
            """)
            # Captura cid e nome no closure
            btn.clicked.connect(lambda _, i=cid, n=nome: self._selecionar_funcionario(i, n))
            self._lista_itens_lay.addWidget(btn)

        total = len(resultados)
        sufixo = " (mostrando primeiros 30)" if total == 30 else ""
        self._lista_header.setText(f"Selecione o funcionário ({total} encontrado{'s' if total > 1 else ''}{sufixo}):")
        self._lista_frame.setVisible(True)
        self._alert.set_text(f"{total} funcionário{'s' if total > 1 else ''} encontrado{'s' if total > 1 else ''}. Clique para selecionar.")
        self._alert.set_kind("info")

    def _on_lista_nome_erro(self, msg: str):
        self._alert.set_text(f"Erro ao buscar: {msg}")
        self._alert.set_kind("danger")
        self._lista_frame.setVisible(False)

    def _selecionar_funcionario(self, cid: int, nome: str):
        """Preenche o campo FK_CADASTRO e exibe o nome ao clicar em um resultado."""
        self._fld_id.value = str(cid)
        self._nome_label.setText(nome)
        self._nome_frame.setVisible(True)
        self._lista_frame.setVisible(False)
        self._alert.set_text(f"Selecionado: {nome}  (ID {cid})")
        self._alert.set_kind("success")

    # --- Pesquisar ID ---

    def _on_pesquisar_id(self):
        fk = self._fld_id.value
        if not fk:
            self._alert.set_text("Informe o FK_CADASTRO antes de pesquisar.")
            self._alert.set_kind("danger")
            return
        if not self._fld_db.value:
            self._alert.set_text("Informe o caminho do banco de dados.")
            self._alert.set_kind("danger")
            return

        self._btn_pesquisar_id.setEnabled(False)
        self._btn_pesquisar_id.setText("Buscando...")
        self._nome_frame.setVisible(False)

        self._worker_nome = _PesquisarNomeWorker(
            _DEFAULT_HOST,
            self._fld_db.value,
            _DEFAULT_USER,
            _DEFAULT_PASSWORD,
            fk,
        )
        self._worker_nome.resultado.connect(self._on_nome_ok)
        self._worker_nome.erro.connect(self._on_nome_erro)
        self._worker_nome.finished.connect(
            lambda: (
                self._btn_pesquisar_id.setEnabled(FDB_DISPONIVEL),
                self._btn_pesquisar_id.setText("PESQUISAR ID"),
            )
        )
        self._worker_nome.start()

    def _on_nome_ok(self, nome: str):
        if nome:
            self._nome_label.setText(nome)
            self._nome_frame.setVisible(True)
            self._alert.set_text(f"Funcionário encontrado: {nome}")
            self._alert.set_kind("success")
        else:
            self._nome_frame.setVisible(False)
            self._alert.set_text(f"Nenhum cadastro encontrado para o ID informado.")
            self._alert.set_kind("danger")

    def _on_nome_erro(self, msg: str):
        self._nome_frame.setVisible(False)
        self._alert.set_text(f"Erro ao pesquisar: {msg}")
        self._alert.set_kind("danger")

    # --- Testar conexao ---

    def _on_testar(self):
        self._btn_testar.setEnabled(False)
        self._btn_testar.setText("Testando...")
        self._alert.set_text("Testando conexão com o banco...")
        self._alert.set_kind("info")

        self._worker_teste = _TestarConexaoWorker(
            _DEFAULT_HOST,
            self._fld_db.value,
            _DEFAULT_USER,
            _DEFAULT_PASSWORD,
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

    # --- Alterar PIS ---

    def _on_buscar(self):
        fk = self._fld_id.value
        pis_digits = self._fld_pis.pis_digits()

        if not self._fld_db.value:
            self._alert.set_text("Informe o caminho do banco de dados.")
            self._alert.set_kind("danger")
            return
        if not fk:
            self._alert.set_text("Informe o FK_CADASTRO do funcionário.")
            self._alert.set_kind("danger")
            return
        if len(pis_digits) != 12:
            self._alert.set_text("PIS inválido — informe 12 dígitos.")
            self._alert.set_kind("danger")
            return

        self._alert.set_text("Buscando funcionário no banco...")
        self._alert.set_kind("info")
        self._btn_alterar.setEnabled(False)
        self.buscar.emit(fk, self._fld_pis.value)

    def reabilitar(self):
        self._btn_alterar.setEnabled(FDB_DISPONIVEL)
        self._btn_testar.setEnabled(FDB_DISPONIVEL)
        self._btn_pesquisar_id.setEnabled(FDB_DISPONIVEL)
        self._btn_buscar_nome.setEnabled(FDB_DISPONIVEL)
        self._nome_frame.setVisible(False)
        self._nome_label.setText("")
        self._lista_frame.setVisible(False)
        self._fld_busca_nome.clear()

    def set_erro(self, msg: str):
        self._alert.set_text(msg)
        self._alert.set_kind("danger")
        self._btn_alterar.setEnabled(FDB_DISPONIVEL)

    @property
    def host(self) -> str:
        return _DEFAULT_HOST

    @property
    def database(self) -> str:
        return self._fld_db.value

    @property
    def fk_cadastro(self) -> str:
        return self._fld_id.value

    @property
    def novo_pis(self) -> str:
        return self._fld_pis.value

    @property
    def novo_pis_digits(self) -> str:
        return self._fld_pis.pis_digits()


# ---------------------------------------------------------------------------
# Step 1 — Confirmacao
# ---------------------------------------------------------------------------

class _StepConfirmacao(QWidget):
    confirmar = pyqtSignal()
    voltar    = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        self._alert = AlertBox("Confirme os dados antes de salvar.", "warn")
        lay.addWidget(self._alert)

        lay.addWidget(SectionHeader("Dados do Funcionário Encontrado"))

        self._painel = _PainelFuncionario()
        lay.addWidget(self._painel)

        lay.addStretch()
        lay.addWidget(h_line())

        self._btn_confirmar = make_primary_btn("CONFIRMAR E SALVAR", 160)
        self._btn_voltar    = make_secondary_btn("VOLTAR", 80)
        self._btn_confirmar.clicked.connect(self._on_confirmar)
        self._btn_voltar.clicked.connect(self.voltar.emit)

        lay.addWidget(btn_row(self._btn_voltar, self._btn_confirmar))

    def carregar(self, dados: dict, novo_pis: str):
        self._painel.carregar(dados, novo_pis)
        self._alert.set_text(
            f"Funcionário FK_CADASTRO={dados.get('FK_CADASTRO')} encontrado. "
            "Revise as informações e confirme a alteração do PIS."
        )
        self._alert.set_kind("warn")

    def _on_confirmar(self):
        self._btn_confirmar.setEnabled(False)
        self._btn_voltar.setEnabled(False)
        self._alert.set_text("Salvando alteração no banco...")
        self._alert.set_kind("info")
        self.confirmar.emit()

    def reabilitar(self):
        self._btn_confirmar.setEnabled(True)
        self._btn_voltar.setEnabled(True)


# ---------------------------------------------------------------------------
# Step 2 — Resultado
# ---------------------------------------------------------------------------

class _StepResultado(QWidget):
    go_menu   = pyqtSignal()
    nova_edicao = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        self._alert      = AlertBox("", "success")
        self._result_box = ResultBox("Resultado", [], "success")

        lay.addWidget(self._alert)
        lay.addWidget(self._result_box)
        lay.addStretch()
        lay.addWidget(h_line())

        self._btn_nova  = make_primary_btn("NOVA EDIÇÃO", 180)
        self._btn_menu  = make_secondary_btn("MENU PRINCIPAL", 180)
        self._btn_nova.clicked.connect(self.nova_edicao.emit)
        self._btn_menu.clicked.connect(self.go_menu.emit)

        lay.addWidget(btn_row(self._btn_nova, self._btn_menu))

    def set_resultado(self, sucesso: bool, fk_cadastro: str, novo_pis: str, erro: str = ""):
        lay = self.layout()
        lay.removeWidget(self._result_box)
        self._result_box.deleteLater()

        if sucesso:
            self._alert.set_text("PIS atualizado com sucesso!")
            self._alert.set_kind("success")
            self._result_box = ResultBox(
                "Alteração realizada",
                [
                    ("FK_CADASTRO", fk_cadastro),
                    # Exibe o PIS gravado ja formatado no padrao XXXX.XXXXX.XX/X
                    ("Novo PIS",    _formatar_pis(novo_pis)),
                ],
                "success",
            )
        else:
            self._alert.set_text("Erro ao salvar a alteração.")
            self._alert.set_kind("danger")
            self._result_box = ResultBox(
                "Falha na operação",
                [("Detalhe", erro)],
                "error",
            )

        lay.insertWidget(1, self._result_box)


# ---------------------------------------------------------------------------
# PageEditarFuncionario — pagina principal
# ---------------------------------------------------------------------------

from PyQt6.QtWidgets import QStackedWidget


class PageEditarFuncionario(QWidget):
    go_menu = pyqtSignal()

    _IDX_FORM    = 0
    _IDX_CONFIRM = 1
    _IDX_RESULT  = 2

    def __init__(self, parent=None):
        super().__init__(parent)

        # worker exposto para o busy indicator da MainWindow
        self._worker: QThread | None = None

        # Estado temporario entre steps
        self._dados_funcionario: dict  = {}
        self._fk_cadastro: str         = ""
        self._novo_pis: str            = ""
        self._host: str                = _DEFAULT_HOST
        self._database: str            = _DEFAULT_DATABASE

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 14)
        root.setSpacing(3)

        root.addWidget(PageTitle("", "Editar Cadastro de Funcionário"))

        self._stack = QStackedWidget()

        self._form    = _StepFormulario()
        self._confirm = _StepConfirmacao()
        self._result  = _StepResultado()

        self._stack.addWidget(self._form)     # 0
        self._stack.addWidget(self._confirm)  # 1
        self._stack.addWidget(self._result)   # 2

        root.addWidget(self._stack, 1)
        self._overlay = BusyOverlay(self)

        # Conexoes
        self._form.buscar.connect(self._on_buscar)
        self._confirm.confirmar.connect(self._on_confirmar)
        self._confirm.voltar.connect(self._go_form)
        self._result.go_menu.connect(self.go_menu.emit)
        self._result.nova_edicao.connect(self._go_form)

    # ── Navegacao interna ────────────────────────────────────────────────────

    def reset(self):
        self._go_form()

    def _go_form(self):
        self._form.reabilitar()
        self._confirm.reabilitar()
        self._stack.setCurrentIndex(self._IDX_FORM)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self._stack.currentIndex() == self._IDX_FORM:
                self.go_menu.emit()
            elif self._stack.currentIndex() == self._IDX_CONFIRM:
                self._go_form()
        else:
            super().keyPressEvent(event)

    # ── Step 0 → Step 1: Busca ───────────────────────────────────────────────

    def _on_buscar(self, fk_cadastro: str, novo_pis: str):
        self._fk_cadastro = fk_cadastro
        self._novo_pis    = novo_pis
        self._host        = self._form.host
        self._database    = self._form.database

        worker = _BuscarWorker(
            self._host, self._database,
            _DEFAULT_USER, _DEFAULT_PASSWORD,
            fk_cadastro,
        )
        worker.resultado.connect(self._on_busca_ok)
        worker.erro.connect(self._on_busca_erro)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()
        self._overlay.show_with("Buscando funcionário…")

        log.info(f"[EditarFuncionario] Buscando FK_CADASTRO={fk_cadastro}...")

    def _on_busca_ok(self, dados):
        self._overlay.hide_spinner()
        if dados is None:
            self._form.set_erro(
                f"Funcionário com FK_CADASTRO={self._fk_cadastro} não encontrado."
            )
            log.warn(f"[EditarFuncionario] FK_CADASTRO={self._fk_cadastro} não encontrado.")
            return

        self._dados_funcionario = dados
        self._confirm.carregar(dados, self._novo_pis)
        self._stack.setCurrentIndex(self._IDX_CONFIRM)
        log.info(f"[EditarFuncionario] Funcionário encontrado: {dados}")

    def _on_busca_erro(self, msg: str):
        self._overlay.hide_spinner()
        self._form.set_erro(f"Erro ao conectar: {msg}")
        log.error(f"[EditarFuncionario] Erro na busca: {msg}")

    # ── Step 1 → Step 2: Gravacao ────────────────────────────────────────────

    def _on_confirmar(self):
        worker = _GravarWorker(
            self._host, self._database,
            _DEFAULT_USER, _DEFAULT_PASSWORD,
            self._fk_cadastro, self._novo_pis,
        )
        worker.concluido.connect(self._on_gravar_ok)
        worker.erro.connect(self._on_gravar_erro)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()
        self._overlay.show_with("Salvando alteração…")
        log.info(
            f"[EditarFuncionario] Gravando PIS para FK_CADASTRO={self._fk_cadastro}..."
        )

    def _on_gravar_ok(self, pis_gravado: str):
        self._overlay.hide_spinner()
        self._result.set_resultado(True, self._fk_cadastro, pis_gravado)
        self._stack.setCurrentIndex(self._IDX_RESULT)
        log.ok(
            f"[EditarFuncionario] PIS atualizado — "
            f"FK_CADASTRO={self._fk_cadastro}, PIS={pis_gravado}"
        )

    def _on_gravar_erro(self, msg: str):
        self._overlay.hide_spinner()
        self._confirm.reabilitar()
        self._result.set_resultado(False, self._fk_cadastro, self._novo_pis, erro=msg)
        self._stack.setCurrentIndex(self._IDX_RESULT)
        log.error(f"[EditarFuncionario] Erro ao gravar: {msg}")

    # ── Util ─────────────────────────────────────────────────────────────────

    def _limpar_worker(self, worker: QThread):
        if self._worker is worker:
            self._worker = None