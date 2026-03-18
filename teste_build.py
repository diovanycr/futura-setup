import os
import fdb

path     = r'C:\FuturaDados\GOURMET.fdb'
user     = 'SYSDBA'
password = 'sbofutura'

# Candidatos para fbclient.dll
candidatos_dll = [
    r'C:\FuturaFirebird\FB\fbclient.dll',
    r'C:\FuturaFirebird\FB4\fbclient.dll',
    r'C:\FuturaFirebird\FB3\fbclient.dll',
    r'C:\Program Files\Firebird\Firebird_4_0\fbclient.dll',
    r'C:\Program Files\Firebird\Firebird_3_0\fbclient.dll',
    r'C:\Program Files (x86)\Firebird\Firebird_4_0\fbclient.dll',
    r'C:\Program Files (x86)\Firebird\Firebird_3_0\fbclient.dll',
    r'C:\Windows\System32\fbclient.dll',
    r'C:\Windows\SysWOW64\fbclient.dll',
]

dll_encontrada = None
for dll in candidatos_dll:
    if os.path.isfile(dll):
        dll_encontrada = dll
        print(f"fbclient.dll encontrada: {dll}")
        break

if not dll_encontrada:
    print("ERRO: fbclient.dll nao encontrada em nenhum caminho!")
    print("Caminhos verificados:")
    for c in candidatos_dll:
        print(f"  {c}")
    exit(1)

# Inicializar fdb com a dll encontrada
fdb.load_api(dll_encontrada)

tentativas = [
    {'host': 'localhost', 'database': path},
    {'host': '',          'database': path},
]

for p in tentativas:
    try:
        print(f"\nTentando host={repr(p['host'])}...")
        con = fdb.connect(host=p['host'], database=p['database'], user=user, password=password)
        cur = con.cursor()
        cur.execute('SELECT BUILD_BD FROM PARAMETROS')
        row = cur.fetchone()
        con.close()
        print(f"SUCESSO! BUILD_BD = {row[0]}")
        break
    except Exception as e:
        print(f"ERRO: {e}")