"""
teste_pis.py — Teste direto de conexao e UPDATE do PIS no Firebird.
Execute: python teste_pis.py
"""

import fdb
import re

# ── Ajuste aqui se necessario ─────────────────────────────────────────────
HOST     = "localhost"
DATABASE = r"C:\Futura_atualizar\Dados\gourmet-2025.5.fdb"
USER     = "sysdba"
PASSWORD = "sbofutura"
FK       = 13103
NOVO_PIS = "11111111111"   # 11 digitos sem mascara
# ─────────────────────────────────────────────────────────────────────────

print("=" * 50)
print("TESTE DE GRAVACAO DO PIS")
print("=" * 50)

try:
    print(f"\n[1] Conectando em {HOST} / {DATABASE}...")
    conn = fdb.connect(
        host=HOST, database=DATABASE,
        user=USER, password=PASSWORD,
        charset="WIN1252"
    )
    print("    OK — conexao estabelecida.")

    cur = conn.cursor()

    print(f"\n[2] Lendo PIS atual (FK_CADASTRO={FK})...")
    cur.execute(
        "SELECT ID, FK_CADASTRO, PIS FROM CADASTRO_FUNCIONARIO WHERE FK_CADASTRO = ?",
        (FK,)
    )
    row = cur.fetchone()
    if row is None:
        print(f"    ERRO: nenhum registro encontrado para FK_CADASTRO={FK}")
    else:
        print(f"    ID={row[0]}  FK_CADASTRO={row[1]}  PIS={row[2]!r}")

    print(f"\n[3] Executando UPDATE...")
    cur.execute(
        "UPDATE CADASTRO_FUNCIONARIO SET PIS = ? WHERE FK_CADASTRO = ?",
        (NOVO_PIS, FK)
    )
    print(f"    rowcount = {cur.rowcount}")

    print("\n[4] Fazendo COMMIT...")
    conn.commit()
    print("    OK")

    print(f"\n[5] Verificando PIS apos commit...")
    cur.execute(
        "SELECT ID, FK_CADASTRO, PIS FROM CADASTRO_FUNCIONARIO WHERE FK_CADASTRO = ?",
        (FK,)
    )
    row = cur.fetchone()
    if row is None:
        print(f"    ERRO: registro sumiu apos commit?")
    else:
        print(f"    ID={row[0]}  FK_CADASTRO={row[1]}  PIS={row[2]!r}")
        if str(row[2] or "").strip() == NOVO_PIS:
            print("\n>>> SUCESSO: PIS gravado corretamente!")
        else:
            print(f"\n>>> FALHA: PIS no banco e '{row[2]}', esperado '{NOVO_PIS}'")

    cur.close()
    conn.close()

except Exception as e:
    print(f"\n>>> EXCECAO: {e}")

print("\n" + "=" * 50)
input("Pressione Enter para fechar...")