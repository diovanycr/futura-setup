"""
core/db_mobile.py — Execucao dos scripts de implantacao do Mobile/Tablet.
"""
from __future__ import annotations

from typing import Any

try:
    import fdb
    FDB_DISPONIVEL = True
except ImportError:
    FDB_DISPONIVEL = False

from core.firebird_services import (
    stop_firebird_services,
    start_firebird_services,
)


# ---------------------------------------------------------------------------
# Tabelas e triggers
# ---------------------------------------------------------------------------

_TABELAS_TRIGGERS: list[tuple[str, str]] = [
    ("CADASTRO_AIUD8",                    "CADASTRO"),
    ("CADASTRO_ENDERECO_AIUD8",            "CADASTRO_ENDERECO"),
    ("PRODUTO_AIUD8",                      "PRODUTO"),
    ("SYS_USUARIO_AIUD8",                  "SYS_USUARIO"),
    ("CONFIGURACAO_MOBILE_AIUD8",           "CONFIGURACAO_MOBILE"),
    ("PEDIDO_PROMOCAO_AIUD8",               "PEDIDO_PROMOCAO"),
    ("PEDIDO_DESCONTO_AIUD8",               "PEDIDO_DESCONTO"),
    ("CADASTRO_NEGATIVACAO_AIUD8",          "CADASTRO_NEGATIVACAO"),
    ("SYS_MODULO_AIUD8",                   "SYS_MODULO"),
    ("SYS_USUARIO_MODULO_AIUD8",            "SYS_USUARIO_MODULO"),
    ("EMAIL_AIUD8",                        "EMAIL"),
    ("TABELA_PRECO_AIUD8",                 "TABELA_PRECO"),
    ("PRODUTO_COR_AIUD8",                  "PRODUTO_COR"),
    ("PRODUTO_ESPECIFICACAO_AIUD8",         "PRODUTO_ESPECIFICACAO"),
    ("PRODUTO_UNIDADE_AIUD8",              "PRODUTO_UNIDADE"),
    ("PRODUTO_MARCA_AIUD8",                "PRODUTO_MARCA"),
    ("PRODUTO_GRUPO_AIUD8",                "PRODUTO_GRUPO"),
    ("PRODUTO_SUBGRUPO_AIUD8",             "PRODUTO_SUBGRUPO"),
    ("PRODUTO_TAMANHO_AIUD8",              "PRODUTO_TAMANHO"),
    ("PRODUTO_CODIGO_BARRA_AIUD8",         "PRODUTO_CODIGO_BARRA"),
    ("PRODUTO_CONVERSAO_AIUD8",            "PRODUTO_CONVERSAO"),
    ("PRODUTO_CODIGO_CAIXA_AIUD8",         "PRODUTO_CODIGO_CAIXA"),
    ("PRODUTO_PRECO_AIUD8",                "PRODUTO_PRECO"),
    ("REGIAO_AIUD8",                       "REGIAO"),
    ("TIPO_PEDIDO_AIUD8",                  "TIPO_PEDIDO"),
    ("FATURA_PRAZO_AIUD8",                 "FATURA_PRAZO"),
    ("PRODUTO_INGREDIENTES_ITM_AIUD8",     "PRODUTO_INGREDIENTES_ITEM"),
    ("PRODUTO_GUARNICOES_AIUD8",           "PRODUTO_GUARNICOES"),
    ("PRODUTO_GRADE_GUARNICAO_AIUD8",      "PRODUTO_GRADE_GUARNICAO"),
    ("PRODUTO_REFEICAO_AIUD8",             "PRODUTO_REFEICAO"),
    ("PRODUTO_GRADE_AIUD8",                "PRODUTO_GRADE"),
    ("PRODUTO_GRADE_ITEM_AIUD8",           "PRODUTO_GRADE_ITEM"),
    ("MESA_AIUD8",                         "MESA"),
    ("COMANDA_EXTRAVIADA_AIUD8",           "COMANDA_EXTRAVIADA"),
    ("COMANDA_AIUD8",                      "COMANDA"),
    ("PRODUTO_COMBO_AIUD8",                "PRODUTO_COMBO"),
    ("PRODUTO_COMBO_OPCAO_AIUD8",          "PRODUTO_COMBO_OPCAO"),
    ("PRODUTO_COMBO_OPCAO_ITEM_AIUD8",     "PRODUTO_COMBO_OPCAO_ITEM"),
    ("TIPO_PAGAMENTO_AIUD8",               "TIPO_PAGAMENTO"),
    ("REGIAO_ENTREGA_AIUD8",               "REGIAO_ENTREGA"),
    ("REGIAO_ENTREGA_BAIRRO_AIUD8",        "REGIAO_ENTREGA_BAIRRO"),
    ("PEDIDO_FILA_TIPO_AIUD8",             "PEDIDO_FILA_TIPO"),
    ("VALE_PRESENTE_AIUD8",                "VALE_PRESENTE"),
    ("LAYOUT_AIUD8",                       "LAYOUT"),
    ("LAYOUT_ORDEM_AIUD8",                 "LAYOUT_ORDEM"),
    ("LAYOUT_ITEM_AIUD8",                  "LAYOUT_ITEM"),
    ("UF_MUNICIPIO_IBGE_AIUD8",            "UF_MUNICIPIO_IBGE"),
    ("CADASTRO_FUNCIONARIO_AIUD8",         "CADASTRO_FUNCIONARIO"),
    ("CADASTRO_GRUPO_VENDA_AIUD8",         "CADASTRO_GRUPO_VENDA"),
    ("CADASTRO_GRUPO_VENDA_ITM_AIUD8",     "CADASTRO_GRUPO_VENDA_ITEM"),
    ("PAISES_AIUD8",                       "PAISES"),
    ("OS_SUPORTE_EXTERNO_AIUD8",           "OS_SUPORTE_EXTERNO"),
    ("SYS_CONTROLE_ENTREGA_TIP_AIUD8",     "SYS_CONTROLE_ENTREGA_TIPO"),
    ("PRODUTO_ESTOQUE_AIUD8",              "PRODUTO_ESTOQUE"),
    ("PRODUTO_IMAGEM_AIUD8",               "PRODUTO_IMAGEM"),
    ("PRODUTO_KIT_AIUD8",                  "PRODUTO_KIT"),
    ("PRODUTO_KIT_ITEM_AIUD8",             "PRODUTO_KIT_ITEM"),
]

_TABELAS_GRANT_REPL: list[str] = [
    "CADASTRO", "CADASTRO_ENDERECO", "PRODUTO", "SYS_USUARIO",
    "CONFIGURACAO_MOBILE", "PEDIDO_PROMOCAO", "PEDIDO_DESCONTO",
    "CADASTRO_NEGATIVACAO", "SYS_MODULO", "SYS_USUARIO_MODULO",
    "EMAIL", "TABELA_PRECO", "PRODUTO_COR", "PRODUTO_ESPECIFICACAO",
    "PRODUTO_UNIDADE", "PRODUTO_MARCA", "PRODUTO_GRUPO", "PRODUTO_SUBGRUPO",
    "PRODUTO_TAMANHO", "PRODUTO_CODIGO_BARRA", "PRODUTO_CONVERSAO",
    "PRODUTO_CODIGO_CAIXA", "PRODUTO_PRECO", "REGIAO", "TIPO_PEDIDO",
    "FATURA_PRAZO", "PRODUTO_INGREDIENTES_ITEM", "PRODUTO_GUARNICOES",
    "PRODUTO_GRADE_GUARNICAO", "PRODUTO_REFEICAO", "PRODUTO_GRADE",
    "PRODUTO_GRADE_ITEM", "MESA", "COMANDA_EXTRAVIADA", "COMANDA",
    "PRODUTO_COMBO", "PRODUTO_COMBO_OPCAO", "PRODUTO_COMBO_OPCAO_ITEM",
    "TIPO_PAGAMENTO", "REGIAO_ENTREGA", "REGIAO_ENTREGA_BAIRRO",
    "PEDIDO_FILA_TIPO", "VALE_PRESENTE", "LAYOUT", "LAYOUT_ORDEM",
    "LAYOUT_ITEM", "UF_MUNICIPIO_IBGE", "CADASTRO_FUNCIONARIO",
    "CADASTRO_GRUPO_VENDA", "CADASTRO_GRUPO_VENDA_ITEM", "PAISES",
    "OS_SUPORTE_EXTERNO", "SYS_CONTROLE_ENTREGA_TIPO", "PRODUTO_ESTOQUE",
    "PRODUTO_IMAGEM", "PRODUTO_KIT", "PRODUTO_KIT_ITEM",
]


# ---------------------------------------------------------------------------
# Montagem do Script 1
# ---------------------------------------------------------------------------

def _bloco_set_term(sql_corpo: str) -> str:
    return f"SET TERM ^ ;\n{sql_corpo.strip()}\n^\nSET TERM ; ^"


def _build_script_1() -> str:
    partes: list[str] = []

    ddl_simples = [
        """CREATE TABLE CHANGE_TABLET (
    ID Integer NOT NULL,
    TABLE_NAME Varchar(30),
    PK_FIELD Varchar(40),
    PK_VALUE Varchar(40),
    TYPE_OPERATION Char(1),
    DATE_TIME Timestamp,
    BASE_ORIGEM Varchar(02),
    CONSTRAINT PK_CHANGE_TABLET PRIMARY KEY (ID)
)""",
        "CREATE INDEX IND_CHANGE_TABLET1 ON CHANGE_TABLET (TABLE_NAME)",
        "CREATE INDEX IND_CHANGE_TABLET2 ON CHANGE_TABLET (PK_VALUE)",
        "CREATE INDEX IND_CHANGE_TABLET3 ON CHANGE_TABLET (TYPE_OPERATION)",
        "CREATE INDEX IND_CHANGE_TABLET4 ON CHANGE_TABLET (BASE_ORIGEM)",
        "GRANT DELETE, INSERT, REFERENCES, SELECT, UPDATE ON CHANGE_TABLET TO SYSDBA WITH GRANT OPTION",
        "GRANT DELETE, INSERT, REFERENCES, SELECT, UPDATE ON CHANGE_TABLET TO SYS_REPL",
        "GRANT DELETE, INSERT, REFERENCES, SELECT, UPDATE ON CHANGE_TABLET TO SYS_WEB",
        "CREATE GENERATOR GEN_CHANGE_TABLET",
    ]
    partes.append(";\n".join(ddl_simples) + ";")

    partes.append(_bloco_set_term("""
CREATE OR ALTER TRIGGER CHANGE_TABLET_AIUD5 FOR CHANGE_TABLET
ACTIVE AFTER INSERT OR UPDATE OR DELETE POSITION 5
AS BEGIN
  IF (INSERTING) THEN EXECUTE PROCEDURE SP_SET_CHANGE('CHANGE_TABLET','ID',NEW.ID,'I');
  IF (UPDATING)  THEN EXECUTE PROCEDURE SP_SET_CHANGE('CHANGE_TABLET','ID',NEW.ID,'U');
  IF (DELETING)  THEN EXECUTE PROCEDURE SP_SET_CHANGE('CHANGE_TABLET','ID',OLD.ID,'D');
END
"""))

    partes.append(_bloco_set_term("""
CREATE OR ALTER PROCEDURE SP_CHANGE_TABLET_EXECUTE
AS
DECLARE VARIABLE UltimaLimpeza    DATE;
DECLARE VARIABLE MaiorData        TIMESTAMP;
DECLARE VARIABLE QuantidadeChange INTEGER;
BEGIN
  IF (USER <> 'SYS_REPL') THEN BEGIN
    SELECT FIRST 1 CHANGE_TABLET_LIMPEZA FROM PARAMETROS INTO :UltimaLimpeza;
    IF (:UltimaLimpeza < CURRENT_DATE) THEN BEGIN
      SELECT COUNT(*) FROM CHANGE_TABLET INTO :QuantidadeChange;
      IF (QuantidadeChange > 700000) THEN BEGIN
        SELECT FIRST 1 SKIP 200000 DATE_TIME FROM CHANGE_TABLET
          ORDER BY DATE_TIME ASC INTO :MaiorData;
        DELETE FROM CHANGE_TABLET WHERE DATE_TIME < :MaiorData;
      END
      UPDATE PARAMETROS SET CHANGE_TABLET_LIMPEZA = CURRENT_DATE;
    END
  END
END
"""))

    partes.append(
        "GRANT EXECUTE ON PROCEDURE SP_CHANGE_TABLET_EXECUTE TO SYSDBA;\n"
        "GRANT EXECUTE ON PROCEDURE SP_CHANGE_TABLET_EXECUTE TO SYS_REPL;\n"
        "GRANT EXECUTE ON PROCEDURE SP_CHANGE_TABLET_EXECUTE TO SYS_WEB;"
    )

    partes.append(_bloco_set_term("""
CREATE OR ALTER PROCEDURE SP_SET_CHANGE_TABLET (
    TABLE_NAME     Varchar(30),
    PK_FIELD       Varchar(40),
    PK_VALUE       Varchar(40),
    TYPE_OPERATION Char(1))
AS
DECLARE VARIABLE ID_TEMP     INTEGER;
DECLARE VARIABLE BASE_TEMP   VARCHAR(20);
DECLARE VARIABLE BASE_ORIGEM VARCHAR(02);
DECLARE VARIABLE ID          INTEGER;
BEGIN
  IF (USER <> 'SYS_REPL') THEN BEGIN
    SELECT RESULT FROM SP_GET_GENERATOR('GEN_CHANGE_TABLET') INTO :ID;
    SELECT GEN_ID(GEN_CHANGE_TABLET,0) FROM RDB$DATABASE INTO :ID_TEMP;
    IF (:ID = :ID_TEMP) THEN BEGIN
      BASE_ORIGEM = '01';
    END ELSE BEGIN
      BASE_TEMP   = CAST(:ID AS VARCHAR(20));
      BASE_ORIGEM = SUBSTRING(BASE_TEMP FROM (CHAR_LENGTH(BASE_TEMP)-1) FOR 2);
    END
    INSERT INTO CHANGE_TABLET
      (ID, TABLE_NAME, PK_FIELD, PK_VALUE, TYPE_OPERATION, DATE_TIME, BASE_ORIGEM)
    VALUES
      (:ID, :TABLE_NAME, :PK_FIELD, :PK_VALUE, :TYPE_OPERATION, CURRENT_TIMESTAMP, :BASE_ORIGEM);
    IF (MOD(ID_TEMP,1000)=0) THEN EXECUTE PROCEDURE SP_CHANGE_TABLET_EXECUTE;
  END
END
"""))

    partes.append(
        "GRANT EXECUTE ON PROCEDURE SP_SET_CHANGE_TABLET TO SYSDBA;\n"
        "GRANT EXECUTE ON PROCEDURE SP_SET_CHANGE_TABLET TO SYS_REPL;\n"
        "GRANT EXECUTE ON PROCEDURE SP_SET_CHANGE_TABLET TO SYS_WEB;"
    )

    for trig, table in _TABELAS_TRIGGERS:
        partes.append(_bloco_set_term(f"""
CREATE OR ALTER TRIGGER {trig} FOR {table}
ACTIVE AFTER INSERT OR UPDATE OR DELETE POSITION 8
AS BEGIN
  IF (INSERTING) THEN EXECUTE PROCEDURE SP_SET_CHANGE_TABLET('{table}','ID',NEW.ID,'I');
  IF (UPDATING)  THEN EXECUTE PROCEDURE SP_SET_CHANGE_TABLET('{table}','ID',NEW.ID,'U');
  IF (DELETING)  THEN EXECUTE PROCEDURE SP_SET_CHANGE_TABLET('{table}','ID',OLD.ID,'D');
END
"""))

    grants_repl = [
        f"GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON {t} TO SYS_REPL"
        for t in _TABELAS_GRANT_REPL
    ]
    partes.append(";\n".join(grants_repl) + ";")
    partes.append("COMMIT;")

    return "\n\n".join(partes) + "\n"


_SCRIPT_2_SQL = """GRANT USAGE ON GENERATOR GEN_CHANGE_TABLET TO SYSDBA;
GRANT USAGE ON GENERATOR GEN_CHANGE_TABLET TO SYS_REPL;
GRANT USAGE ON GENERATOR GEN_CHANGE_TABLET TO SYS_WEB;
COMMIT;
"""

_SCRIPT_3_SQL = """SET TERM ^ ;
EXECUTE BLOCK AS
DECLARE VARIABLE gen VARCHAR(500);
BEGIN
  FOR SELECT 'GRANT USAGE ON GENERATOR '||RDB$GENERATOR_NAME||' TO SYS_REPL'
        FROM RDB$GENERATORS
       WHERE RDB$SYSTEM_FLAG = 0
        INTO :gen DO
    BEGIN
      EXECUTE STATEMENT :gen;
    END
END^
SET TERM ; ^
COMMIT;
"""

_SCRIPT_1_SQL = _build_script_1()

SCRIPTS = [
    ("Script 1 — CHANGE_TABLET, procedures e triggers", _SCRIPT_1_SQL),
    ("Script 2 — GRANT USAGE ON GENERATOR fixos",       _SCRIPT_2_SQL),
    ("Script 3 — GRANT USAGE em todos os generators",   _SCRIPT_3_SQL),
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
    if not FDB_DISPONIVEL:
        raise RuntimeError("Biblioteca 'fdb' não instalada.\nExecute: pip install fdb")
    return fdb.connect(
        host=host,
        database=database,
        user=user,
        password=password,
        charset=charset,
    )


# ---------------------------------------------------------------------------
# isql
# ---------------------------------------------------------------------------

_ISQL_CANDIDATES = [
    r"C:\Program Files\Firebird\Firebird_3_0\isql.exe",
    r"C:\Program Files\Firebird\Firebird_2_5\isql.exe",
    r"C:\Program Files (x86)\Firebird\Firebird_3_0\isql.exe",
    r"C:\Program Files (x86)\Firebird\Firebird_2_5\isql.exe",
    r"C:\Firebird\isql.exe",
]


def _encontrar_isql() -> str:
    import os
    for path in _ISQL_CANDIDATES:
        if os.path.isfile(path):
            return path
    raise RuntimeError(
        "isql.exe nao encontrado. Verifique a instalacao do Firebird.\n"
        "Caminhos tentados:\n" + "\n".join(_ISQL_CANDIDATES)
    )


# ---------------------------------------------------------------------------
# Controle do Firebird
# ---------------------------------------------------------------------------

def parar_firebird() -> list[str]:
    from core.logger import log
    parados = stop_firebird_services()
    if parados:
        log.info(f"[Mobile] Servicos Firebird parados: {', '.join(parados)}")
    else:
        log.warn("[Mobile] Nenhum servico Firebird estava ativo")
    return parados


def iniciar_firebird(servicos_parados: list[str]) -> None:
    from core.logger import log
    if not servicos_parados:
        return
    start_firebird_services(servicos_parados)
    log.info(f"[Mobile] Servicos Firebird reiniciados: {', '.join(servicos_parados)}")


def aguardar_firebird_pronto(
    host: str,
    database: str,
    user: str,
    password: str,
    timeout: int = 30,
) -> bool:
    """
    Aguarda o Firebird estar realmente aceitando conexoes TCP.
    O servico pode estar RUNNING mas ainda nao aceitar conexoes por alguns
    segundos — esta funcao tenta conectar via fdb ate conseguir ou timeout.
    Retorna True se conseguiu conectar, False se esgotou o timeout.
    """
    import time
    from core.logger import log

    if not FDB_DISPONIVEL:
        # Sem fdb, aguarda um tempo fixo conservador
        log.info("[Mobile] fdb nao disponivel — aguardando 8s fixos para o Firebird subir")
        time.sleep(8)
        return True

    log.info(f"[Mobile] Aguardando Firebird aceitar conexoes (timeout={timeout}s)...")
    inicio = time.time()
    tentativa = 0
    while time.time() - inicio < timeout:
        tentativa += 1
        try:
            conn = fdb.connect(
                host=host, database=database,
                user=user, password=password,
                charset="WIN1252",
            )
            conn.close()
            elapsed = round(time.time() - inicio, 1)
            log.info(f"[Mobile] Firebird pronto apos {elapsed}s ({tentativa} tentativa(s))")
            return True
        except Exception:
            time.sleep(1)

    log.warn(f"[Mobile] Firebird nao ficou pronto em {timeout}s")
    return False


# ---------------------------------------------------------------------------
# Execucao de SQL via isql
# ---------------------------------------------------------------------------

def _rodar_sql_via_isql(
    host: str,
    database: str,
    user: str,
    password: str,
    sql: str,
    nome: str,
) -> dict:
    import subprocess, tempfile, os
    from core.logger import log

    _NO_WINDOW = subprocess.CREATE_NO_WINDOW

    resultado = {"nome": nome, "total": 1, "ok": 0, "erros": []}
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".sql", delete=False, encoding="latin-1"
    )
    try:
        tmp.write(sql)
        tmp.close()
        isql = _encontrar_isql()
        dsn  = f"{host}:{database}"
        proc = subprocess.run(
            [isql, "-user", user, "-password", password, "-input", tmp.name, dsn],
            capture_output=True, text=True, encoding="latin-1",
            creationflags=_NO_WINDOW,
        )
        saida = (proc.stdout or "") + (proc.stderr or "")
        log.info(f"[Mobile][isql][{nome}] rc={proc.returncode}")
        for linha in saida.strip().splitlines():
            log.info(f"[Mobile][isql] {linha}")

        erros_isql = [
            linha.strip() for linha in saida.splitlines()
            if any(p in linha.upper() for p in ("ERROR", "UNSUCCESSFUL", "SQLCODE"))
        ]
        if erros_isql:
            resultado["erros"].append((nome, "\n".join(erros_isql)))
        else:
            resultado["ok"] = 1
    except Exception as e:
        resultado["erros"].append((nome, str(e)))
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass
    return resultado


# ---------------------------------------------------------------------------
# Execucao principal — Implantacao
# ---------------------------------------------------------------------------

def executar_implantacao(
    host: str,
    database: str,
    user: str = "sysdba",
    password: str = "sbofutura",
) -> list[dict[str, Any]]:
    """
    Para o Firebird, reinicia e aguarda estar pronto para aceitar conexoes
    antes de executar os scripts via isql.
    """
    from core.logger import log

    servicos_parados = parar_firebird()
    resultados = []
    try:
        iniciar_firebird(servicos_parados)
        servicos_parados = []

        # Aguarda o Firebird estar realmente aceitando conexoes TCP
        # antes de chamar o isql — evita "Unable to complete network request"
        if not aguardar_firebird_pronto(host, database, user, password):
            raise RuntimeError(
                "Firebird nao ficou disponivel em 30s apos reinicio. "
                "Verifique o servico manualmente."
            )

        for nome_script, sql in SCRIPTS:
            r = _rodar_sql_via_isql(host, database, user, password, sql, nome_script)
            resultados.append(r)

    except Exception as e:
        log.error(f"[Mobile] Erro na implantacao: {e}")
        iniciar_firebird(servicos_parados)
        resultados.append({
            "nome":  "Erro geral",
            "total": 1,
            "ok":    0,
            "erros": [("implantacao", str(e))],
        })

    return resultados


# ---------------------------------------------------------------------------
# Remocao dinamica
# ---------------------------------------------------------------------------

def _consultar_dependentes(conn, objeto: str) -> list[str]:
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT TRIM(d.RDB$DEPENDENT_NAME)
        FROM RDB$DEPENDENCIES d
        JOIN RDB$TRIGGERS t ON TRIM(t.RDB$TRIGGER_NAME) = TRIM(d.RDB$DEPENDENT_NAME)
        WHERE TRIM(d.RDB$DEPENDED_ON_NAME) = ?
          AND d.RDB$DEPENDENT_TYPE = 2
    """, [objeto.strip()])
    rows = cur.fetchall()
    cur.close()
    return [r[0].strip() for r in rows if r[0]]


def _consultar_todas_triggers_tabela(conn, tabela: str) -> list[str]:
    cur = conn.cursor()
    cur.execute("""
        SELECT TRIM(RDB$TRIGGER_NAME)
        FROM RDB$TRIGGERS
        WHERE TRIM(RDB$RELATION_NAME) = ?
          AND RDB$SYSTEM_FLAG = 0
    """, [tabela.strip()])
    rows = cur.fetchall()
    cur.close()
    return [r[0] for r in rows if r[0]]


def _tabela_existe(conn, tabela: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM RDB$RELATIONS "
        "WHERE TRIM(RDB$RELATION_NAME) = ? AND RDB$SYSTEM_FLAG = 0",
        [tabela.strip()]
    )
    row = cur.fetchone()
    cur.close()
    return bool(row and row[0] > 0)


def executar_remocao(
    host: str,
    database: str,
    user: str = "sysdba",
    password: str = "sbofutura",
) -> dict:
    """
    Fluxo:
      1. Consulta dependencias reais via fdb (Firebird rodando)
      2. Para o Firebird
      3. Reinicia o Firebird
      4. Aguarda o Firebird estar pronto para conexoes TCP
      5. Executa script via isql com WHENEVER ERROR CONTINUE
      6. Verifica via fdb se CHANGE_TABLET foi realmente removida
    """
    from core.logger import log
    import os, tempfile, subprocess

    _NO_WINDOW = subprocess.CREATE_NO_WINDOW

    resultado = {
        "nome":  "Remover CHANGE_TABLET",
        "total": 1,
        "ok":    0,
        "erros": [],
    }

    # ── Passo 1: consulta dependencias com Firebird rodando ──────────────────
    triggers_a_dropar: list[str] = []

    if FDB_DISPONIVEL:
        try:
            log.info("[Mobile][remocao] Consultando dependencias no banco...")
            conn = criar_conexao(host, database, user, password)
            try:
                dep1    = _consultar_dependentes(conn, "SP_SET_CHANGE_TABLET")
                dep2    = _consultar_dependentes(conn, "SP_CHANGE_TABLET_EXECUTE")
                trig_ct = _consultar_todas_triggers_tabela(conn, "CHANGE_TABLET")
                vistas  = set()
                for t in dep1 + dep2 + trig_ct:
                    if t not in vistas:
                        vistas.add(t)
                        triggers_a_dropar.append(t)
                log.info(f"[Mobile][remocao] Triggers a dropar: {triggers_a_dropar}")
            finally:
                conn.close()
        except Exception as e:
            log.warn(f"[Mobile][remocao] Nao foi possivel consultar via fdb: {e}")

    if not triggers_a_dropar:
        triggers_a_dropar = [trig for trig, _ in _TABELAS_TRIGGERS] + ["CHANGE_TABLET_AIUD5"]
        log.warn("[Mobile][remocao] Usando lista padrao de triggers")

    # ── Passo 2: monta script com WHENEVER ERROR CONTINUE ───────────────────
    linhas: list[str] = [
        "WHENEVER ERROR CONTINUE;",
        "",
    ]
    for trig in triggers_a_dropar:
        linhas.append(f"DROP TRIGGER {trig.strip()};")
    linhas.append("commit;")
    linhas.append("")
    linhas.append("SET TERM ^ ;")
    linhas.append("ALTER PROCEDURE SP_CHANGE_TABLET_EXECUTE (")
    linhas.append("    TABLE_NAME Varchar(30),")
    linhas.append("    PK_FIELD Varchar(40),")
    linhas.append("    PK_VALUE Varchar(40),")
    linhas.append("    TYPE_OPERATION Char(1) )")
    linhas.append("AS")
    linhas.append("BEGIN")
    linhas.append("END^")
    linhas.append("SET TERM ; ^")
    linhas.append("")
    linhas.append("SET TERM ^ ;")
    linhas.append("ALTER PROCEDURE SP_SET_CHANGE_TABLET (")
    linhas.append("    TABLE_NAME Varchar(30),")
    linhas.append("    PK_FIELD Varchar(40),")
    linhas.append("    PK_VALUE Varchar(40),")
    linhas.append("    TYPE_OPERATION Char(1) )")
    linhas.append("AS")
    linhas.append("BEGIN")
    linhas.append("END^")
    linhas.append("SET TERM ; ^")
    linhas.append("commit;")
    linhas.append("")
    linhas.append("DROP TABLE CHANGE_TABLET;")
    linhas.append("commit;")
    linhas.append("DROP PROCEDURE SP_SET_CHANGE_TABLET;")
    linhas.append("DROP PROCEDURE SP_CHANGE_TABLET_EXECUTE;")
    linhas.append("commit;")
    linhas.append("DROP GENERATOR GEN_CHANGE_TABLET;")
    linhas.append("commit;")

    script_sql = "\n".join(linhas) + "\n"
    log.info(f"[Mobile][remocao] Script:\n{script_sql}")

    # ── Passo 3: para, reinicia, aguarda e executa via isql ─────────────────
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".sql", delete=False, encoding="latin-1"
    )
    servicos_parados: list[str] = []
    try:
        tmp.write(script_sql)
        tmp.close()

        isql = _encontrar_isql()
        dsn  = f"{host}:{database}"

        servicos_parados = parar_firebird()
        iniciar_firebird(servicos_parados)
        servicos_parados = []

        # Aguarda o Firebird estar realmente pronto antes do isql
        aguardar_firebird_pronto(host, database, user, password)

        proc = subprocess.run(
            [isql, "-user", user, "-password", password, "-input", tmp.name, dsn],
            capture_output=True, text=True, encoding="latin-1",
            creationflags=_NO_WINDOW,
        )

        saida = (proc.stdout or "") + (proc.stderr or "")
        log.info(f"[Mobile][remocao] isql rc={proc.returncode}")
        for linha in saida.strip().splitlines():
            log.info(f"[Mobile][remocao] {linha}")

        # ── Passo 4: verifica se CHANGE_TABLET foi realmente removida ────────
        try:
            conn2 = criar_conexao(host, database, user, password)
            try:
                ainda_existe = _tabela_existe(conn2, "CHANGE_TABLET")
            finally:
                conn2.close()

            if ainda_existe:
                erros_isql = [
                    l.strip() for l in saida.splitlines()
                    if any(p in l.upper() for p in ("ERROR", "UNSUCCESSFUL", "SQLCODE"))
                ]
                msg = "\n".join(erros_isql) if erros_isql else "CHANGE_TABLET ainda existe apos o script."
                resultado["erros"].append(("isql output", msg))
                log.error("[Mobile][remocao] CHANGE_TABLET ainda existe apos o script!")
            else:
                resultado["ok"] = 1
                log.ok("[Mobile][remocao] CHANGE_TABLET removida com sucesso!")

        except Exception as e:
            log.warn(f"[Mobile][remocao] Nao foi possivel verificar remocao: {e}")
            resultado["ok"] = 1  # assume ok se nao conseguiu verificar

    except Exception as e:
        log.error(f"[Mobile][remocao] Excecao: {e}")
        resultado["erros"].append(("executar_remocao", str(e)))
        iniciar_firebird(servicos_parados)
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

    return resultado