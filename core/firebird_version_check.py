# =============================================================================
# FUTURA SETUP — Core: Verificar Versão + Integridade do Firebird via .fdb
# Salvar em: core/firebird_version_check.py
#
# Layout real do header confirmado por análise binária:
#   offset 16 : uint16 LE — page size         (ex: 16384)
#   offset 18 : byte baixo — ODS major         (ex: 0x0c = 12 = FB3)
#   offset 20 : byte baixo — ODS minor         (ex: 0x03 = 3)
#
# Versão Futura:
#   Calculada a partir do BUILD_BD da tabela PARAMETROS.
#   Âncoras confirmadas: 73xxx = 2021.04.26 | 114xxx = 2026.02.09
#   Intervalo médio entre releases: ~42.68 dias
# =============================================================================
from __future__ import annotations

import os
import re
import struct
import subprocess
import winreg
from datetime import datetime, timedelta


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
# Versão do Sistema Futura — cálculo por BUILD_BD
# =============================================================================

_FUTURA_ANCHOR_PREFIX = 73
_FUTURA_ANCHOR_DATE   = datetime(2021, 4, 26)
_FUTURA_ANCHOR_114    = datetime(2026, 2, 9)
_FUTURA_AVG_INTERVAL  = (
    (_FUTURA_ANCHOR_114 - _FUTURA_ANCHOR_DATE).days / (114 - _FUTURA_ANCHOR_PREFIX)
)  # ~42.68 dias por release

# Dados históricos confirmados: prefixo → versão real
_FUTURA_HISTORICO: dict[int, str] = {
    5:  "2015.12.02",  6:  "2016.03.14",  7:  "2016.04.11",
    8:  "2016.05.09",  9:  "2016.06.06",  10: "2016.08.01",
    11: "2016.08.29",  12: "2016.09.26",  13: "2016.10.24",
    14: "2016.11.21",  15: "2017.01.16",  16: "2017.02.13",
    17: "2017.03.13",  18: "2017.04.10",  19: "2017.05.08",
    20: "2017.06.05",  21: "2017.07.03",  22: "2017.07.31",
    23: "2017.08.28",  25: "2017.09.25",  26: "2017.10.23",
    27: "2017.11.20",  28: "2018.01.29",  29: "2018.02.26",
    31: "2018.03.26",  32: "2018.04.23",  33: "2018.05.21",
    34: "2018.06.18",  35: "2018.07.16",  36: "2018.08.13",
    37: "2018.09.10",  38: "2018.10.08",  39: "2018.11.05",
    40: "2018.12.03",  41: "2019.01.28",  42: "2019.02.25",
    43: "2019.03.25",  44: "2019.04.22",  45: "2019.05.20",
    46: "2019.06.17",  47: "2019.07.15",  48: "2019.08.12",
    49: "2019.09.09",  50: "2019.10.07",  51: "2019.11.04",
    52: "2019.12.02",  53: "2020.01.27",  59: "2020.02.24",
    61: "2020.04.20",  62: "2020.05.18",  63: "2020.06.15",
    64: "2020.07.13",  65: "2020.08.01",  66: "2020.09.01",
    67: "2020.10.01",  68: "2020.11.02",  69: "2020.11.30",
    70: "2021.02.01",  71: "2021.03.01",  72: "2021.03.29",
    73: "2021.04.26",  114: "2026.02.09",
}


def _build_para_versao_futura(build_bd: int) -> tuple[str, bool]:
    """
    Converte BUILD_BD em versão do sistema Futura.

    Retorna:
        (versao_str, is_estimado)
        ex: ("2026.02.09", False)  → confirmado
            ("2025.01.20", True)   → estimado por interpolação
    """
    s = str(abs(build_bd))
    if len(s) >= 5:
        prefix = int(s[:3])
    elif len(s) >= 3:
        prefix = int(s[:2])
    else:
        prefix = int(s[:1])

    if prefix in _FUTURA_HISTORICO:
        return _FUTURA_HISTORICO[prefix], False

    days = (prefix - _FUTURA_ANCHOR_PREFIX) * _FUTURA_AVG_INTERVAL
    dt   = _FUTURA_ANCHOR_DATE + timedelta(days=days)
    return dt.strftime("%Y.%m.%d"), True


def _encontrar_fbclient_dll(ods_major: int = 0) -> str | None:
    """
    Localiza fbclient.dll compatível com a versão do banco.

    Se ods_major >= 13 (FB4/FB5): prioriza DLLs do Firebird 4/5.
    Se ods_major == 12 (FB3):     prioriza DLLs do Firebird 3.
    Se ods_major == 0 (desconhecido): tenta FB4 primeiro.
    """
    # Candidatos FB4/FB5
    fb4_candidatos = [
        r"C:\FuturaFirebird\FB\fbclient.dll",
        r"C:\FuturaFirebird\FB4\fbclient.dll",
        r"C:\FuturaFirebird\Firebird\fbclient.dll",
        r"C:\Program Files\Firebird\Firebird_5_0\fbclient.dll",
        r"C:\Program Files\Firebird\Firebird_4_0\fbclient.dll",
        r"C:\Program Files (x86)\Firebird\Firebird_4_0\fbclient.dll",
    ]

    # Candidatos FB3
    fb3_candidatos = [
        r"C:\FuturaFirebird\FB3\fbclient.dll",
        r"C:\Program Files\Firebird\Firebird_3_0\fbclient.dll",
        r"C:\Program Files (x86)\Firebird\Firebird_3_0\fbclient.dll",
    ]

    # Fallback genérico
    fallback = [
        r"C:\Windows\System32\fbclient.dll",
        r"C:\Windows\SysWOW64\fbclient.dll",
    ]

    # Definir ordem de acordo com ODS
    if ods_major >= 13:        # FB4 ou FB5
        ordem = fb4_candidatos + fb3_candidatos + fallback
    elif ods_major == 12:      # FB3
        ordem = fb3_candidatos + fb4_candidatos + fallback
    else:                      # desconhecido — tenta FB4 primeiro
        ordem = fb4_candidatos + fb3_candidatos + fallback

    for c in ordem:
        if os.path.isfile(c):
            return c
    return None


def _consultar_build_bd(
    path: str, user: str, password: str, ods_major: int = 0
) -> tuple[int | None, str]:
    """
    Conecta no .fdb via módulo fdb e retorna (BUILD_BD, erro).
    Executa: SELECT BUILD_BD FROM PARAMETROS
    Usa acesso direto ao arquivo (host='') que funciona sem servico rodando.
    Seleciona fbclient.dll compatível com o ODS do banco.
    """
    try:
        import fdb  # type: ignore
    except ImportError:
        return None, "Modulo 'fdb' nao instalado. Execute: pip install fdb"

    dll = _encontrar_fbclient_dll(ods_major)
    if not dll:
        return None, (
            "fbclient.dll nao encontrada. "
            "Instale o Firebird ou copie fbclient.dll para C:\\FuturaFirebird\\FB\\"
        )

    try:
        fdb.load_api(dll)
    except Exception as e:
        return None, f"Erro ao carregar fbclient.dll ({dll}): {e}"

    tentativas = [
        {"host": "",          "database": path},
        {"host": "localhost", "database": path},
    ]

    ultimo_erro = ""
    for params in tentativas:
        try:
            con = fdb.connect(
                host=params["host"],
                database=params["database"],
                user=user,
                password=password,
            )
            cur = con.cursor()
            cur.execute("SELECT BUILD_BD FROM PARAMETROS")
            row = cur.fetchone()
            con.close()
            if row:
                return int(row[0]), ""
            return None, "Tabela PARAMETROS vazia."
        except Exception as e:
            ultimo_erro = str(e)
            continue

    return None, ultimo_erro


# =============================================================================
# Detectar instalação do Firebird
# =============================================================================

def _encontrar_fb_dir() -> str | None:
    """
    Retorna o diretório do Firebird que contém gfix.exe.

    Ordem de busca:
      1. Portable Futura  — C:\\FuturaFirebird\\FB  (e subpasta bin\\)
      2. Registro do Windows
      3. Pastas padrão de instalação
    """

    def _tem_gfix(pasta: str) -> bool:
        return os.path.isfile(os.path.join(pasta, "gfix.exe"))

    # 1. Portable Futura — gfix.exe direto na raiz da pasta
    portable_bases = [
        r"C:\FuturaFirebird\FB",
        r"C:\FuturaFirebird\FB4",
        r"C:\FuturaFirebird\Firebird",
        r"C:\FuturaFirebird\FB3",  # FB3 por ultimo
    ]
    for base in portable_bases:
        if _tem_gfix(base):
            return base

    # 2. Registro do Windows
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

    # 3. Pastas padrão de instalação
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
            capture_output=True,
            timeout=120,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )

        saida = (proc.stdout + proc.stderr).strip()
        resultado["executado"]   = True
        resultado["saida_bruta"] = saida

        if not saida:
            resultado["ok"] = True
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
            resultado["detalhes"].append(
                f"Paginas: {tamanho // page_size:,} (multiplo correto)"
            )

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
    """
    Lê o cabeçalho binário do .fdb, consulta BUILD_BD via fdb e
    opcionalmente roda gfix -validate.

    Retorna dict com:
        ok                  : bool
        ods_major           : int
        ods_minor           : int
        versao_arquivo      : str   — versão Firebird que criou o banco
        versao_instalada    : str   — versão Firebird instalada na máquina
        page_size           : int
        header_ok           : bool
        header_erros        : list[str]
        header_detalhes     : list[str]
        gfix_executado      : bool
        gfix_ok             : bool
        gfix_erros          : list[str]
        gfix_avisos         : list[str]
        gfix_saida_bruta    : str
        gfix_msg            : str
        build_bd            : int   — valor de SELECT BUILD_BD FROM PARAMETROS
        versao_futura       : str   — versão do sistema Futura (ex: 2026.02.09)
        versao_futura_est   : bool  — True se estimado, False se confirmado
        versao_futura_erro  : str   — erro ao consultar BUILD_BD (se houver)
        erro                : str   — erro geral (arquivo não encontrado, etc.)
    """
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
        "versao_futura":     "",
        "versao_futura_est": False,
        "versao_futura_erro": "",
        "erro":              "",
    }

    # -- Validações básicas --------------------------------------------------
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

    # -- Leitura do header binário -------------------------------------------
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

        # -- Consulta BUILD_BD e versão Futura -------------------------------
        build_bd, fdb_erro = _consultar_build_bd(path, user, password, ods_major)

        versao_futura     = ""
        versao_futura_est = False
        if build_bd:
            versao_futura, versao_futura_est = _build_para_versao_futura(build_bd)

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
            "build_bd":          build_bd or 0,
            "versao_futura":     versao_futura,
            "versao_futura_est": versao_futura_est,
            "versao_futura_erro": fdb_erro,
            "erro":              "",
        })

    except PermissionError:
        result["erro"] = "Sem permissao para ler o arquivo. Execute como Administrador."
    except Exception as e:
        result["erro"] = f"Erro ao ler arquivo: {e}"

    return result