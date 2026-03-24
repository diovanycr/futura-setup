# =============================================================================
# FUTURA SETUP — Core: Verificar Versão + Integridade do Firebird via .fdb
# Salvar em: core/firebird_version_check.py
# =============================================================================
from __future__ import annotations

import base64
import os
import re
import struct
import subprocess
import winreg


# =============================================================================
# Descriptografia AES — campo VERSAO da tabela PARAMETROS
# =============================================================================

_AES_CHAVE = "H5m4454pFjh201dp54Ddd8gP5Hf6GVFd"


def decrypt_aes(base64_texto: str, chave_str: str = _AES_CHAVE) -> str:
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
    except ImportError as exc:
        raise ImportError(
            "Modulo 'pycryptodome' nao instalado. Execute: pip install pycryptodome"
        ) from exc

    raw    = base64.b64decode(base64_texto)
    texto  = raw.decode("utf-8")
    partes = texto.split("::")

    if len(partes) != 2:
        raise ValueError(f"Formato AES invalido — esperado 'dados::iv', obtido: {texto!r}")

    dados = base64.b64decode(partes[0].strip())
    iv    = partes[1].strip().encode("utf-8")
    chave = chave_str[:32].encode("utf-8")

    cipher     = AES.new(chave, AES.MODE_CBC, iv)
    decriptado = unpad(cipher.decrypt(dados), AES.block_size)
    return decriptado.decode("utf-8")


# =============================================================================
# Mapeamento ODS → Versão Firebird
# =============================================================================

_ODS_MAP: dict[int, str] = {
    8:  "Firebird 1.0",
    9:  "Firebird 1.5",
    10: "Interbase 6.x",
    11: "Firebird 2.x",
    12: "Firebird 3.0",
    13: "Firebird 4.0 / 5.0",
}

_ODS_MINOR_MAP: dict[tuple[int, int], str] = {
    (11, 0): "Firebird 2.0",
    (11, 1): "Firebird 2.1",
    (11, 2): "Firebird 2.5",
    (12, 0): "Firebird 3.0",
    (12, 1): "Firebird 3.0",
    (12, 2): "Firebird 3.0",
    (12, 3): "Firebird 3.0",
    (12, 4): "Firebird 3.0",
    (13, 0): "Firebird 4.0",
    (13, 1): "Firebird 4.0",
    (13, 2): "Firebird 4.0",
    (13, 3): "Firebird 4.0",
    (13, 4): "Firebird 4.0",
    (13, 5): "Firebird 5.0",
}

_PAGE_SIZE_OFFSET = 16
_ODS_MAJOR_OFFSET = 18
_ODS_MINOR_OFFSET = 20
_MIN_READ         = 22
_VALID_PAGE_SIZES = {1024, 2048, 4096, 8192, 16384, 32768}


# =============================================================================
# ID do Cliente — cálculo por CI
# =============================================================================

def ci_para_id_cliente(ci: str | int) -> str:
    ci_str = re.sub(r"\D", "", str(ci).strip())
    if len(ci_str) < 4:
        return ""
    primeiros = ci_str[:4]
    return ("1" + primeiros) if ci_str.endswith("001") else primeiros


# =============================================================================
# Localizar fbclient.dll por ODS — tenta a DLL compatível primeiro
# =============================================================================

# --- Localiza diretório do projeto para busca de DLLs embutidas ---
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOCAL_FB4 = os.path.join(_BASE_DIR, "bin", "firebird", "FB4")
_LOCAL_FB3 = os.path.join(_BASE_DIR, "bin", "firebird", "FB3")

# Caminhos candidatos por versão do Firebird
# Prioridade: 1. Pasta Local (bin/) -> 2. Pasta Portable (C:\FuturaFirebird) -> 3. Instalação Padrão
_FB_DLL_CANDIDATOS: dict[str, list[str]] = {
    "fb4": [
        os.path.join(_LOCAL_FB4, "fbclient.dll"),
        r"C:\FuturaFirebird\FB\fbclient.dll",
        r"C:\FuturaFirebird\FB4\fbclient.dll",
        r"C:\FuturaFirebird\Firebird\fbclient.dll",
        r"C:\Program Files\Firebird\Firebird_5_0\fbclient.dll",
        r"C:\Program Files\Firebird\Firebird_4_0\fbclient.dll",
        r"C:\Program Files (x86)\Firebird\Firebird_4_0\fbclient.dll",
    ],
    "fb3": [
        os.path.join(_LOCAL_FB3, "fbclient.dll"),
        r"C:\FuturaFirebird\FB3\fbclient.dll",
        r"C:\Program Files\Firebird\Firebird_3_0\fbclient.dll",
        r"C:\Program Files (x86)\Firebird\Firebird_3_0\fbclient.dll",
    ],
    "fb2": [
        r"C:\Program Files\Firebird\Firebird_2_5\fbclient.dll",
        r"C:\Program Files (x86)\Firebird\Firebird_2_5\fbclient.dll",
    ],
    "fallback": [
        r"C:\Windows\System32\fbclient.dll",
        r"C:\Windows\SysWOW64\fbclient.dll",
    ],
}


def _dll_existe(path: str) -> bool:
    return os.path.isfile(path)


def _primeira_dll(lista: list[str]) -> str | None:
    return next((p for p in lista if _dll_existe(p)), None)


def _encontrar_fbclient_dll(ods_major: int = 0) -> tuple[str | None, str]:
    """
    Localiza a fbclient.dll mais compatível com o ODS do banco.

    Retorna:
        (caminho_dll, descricao_versao)  ou  (None, "")
    """
    if ods_major >= 13:
        # Banco FB4/FB5 — tenta FB4 primeiro, depois FB3 como fallback
        ordem = [
            (_FB_DLL_CANDIDATOS["fb4"], "Firebird 4/5"),
            (_FB_DLL_CANDIDATOS["fb3"], "Firebird 3"),
            (_FB_DLL_CANDIDATOS["fallback"], "sistema"),
        ]
    elif ods_major == 12:
        # Banco FB3 — tenta FB3 primeiro, depois FB4
        ordem = [
            (_FB_DLL_CANDIDATOS["fb3"], "Firebird 3"),
            (_FB_DLL_CANDIDATOS["fb4"], "Firebird 4/5"),
            (_FB_DLL_CANDIDATOS["fallback"], "sistema"),
        ]
    elif ods_major == 11:
        ordem = [
            (_FB_DLL_CANDIDATOS["fb2"], "Firebird 2.5"),
            (_FB_DLL_CANDIDATOS["fb3"], "Firebird 3"),
            (_FB_DLL_CANDIDATOS["fallback"], "sistema"),
        ]
    else:
        ordem = [
            (_FB_DLL_CANDIDATOS["fb4"], "Firebird 4/5"),
            (_FB_DLL_CANDIDATOS["fb3"], "Firebird 3"),
            (_FB_DLL_CANDIDATOS["fb2"], "Firebird 2.5"),
            (_FB_DLL_CANDIDATOS["fallback"], "sistema"),
        ]

    for candidatos, descricao in ordem:
        dll = _primeira_dll(candidatos)
        if dll:
            return dll, descricao
    return None, ""


def _ods_da_dll(dll_path: str) -> int:
    """
    Tenta inferir o ODS máximo suportado pela DLL a partir do caminho.
    Retorna 0 se não identificado.
    """
    p = dll_path.lower()
    if "firebird_5" in p or "fb5" in p:
        return 13
    if "firebird_4" in p or "fb4" in p or (r"futurafirebird\fb" in p and "fb3" not in p):
        return 13
    if "firebird_3" in p or "fb3" in p:
        return 12
    if "firebird_2" in p or "fb2" in p:
        return 11
    return 0


# =============================================================================
# Consulta via subprocess — isola o carregamento da DLL em processo limpo
# =============================================================================

# Script Python embutido executado em subprocesso para cada DLL candidata.
# Recebe argumentos: dll_path db_path user password
_SUBPROCESS_SCRIPT = r"""
import sys, json, os

dll  = sys.argv[1]
path = sys.argv[2]
user = sys.argv[3]
pwd  = sys.argv[4]

dll_dir = os.path.dirname(os.path.abspath(dll))

# PATH: permite que o Windows encontre ib_util.dll, icudt67.dll, etc.
os.environ['PATH'] = dll_dir + os.pathsep + os.environ.get('PATH', '')

# FIREBIRD: indica ao fbclient.dll onde esta a pasta plugins (engine13.dll)
# Isso e obrigatorio para o modo embedded funcionar sem servidor instalado.
os.environ['FIREBIRD'] = dll_dir
os.environ.setdefault('FIREBIRD_TMP', os.environ.get('TEMP', 'C:\\Temp'))

if hasattr(os, 'add_dll_directory'):
    try: os.add_dll_directory(dll_dir)
    except: pass

try:
    import fdb
    fdb.load_api(dll)
except Exception as e:
    print(json.dumps({'ok': False, 'error': f'load_api: {e}'}))
    sys.exit(0)

# Tenta embedded primeiro (sem servidor), depois localhost (com servidor)
last = ''
for host in ['', 'localhost']:
    try:
        con = fdb.connect(host=host, database=path, user=user, password=pwd)
        cur = con.cursor()
        cur.execute('SELECT BUILD_BD, BUILD_EXE, VERSAO, CI FROM PARAMETROS')
        row = cur.fetchone()
        con.close()
        if row:
            print(json.dumps({
                'ok': True,
                'build_bd':  int(row[0]) if row[0] is not None else 0,
                'build_exe': int(row[1]) if row[1] is not None else 0,
                'versao':    str(row[2] or '').strip(),
                'ci':        str(row[3] or '').strip(),
            }))
            sys.exit(0)
        last = 'PARAMETROS vazia'
    except Exception as e:
        last = str(e)

print(json.dumps({'ok': False, 'error': last}))
"""


def _consultar_via_subprocess(
    dll: str, path: str, user: str, password: str
) -> tuple[dict | None, str]:
    """
    Executa a consulta PARAMETROS em subprocess isolado.
    Contorna a limitao do fdb (uma DLL por processo Python).
    """
    import json
    import sys as _sys

    python_exe = _sys.executable

    # Em apps empacotados (PyInstaller) sys.executable e o .exe, nao o Python.
    # Nesse caso voltamos ao metodo inprocess.
    if getattr(_sys, "frozen", False):
        return None, "__frozen__"   # sinal para usar fallback inline

    try:
        proc = subprocess.run(
            [python_exe, "-c", _SUBPROCESS_SCRIPT, dll, path, user, password],
            capture_output=True,
            text=True,
            timeout=20,
            encoding="utf-8",
            errors="ignore",
        )
        raw = (proc.stdout or "").strip()
        if not raw:
            stderr = (proc.stderr or "").strip()
            return None, stderr or "Sem resposta do subprocess"

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None, f"Resposta invalida: {raw[:200]}"

        if data.get("ok"):
            return {
                "build_bd":  data.get("build_bd",  0),
                "build_exe": data.get("build_exe", 0),
                "versao":    data.get("versao",    ""),
                "ci":        data.get("ci",        ""),
            }, ""
        return None, data.get("error", "Erro desconhecido no subprocess")

    except subprocess.TimeoutExpired:
        return None, "Timeout (20s) ao conectar. Banco muito grande ou servidor bloqueado."
    except FileNotFoundError:
        return None, "__frozen__"   # python_exe nao encontrado, usa fallback
    except Exception as e:
        return None, str(e)


def _conectar_fdb_inline(dll: str, path: str, user: str, password: str):
    """Fallback inline (app empacotado): tenta conectar no processo atual."""
    import fdb  # type: ignore

    dll_dir = os.path.dirname(os.path.abspath(dll))

    # PATH: DLLs dependentes (ib_util.dll, ICU, etc.)
    old_path = os.environ.get("PATH", "")
    if dll_dir.lower() not in old_path.lower():
        os.environ["PATH"] = dll_dir + os.pathsep + old_path

    # FIREBIRD: diz ao fbclient.dll onde esta a pasta plugins\
    old_fb   = os.environ.get("FIREBIRD", "")
    os.environ["FIREBIRD"] = dll_dir
    os.environ.setdefault("FIREBIRD_TMP", os.environ.get("TEMP", "C:\\Temp"))

    _ctx = None
    if hasattr(os, "add_dll_directory"):
        try:
            _ctx = os.add_dll_directory(dll_dir)
        except Exception:
            pass

    try:
        try:
            fdb.load_api(dll)
        except Exception as e:
            if "already loaded" not in str(e).lower():
                raise
        for host in ["", "localhost"]:
            try:
                return fdb.connect(
                    host=host, database=path, user=user, password=password
                )
            except Exception:
                pass
        raise RuntimeError("Nao foi possivel conectar (embedded nem localhost)")
    finally:
        os.environ["PATH"] = old_path
        if old_fb:
            os.environ["FIREBIRD"] = old_fb
        else:
            os.environ.pop("FIREBIRD", None)
        if _ctx is not None:
            try:
                _ctx.close()
            except Exception:
                pass


def _consultar_parametros(
    path: str, user: str, password: str, ods_major: int = 0
) -> tuple[dict | None, str]:
    """
    Consulta BUILD_BD, BUILD_EXE, VERSAO e CI da tabela PARAMETROS.

    Estrategia:
      1. Para cada DLL candidata, executa a consulta em subprocess isolado
         (contorna a limitacao do fdb: uma DLL por processo Python).
      2. Se a DLL e compativel com o ODS e a conexao falha por outro motivo,
         exibe o erro real (servidor parado, credenciais, etc.).
      3. So exibe 'nenhuma DLL suporta' quando o unico erro e ODS -820.
    """
    try:
        import fdb  # type: ignore  # noqa: F401
    except ImportError:
        return None, "Modulo 'fdb' nao instalado. Execute: pip install fdb"

    # DLL principal (mais compativel com o ODS do banco)
    dll_principal, _ = _encontrar_fbclient_dll(ods_major)
    if not dll_principal:
        return None, (
            "fbclient.dll nao encontrada. "
            "Instale o Firebird ou copie fbclient.dll para C:\\FuturaFirebird\\FB\\"
        )

    # Lista completa de DLLs para tentar (principal primeiro)
    todas_dlls_ordenadas = (
        _FB_DLL_CANDIDATOS["fb4"] +
        _FB_DLL_CANDIDATOS["fb3"] +
        _FB_DLL_CANDIDATOS["fb2"] +
        _FB_DLL_CANDIDATOS["fallback"]
    )
    vistas: set[str] = set()
    dlls_para_tentar: list[str] = []
    for dll in [dll_principal] + todas_dlls_ordenadas:
        if dll not in vistas and _dll_existe(dll):
            vistas.add(dll)
            dlls_para_tentar.append(dll)

    erros_ods_ok: list[str]           = []   # DLL versao-compativel, conexao falhou
    erros_ods_incompativel: list[str] = []   # DLL versao-errada, deu -820 (esperado)
    erros_outros: list[str]           = []   # Outros
    usar_fallback_inline              = False

    for dll in dlls_para_tentar:
        dll_ods       = _ods_da_dll(dll)
        dll_compativel = (dll_ods == 0) or (dll_ods >= ods_major)
        dir_dll       = os.path.basename(os.path.dirname(dll))

        # --- Tenta via subprocess (processo Python limpo, sem "DLL already loaded") ---
        dados, erro = _consultar_via_subprocess(dll, path, user, password)

        if erro == "__frozen__":
            # App empacotado — usa fallback inline para este e todos os demais
            usar_fallback_inline = True

        if usar_fallback_inline:
            # Fallback: conexao no processo atual (limitado a primeira DLL carregada)
            try:
                con = _conectar_fdb_inline(dll, path, user, password)
                cur = con.cursor()
                cur.execute("SELECT BUILD_BD, BUILD_EXE, VERSAO, CI FROM PARAMETROS")
                row = cur.fetchone()
                con.close()
                if not row:
                    return None, "Tabela PARAMETROS vazia."
                return {
                    "build_bd":  int(row[0]) if row[0] is not None else 0,
                    "build_exe": int(row[1]) if row[1] is not None else 0,
                    "versao":    str(row[2]).strip() if row[2] is not None else "",
                    "ci":        str(row[3]).strip() if row[3] is not None else "",
                }, ""
            except Exception as e:
                msg = str(e)
                if "-820" in msg or "unsupported on-disk structure" in msg.lower():
                    erros_ods_incompativel.append(f"{dir_dll}: ODS incompativel")
                elif dll_compativel:
                    erros_ods_ok.append(f"{dir_dll}: {msg}")
                else:
                    erros_outros.append(f"{dir_dll}: {msg}")
            continue

        # subprocess retornou dados validos
        if dados is not None:
            return dados, ""

        # Classifica o erro retornado pelo subprocess
        if "-820" in erro or "unsupported on-disk structure" in erro.lower():
            erros_ods_incompativel.append(f"{dir_dll}: ODS incompativel")
        elif dll_compativel:
            erros_ods_ok.append(f"{dir_dll}: {erro}")
        else:
            erros_outros.append(f"{dir_dll}: {erro}")

    # -------------------------------------------------------------------------
    # Nenhuma DLL conectou — monta mensagem util
    # -------------------------------------------------------------------------
    versao_banco = _ODS_MINOR_MAP.get(
        (ods_major, 0), _ODS_MAP.get(ods_major, f"ODS {ods_major}")
    )

    if erros_ods_ok:
        # A DLL certa esta instalada, mas a conexao falhou por outro motivo
        return None, (
            f"fbclient.dll do {versao_banco} encontrada, mas a conexao falhou.\n"
            f"Erro: {erros_ods_ok[0]}\n"
            f"Verifique se o servico Firebird esta ativo e se as credenciais estao corretas."
        )

    if erros_ods_incompativel and not erros_ods_ok:
        dlls_dir = [
            os.path.dirname(d) for d in dlls_para_tentar
            if "system32" not in d.lower() and "syswow64" not in d.lower()
        ]
        msg_dlls = f"DLLs encontradas: {', '.join(dlls_dir)}" if dlls_dir else "Nenhuma instalacao compativel encontrada."
        return None, (
            f"Banco criado com {versao_banco} (ODS {ods_major}), "
            f"mas nenhuma fbclient.dll instalada suporta essa versao.\n"
            f"{msg_dlls}\n"
            f"Instale o Firebird {versao_banco} em C:\\FuturaFirebird\\FB{ods_major - 9}\\ "
            f"ou em C:\\Program Files\\Firebird\\Firebird_{ods_major - 9}_0\\"
        )

    todos = erros_ods_ok + erros_ods_incompativel + erros_outros
    return None, todos[-1] if todos else "Erro desconhecido ao conectar."



# =============================================================================
# Detectar instalação do Firebird
# =============================================================================

def _encontrar_fb_dir() -> str | None:
    def _tem_gfix(pasta: str) -> bool:
        return os.path.isfile(os.path.join(pasta, "gfix.exe"))

    portable_bases = [
        r"C:\FuturaFirebird\FB",
        r"C:\FuturaFirebird\FB4",
        r"C:\FuturaFirebird\Firebird",
        r"C:\FuturaFirebird\FB3",
    ]
    for base in portable_bases:
        if _tem_gfix(base):
            return base

    chaves = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Firebird Project\Firebird Server\Instances"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Firebird Project\Firebird Server\Instances"),
    ]
    for hive, chave in chaves:
        try:
            with winreg.OpenKey(hive, chave) as k:
                path, _ = winreg.QueryValueEx(k, "DefaultInstance")
                if path and os.path.isdir(path) and _tem_gfix(path):
                    return path
        except Exception:
            continue

    candidatos = [
        r"C:\Program Files\Firebird\Firebird_5_0",
        r"C:\Program Files\Firebird\Firebird_4_0",
        r"C:\Program Files\Firebird\Firebird_3_0",
        r"C:\Program Files (x86)\Firebird\Firebird_4_0",
        r"C:\Program Files (x86)\Firebird\Firebird_3_0",
    ]
    for c in candidatos:
        if _tem_gfix(c):
            return c
    return None


def _versao_instalada() -> str:
    fb_dir = _encontrar_fb_dir()
    if not fb_dir:
        return "Nao encontrado"

    gbak = os.path.join(fb_dir, "gbak.exe")
    if os.path.isfile(gbak):
        try:
            out = subprocess.check_output(
                [gbak, "-z"], timeout=5, stderr=subprocess.STDOUT
            ).decode(errors="ignore")
            m = re.search(r"WI-V([\d.]+)", out)
            if m:
                return m.group(1)
        except Exception:
            pass

    for exe in ["fbserver.exe", "fb_inet_server.exe", "firebird.exe"]:
        exe_path = os.path.join(fb_dir, exe)
        if not os.path.isfile(exe_path):
            continue
        try:
            cmd = f'(Get-Item "{exe_path}").VersionInfo.FileVersion'
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", cmd],
                timeout=5, stderr=subprocess.DEVNULL,
            ).decode(errors="ignore").strip()
            if out:
                return out
        except Exception:
            pass

    nome = os.path.basename(fb_dir).lower()
    for v in ["5_0", "4_0", "3_0"]:
        if v in nome:
            return f"{v.replace('_', '.')} (pasta: {os.path.basename(fb_dir)})"
    return f"Instalado em: {fb_dir}"


# =============================================================================
# Validação real via gfix
# =============================================================================

def _validar_com_gfix(path: str, user: str, password: str) -> dict:
    resultado = {
        "executado":   False,
        "ok":          False,
        "erros":       [],
        "avisos":      [],
        "saida_bruta": "",
        "msg":         "",
    }

    fb_dir = _encontrar_fb_dir()
    if not fb_dir:
        resultado["msg"] = "Firebird nao encontrado na maquina. Instale o Firebird para validar."
        return resultado

    gfix = os.path.join(fb_dir, "gfix.exe")
    if not os.path.isfile(gfix):
        resultado["msg"] = f"gfix.exe nao encontrado em: {fb_dir}"
        return resultado

    try:
        proc = subprocess.run(
            [gfix, "-validate", "-full", "-user", user, "-password", password, path],
            capture_output=True, timeout=120, text=True,
            encoding="utf-8", errors="ignore",
        )
        saida = (proc.stdout + proc.stderr).strip()
        resultado["executado"]   = True
        resultado["saida_bruta"] = saida

        if not saida:
            resultado["ok"] = True
            return resultado

        # Detecta erro de ODS incompatível no gfix também
        if "-820" in saida or "unsupported on-disk structure" in saida.lower():
            ods_match = re.search(r"found (\d+\.\d+).*support (\d+\.\d+)", saida, re.IGNORECASE)
            if ods_match:
                encontrado  = ods_match.group(1)
                suportado   = ods_match.group(2)
                resultado["msg"] = (
                    f"O gfix instalado nao suporta este banco (ODS {encontrado}). "
                    f"O gfix atual suporta ate ODS {suportado}. "
                    f"Instale o Firebird compativel com o banco para validar a integridade."
                )
            else:
                resultado["msg"] = (
                    "O gfix instalado e incompativel com a versao deste banco. "
                    "Instale o Firebird correto para validar a integridade."
                )
            return resultado

        for linha in saida.splitlines():
            l  = linha.strip()
            ll = l.lower()
            if not l:
                continue
            if any(k in ll for k in ["error", "corrupt", "wrong", "bad", "invalid", "damaged"]):
                resultado["erros"].append(l)
            elif any(k in ll for k in ["warning", "warn"]):
                resultado["avisos"].append(l)

        resultado["ok"] = len(resultado["erros"]) == 0

    except subprocess.TimeoutExpired:
        resultado["executado"] = True
        resultado["avisos"].append("Validacao excedeu o tempo limite (120s). Banco muito grande.")
        resultado["ok"] = False
    except PermissionError:
        resultado["msg"] = "Sem permissao para acessar o arquivo. Execute como Administrador."
    except Exception as e:
        resultado["msg"] = f"Erro ao rodar gfix: {e}"

    return resultado


# =============================================================================
# Verificações básicas do header (sem conexão)
# =============================================================================

def _verificar_header(path: str, page_size: int) -> dict:
    resultado = {"ok": True, "erros": [], "detalhes": []}
    try:
        tamanho = os.path.getsize(path)
        if tamanho == 0:
            resultado["erros"].append("Arquivo vazio (0 bytes).")
            resultado["ok"] = False
            return resultado

        resultado["detalhes"].append(f"Tamanho: {tamanho / (1024 * 1024):.1f} MB")

        if tamanho % page_size != 0:
            resultado["erros"].append(
                f"Tamanho ({tamanho} bytes) nao e multiplo do page size ({page_size}). "
                "Possivel truncamento."
            )
            resultado["ok"] = False
        else:
            resultado["detalhes"].append(f"Paginas: {tamanho // page_size:,} (multiplo correto)")

        with open(path, "rb") as f:
            hdr = f.read(min(page_size, 512))
        if not hdr or hdr[0] != 1:
            resultado["erros"].append(
                f"Pagina 0 com tipo invalido (byte={hdr[0] if hdr else '?'}). "
                "Cabecalho corrompido."
            )
            resultado["ok"] = False
        else:
            resultado["detalhes"].append("Cabecalho (pagina 0): OK")

    except Exception as e:
        resultado["erros"].append(f"Erro ao verificar header: {e}")
        resultado["ok"] = False

    return resultado


# =============================================================================
# Função principal
# =============================================================================

def verificar_versao_fdb(
    path: str,
    user: str        = "SYSDBA",
    password: str    = "sbofutura",
    rodar_gfix: bool = True,
) -> dict:
    result = {
        "ok":                False,
        "ods_major":         0,
        "ods_minor":         0,
        "versao_arquivo":    "",
        "versao_instalada":  "",
        "page_size":         0,
        "header_ok":         True,
        "header_erros":      [],
        "header_detalhes":   [],
        "gfix_executado":    False,
        "gfix_ok":           False,
        "gfix_erros":        [],
        "gfix_avisos":       [],
        "gfix_saida_bruta":  "",
        "gfix_msg":          "",
        "build_bd":          0,
        "build_exe":         0,
        "versao_futura":     "",
        "versao_futura_erro": "",
        "ci":                "",
        "id_cliente":        "",
        "id_cliente_erro":   "",
        "erro":              "",
    }

    if not path:
        result["erro"] = "Nenhum arquivo informado."
        return result

    if not os.path.isfile(path):
        result["erro"] = f"Arquivo nao encontrado: {path}"
        return result

    ext = os.path.splitext(path)[1].lower()
    if ext not in (".fdb", ".gdb", ".db"):
        result["erro"] = f"Extensao nao reconhecida: '{ext}'. Use .fdb, .gdb ou .db"
        return result

    try:
        with open(path, "rb") as f:
            data = f.read(128)

        if len(data) < _MIN_READ:
            result["erro"] = "Arquivo muito pequeno ou corrompido."
            return result

        page_size = struct.unpack_from("<H", data, _PAGE_SIZE_OFFSET)[0]
        ods_major = data[_ODS_MAJOR_OFFSET]
        ods_minor = data[_ODS_MINOR_OFFSET]

        if page_size not in _VALID_PAGE_SIZES:
            result["erro"] = (
                f"Page size invalido ({page_size}). "
                "O arquivo pode nao ser um banco Firebird valido."
            )
            return result

        if ods_major < 8 or ods_major > 20:
            result["erro"] = (
                f"ODS invalido ({ods_major}.{ods_minor}). "
                "O arquivo pode nao ser um banco Firebird valido."
            )
            return result

        versao_arquivo   = _ODS_MINOR_MAP.get(
            (ods_major, ods_minor),
            _ODS_MAP.get(ods_major, f"Desconhecido (ODS {ods_major}.{ods_minor})")
        )
        versao_instalada = _versao_instalada()
        header           = _verificar_header(path, page_size)
        gfix             = _validar_com_gfix(path, user, password) if rodar_gfix else {
            "executado": False, "ok": False,
            "erros": [], "avisos": [], "saida_bruta": "", "msg": "",
        }

        params_data, params_erro = _consultar_parametros(path, user, password, ods_major)

        build_bd           = 0
        build_exe          = 0
        ci_raw             = ""
        versao_futura      = ""
        versao_futura_erro = params_erro

        if params_data:
            build_bd  = params_data["build_bd"]
            build_exe = params_data["build_exe"]
            ci_raw    = params_data["ci"]

            versao_raw = params_data["versao"]
            if versao_raw:
                try:
                    versao_futura      = decrypt_aes(versao_raw)
                    versao_futura_erro = ""
                except ImportError as e:
                    versao_futura_erro = str(e)
                except Exception as e:
                    versao_futura_erro = f"Erro ao descriptografar VERSAO: {e}"
            else:
                versao_futura_erro = "Campo VERSAO vazio em PARAMETROS."

        id_cliente      = ci_para_id_cliente(ci_raw) if ci_raw else ""
        id_cliente_erro = "" if ci_raw else (params_erro or "CI nao disponivel.")

        result.update({
            "ok":                True,
            "ods_major":         ods_major,
            "ods_minor":         ods_minor,
            "versao_arquivo":    versao_arquivo,
            "versao_instalada":  versao_instalada,
            "page_size":         page_size,
            "header_ok":         header["ok"],
            "header_erros":      header["erros"],
            "header_detalhes":   header["detalhes"],
            "gfix_executado":    gfix["executado"],
            "gfix_ok":           gfix["ok"],
            "gfix_erros":        gfix["erros"],
            "gfix_avisos":       gfix["avisos"],
            "gfix_saida_bruta":  gfix["saida_bruta"],
            "gfix_msg":          gfix["msg"],
            "build_bd":          build_bd,
            "build_exe":         build_exe,
            "versao_futura":     versao_futura,
            "versao_futura_erro": versao_futura_erro,
            "ci":                ci_raw,
            "id_cliente":        id_cliente,
            "id_cliente_erro":   id_cliente_erro,
            "erro":              "",
        })

    except PermissionError:
        result["erro"] = "Sem permissao para ler o arquivo. Execute como Administrador."
    except Exception as e:
        result["erro"] = f"Erro ao ler arquivo: {e}"

    return result