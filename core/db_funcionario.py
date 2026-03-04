"""
core/db_funcionario.py — Acesso ao banco Firebird para edicao de cadastro de funcionarios.
Operacoes disponiveis:
  - buscar_funcionario(conn, fk_cadastro) -> dict | None
  - atualizar_pis(conn, fk_cadastro, novo_pis) -> None
Conexao gerenciada pelo chamador (PageEditarFuncionario) via fdb.connect().
"""
from __future__ import annotations
from typing import Any
import re

try:
    import fdb
    FDB_DISPONIVEL = True
except ImportError:
    FDB_DISPONIVEL = False

# ---------------------------------------------------------------------------
# Constantes da tabela
# ---------------------------------------------------------------------------
TABELA          = "CADASTRO_FUNCIONARIO"
COL_PK          = "ID"
COL_FK_CADASTRO = "FK_CADASTRO"
COL_PIS         = "PIS"

# Colunas exibidas no painel de confirmacao (todas que existem na tabela)
COLUNAS_EXIBIR = [
    "ID", "FK_CADASTRO", "MATRICULA", "DATA_ADMISSAO",
    "DATA_DEMISSAO", "FK_FUNCAO", "FK_DEPARTAMENTO", "PIS",
]

# ---------------------------------------------------------------------------
# Helpers de conexao
# ---------------------------------------------------------------------------
def criar_conexao(
    host: str,
    database: str,
    user: str = "sysdba",
    password: str = "sbofutura",
    charset: str = "WIN1252",
):
    """Abre e retorna uma conexao fdb. Levanta RuntimeError se fdb nao instalado."""
    if not FDB_DISPONIVEL:
        raise RuntimeError(
            "Biblioteca 'fdb' nao instalada.\n"
            "Execute: pip install fdb"
        )
    return fdb.connect(
        host=host,
        database=database,
        user=user,
        password=password,
        charset=charset,
    )

# ---------------------------------------------------------------------------
# Utilitario: normaliza PIS para o formato XXXX.XXXXX.XX/X
# ---------------------------------------------------------------------------
def _formatar_pis(pis: str) -> str:
    """Recebe PIS em qualquer formato e retorna no padrao XXXX.XXXXX.XX/X.

    Formato: 4 digitos . 5 digitos . 2 digitos / 1 digito = 12 digitos no total.
    Levanta ValueError se o valor nao contiver exatamente 12 digitos.
    """
    digits = re.sub(r"\D", "", pis)
    if len(digits) != 12:
        raise ValueError(
            f"PIS inválido: esperado 12 dígitos, encontrado {len(digits)} em '{pis}'."
        )
    return f"{digits[:4]}.{digits[4:9]}.{digits[9:11]}/{digits[11]}"

# ---------------------------------------------------------------------------
# Operacoes
# ---------------------------------------------------------------------------
def buscar_funcionario(conn, fk_cadastro: int | str) -> dict[str, Any] | None:
    """Busca funcionario por FK_CADASTRO. Retorna dict com colunas ou None se nao encontrado."""
    sql = f"""
        SELECT {', '.join(COLUNAS_EXIBIR)}
        FROM {TABELA}
        WHERE {COL_FK_CADASTRO} = ?
    """
    cur = conn.cursor()
    try:
        cur.execute(sql, (int(fk_cadastro),))
        row = cur.fetchone()
        if row is None:
            return None
        return dict(zip(COLUNAS_EXIBIR, row))
    finally:
        cur.close()


def atualizar_pis(conn, fk_cadastro: int | str, novo_pis: str) -> None:
    """Atualiza o campo PIS do funcionario com FK_CADASTRO informado e faz commit.
    Grava o PIS no formato XXXX.XXXXX.XX/X.
    Verifica a gravacao com SELECT apos o UPDATE para garantir que foi persistido.
    """
    pis_formatado = _formatar_pis(novo_pis)

    cur = conn.cursor()
    try:
        # 1. Executa o UPDATE
        cur.execute(
            f"UPDATE {TABELA} SET {COL_PIS} = ? WHERE {COL_FK_CADASTRO} = ?",
            (pis_formatado, int(fk_cadastro)),
        )
        conn.commit()

        # 2. Verifica se foi gravado
        cur.execute(
            f"SELECT {COL_PIS} FROM {TABELA} WHERE {COL_FK_CADASTRO} = ?",
            (int(fk_cadastro),),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(
                f"FK_CADASTRO={fk_cadastro} não encontrado em {TABELA} após UPDATE."
            )
        pis_gravado = str(row[0] or "").strip()
        if pis_gravado != pis_formatado:
            raise RuntimeError(
                f"Falha na gravação: valor no banco '{pis_gravado}' "
                f"difere do enviado '{pis_formatado}'."
            )
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        cur.close()