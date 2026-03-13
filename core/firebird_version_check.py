# =============================================================================
# FUTURA SETUP — Core: Verificar Versão + Integridade do Firebird via .fdb
# Salvar em: core/firebird_version_check.py
#
# Layout real do header confirmado por análise binária:
#   offset 16 : uint16 LE — page size         (ex: 16384)
#   offset 18 : byte baixo — ODS major         (ex: 0x0c = 12 = FB3)
#   offset 20 : byte baixo — ODS minor         (ex: 0x03 = 3)
# =============================================================================
from __future__ import annotations
import os
import re
import struct
import subprocess
import winreg

# Mapeamento ODS major ? versão genérica (fallback)
_ODS_MAP: dict[int, str] = {
    8:  "Firebird 1.0",
    9:  "Firebird 1.5",
    10: "Interbase 6.x",
    11: "Firebird 2.x",
    12: "Firebird 3.0",
    13: "Firebird 4.0 / 5.0",
}

# ODS (major, minor) ? versão exata
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
# Detectar instalação do Firebird
# =============================================================================

def _encontrar_fb_dir() -> str | None:
    """Retorna o diretório de instalação do Firebird ou None."""
    # 1. Registro do Windows
    chaves = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Firebird Project\Firebird Server\Instances"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Firebird Project\Firebird Server\Instances"),
    ]
    for hive, chave in chaves:
        try:
            with winreg.OpenKey(hive, chave) as k:
                path, _ = winreg.QueryValueEx(k, "DefaultInstance")
                if path and os.path.isdir(path):
                    return path
        except Exception:
            continue

    # 2. Pastas padrão
    candidatos = [
        r"C:\Program Files\Firebird\Firebird_3_0",
        r"C:\Program Files\Firebird\Firebird_4_0",
        r"C:\Program Files\Firebird\Firebird_5_0",
        r"C:\Program Files (x86)\Firebird\Firebird_3_0",
        r"C:\Program Files (x86)\Firebird\Firebird_4_0",
    ]
    for c in candidatos:
        if os.path.isdir(c):
            return c

    return None


def _versao_instalada() -> str:
    fb_dir = _encontrar_fb_dir()
    if not fb_dir:
        return "Nao encontrado"

    # Lê versão via gbak -z
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

    # PowerShell FileVersionInfo
    for exe in ["fbserver.exe", "fb_inet_server.exe", "firebird.exe"]:
        exe_path = os.path.join(fb_dir, exe)
        if not os.path.isfile(exe_path):
            continue
        try:
            cmd = f'(Get-Item "{exe_path}").VersionInfo.FileVersion'
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", cmd],
                timeout=5, stderr=subprocess.DEVNULL
            ).decode(errors="ignore").strip()
            if out:
                return out
        except Exception:
            pass

    # Fallback pelo nome da pasta
    nome = os.path.basename(fb_dir).lower()
    for v in ["3_0", "4_0", "5_0"]:
        if v in nome:
            return f"{v.replace('_', '.')} (pasta: {os.path.basename(fb_dir)})"

    return f"Instalado em: {fb_dir}"


# =============================================================================
# Validação real via gfix
# =============================================================================

def _validar_com_gfix(path: str, user: str, password: str) -> dict:
    """
    Roda gfix -validate -full no arquivo e retorna o resultado.

    Retorna dict com:
        executado   : bool       — True se gfix foi encontrado e rodou
        ok          : bool       — True se sem erros
        erros       : list[str]  — Linhas de erro reportadas pelo gfix
        avisos      : list[str]  — Linhas de aviso
        saida_bruta : str        — Saída completa do gfix
        msg         : str        — Mensagem caso gfix não seja encontrado
    """
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
            [
                gfix,
                "-validate", "-full",
                "-user",     user,
                "-password", password,
                path,
            ],
            capture_output=True,
            timeout=120,  # bancos grandes podem demorar
            text=True,
            encoding="utf-8",
            errors="ignore",
        )

        saida = (proc.stdout + proc.stderr).strip()
        resultado["executado"]   = True
        resultado["saida_bruta"] = saida

        if not saida:
            # gfix sem saída = banco ok
            resultado["ok"] = True
            return resultado

        linhas = saida.splitlines()
        for linha in linhas:
            l = linha.strip()
            if not l:
                continue
            ll = l.lower()
            if any(k in ll for k in ["error", "corrupt", "wrong", "bad", "invalid", "damaged"]):
                resultado["erros"].append(l)
            elif any(k in ll for k in ["warning", "warn"]):
                resultado["avisos"].append(l)
            # linhas informativas são ignoradas (ex: "Validating database...")

        resultado["ok"] = len(resultado["erros"]) == 0

    except subprocess.TimeoutExpired:
        resultado["executado"]   = True
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
    """Verificações rápidas sem precisar do Firebird instalado."""
    resultado = {"ok": True, "erros": [], "detalhes": []}
    try:
        tamanho = os.path.getsize(path)

        if tamanho == 0:
            resultado["erros"].append("Arquivo vazio (0 bytes).")
            resultado["ok"] = False
            return resultado

        resultado["detalhes"].append(f"Tamanho: {tamanho / (1024*1024):.1f} MB")

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
    user: str = "SYSDBA",
    password: str = "sbofutura",
    rodar_gfix: bool = True,
) -> dict:
    """
    Lê o cabeçalho binário do .fdb e opcionalmente roda gfix -validate.

    Retorna dict com:
        ok                  : bool
        ods_major           : int
        ods_minor           : int
        versao_arquivo      : str
        versao_instalada    : str
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
        erro                : str
    """
    result = {
        "ok": False,
        "ods_major": 0,
        "ods_minor": 0,
        "versao_arquivo": "",
        "versao_instalada": "",
        "page_size": 0,
        "header_ok":       True,
        "header_erros":    [],
        "header_detalhes": [],
        "gfix_executado":  False,
        "gfix_ok":         False,
        "gfix_erros":      [],
        "gfix_avisos":     [],
        "gfix_saida_bruta": "",
        "gfix_msg":        "",
        "erro": "",
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

        result.update({
            "ok":               True,
            "ods_major":        ods_major,
            "ods_minor":        ods_minor,
            "versao_arquivo":   versao_arquivo,
            "versao_instalada": versao_instalada,
            "page_size":        page_size,
            "header_ok":        header["ok"],
            "header_erros":     header["erros"],
            "header_detalhes":  header["detalhes"],
            "gfix_executado":   gfix["executado"],
            "gfix_ok":          gfix["ok"],
            "gfix_erros":       gfix["erros"],
            "gfix_avisos":      gfix["avisos"],
            "gfix_saida_bruta": gfix["saida_bruta"],
            "gfix_msg":         gfix["msg"],
            "erro":             "",
        })

    except PermissionError:
        result["erro"] = "Sem permissao para ler o arquivo. Execute como Administrador."
    except Exception as e:
        result["erro"] = f"Erro ao ler arquivo: {e}"

    return result