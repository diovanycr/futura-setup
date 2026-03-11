# =============================================================================
# FUTURA SETUP — Core: Verificar Versão do Firebird via arquivo .fdb
# Mostra a versão pelo ODS do arquivo E a versão instalada na máquina.
# Salvar em: core/firebird_version_check.py
#
# Layout real do header (confirmado por leitura binária):
#   offset 16 : uint16 — page size
#   offset 20 : uint16 — ODS minor
#   offset 30 : uint16 — ODS major
# =============================================================================
from __future__ import annotations
import os
import re
import struct
import subprocess
import winreg

# Mapeamento ODS major → versão genérica (fallback)
_ODS_MAP: dict[int, str] = {
    8:  "Firebird 1.0",
    9:  "Firebird 1.5",
    10: "Interbase 6.x",
    11: "Firebird 2.x",
    12: "Firebird 3.0",
    13: "Firebird 4.0 / 5.0",
}

# ODS (major, minor) → versão exata
_ODS_MINOR_MAP: dict[tuple[int, int], str] = {
    (11, 0): "Firebird 2.0",
    (11, 1): "Firebird 2.1",
    (11, 2): "Firebird 2.5",
    (12, 0): "Firebird 3.0",
    (13, 0): "Firebird 4.0",
    (13, 1): "Firebird 4.0",
    (13, 2): "Firebird 4.0",
    (13, 3): "Firebird 4.0",
    (13, 4): "Firebird 4.0",
    (13, 5): "Firebird 5.0",
}

_PAGE_SIZE_OFFSET = 16
_ODS_MINOR_OFFSET = 20
_ODS_MAJOR_OFFSET = 30
_MIN_READ         = 32


# =============================================================================
# Detectar versão do Firebird instalado na máquina
# =============================================================================

def _versao_instalada() -> str:
    """
    Tenta detectar a versão do Firebird instalado na máquina via:
    1. Registro do Windows
    2. Executável fbserver.exe / fb_inet_server.exe
    Retorna string como "3.0.10.33601" ou "Não encontrado" se não achar.
    """

    # ── 1. Registro do Windows ─────────────────────────────────────────────
    chaves_registro = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Firebird Project\Firebird Server\Instances"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Firebird Project\Firebird Server\Instances"),
    ]
    fb_dir = None
    for hive, chave in chaves_registro:
        try:
            with winreg.OpenKey(hive, chave) as k:
                path, _ = winreg.QueryValueEx(k, "DefaultInstance")
                if path and os.path.isdir(path):
                    fb_dir = path
                    break
        except Exception:
            continue

    # ── 2. Fallback: pastas padrão ─────────────────────────────────────────
    if not fb_dir:
        candidatos = [
            r"C:\Program Files\Firebird\Firebird_3_0",
            r"C:\Program Files\Firebird\Firebird_4_0",
            r"C:\Program Files\Firebird\Firebird_5_0",
            r"C:\Program Files (x86)\Firebird\Firebird_3_0",
            r"C:\Program Files (x86)\Firebird\Firebird_4_0",
        ]
        for c in candidatos:
            if os.path.isdir(c):
                fb_dir = c
                break

    if not fb_dir:
        return "Não encontrado"

    # ── 3. Lê versão do executável ─────────────────────────────────────────
    exes = ["fbserver.exe", "fb_inet_server.exe", "firebird.exe", "fbguard.exe"]
    for exe in exes:
        exe_path = os.path.join(fb_dir, exe)
        if not os.path.isfile(exe_path):
            continue
        try:
            # Usa PowerShell para ler FileVersionInfo
            cmd = (
                f'(Get-Item "{exe_path}").VersionInfo.FileVersion'
            )
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", cmd],
                timeout=5, stderr=subprocess.DEVNULL
            ).decode(errors="ignore").strip()
            if out:
                return out
        except Exception:
            pass

        # Fallback: tenta rodar o exe com -z
        try:
            out = subprocess.check_output(
                [exe_path, "-z"],
                timeout=5, stderr=subprocess.STDOUT
            ).decode(errors="ignore")
            m = re.search(r"(\d+\.\d+\.\d+[\.\d]*)", out)
            if m:
                return m.group(1)
        except Exception:
            pass

    # ── 4. Versão aproximada pelo nome da pasta ────────────────────────────
    nome_pasta = os.path.basename(fb_dir).lower()
    if "3_0" in nome_pasta or "3.0" in nome_pasta:
        return "3.0 (pasta: " + os.path.basename(fb_dir) + ")"
    if "4_0" in nome_pasta or "4.0" in nome_pasta:
        return "4.0 (pasta: " + os.path.basename(fb_dir) + ")"
    if "5_0" in nome_pasta or "5.0" in nome_pasta:
        return "5.0 (pasta: " + os.path.basename(fb_dir) + ")"

    return f"Instalado em: {fb_dir} (versão não identificada)"


# =============================================================================
# Leitura do ODS do arquivo .fdb
# =============================================================================

def verificar_versao_fdb(path: str) -> dict:
    """
    Lê o cabeçalho binário do arquivo .fdb e retorna informações de versão.

    Retorna dict com:
        ok               : bool  — True se leitura bem-sucedida
        ods_major        : int   — ODS major version
        ods_minor        : int   — ODS minor version
        versao_arquivo   : str   — Versão do Firebird que criou o arquivo
        versao_instalada : str   — Versão do Firebird instalado na máquina
        page_size        : int   — Tamanho da página em bytes
        erro             : str   — Mensagem de erro (se ok=False)
    """
    result = {
        "ok": False,
        "ods_major": 0,
        "ods_minor": 0,
        "versao_arquivo": "",
        "versao_instalada": "",
        "page_size": 0,
        "erro": "",
    }

    if not path:
        result["erro"] = "Nenhum arquivo informado."
        return result

    if not os.path.isfile(path):
        result["erro"] = f"Arquivo não encontrado: {path}"
        return result

    ext = os.path.splitext(path)[1].lower()
    if ext not in (".fdb", ".gdb", ".db"):
        result["erro"] = f"Extensão não reconhecida: '{ext}'. Use .fdb, .gdb ou .db"
        return result

    try:
        with open(path, "rb") as f:
            data = f.read(128)

        if len(data) < _MIN_READ:
            result["erro"] = "Arquivo muito pequeno ou corrompido."
            return result

        page_size = struct.unpack_from("<H", data, _PAGE_SIZE_OFFSET)[0]
        ods_minor = struct.unpack_from("<H", data, _ODS_MINOR_OFFSET)[0]
        ods_major = struct.unpack_from("<H", data, _ODS_MAJOR_OFFSET)[0]

        valid_page_sizes = {1024, 2048, 4096, 8192, 16384, 32768}
        if page_size not in valid_page_sizes:
            result["erro"] = (
                f"Page size inválido ({page_size}). "
                "O arquivo pode não ser um banco Firebird válido."
            )
            return result

        if ods_major < 8 or ods_major > 20:
            result["erro"] = (
                f"ODS inválido ({ods_major}.{ods_minor}). "
                "O arquivo pode não ser um banco Firebird válido."
            )
            return result

        versao_arquivo = _ODS_MINOR_MAP.get(
            (ods_major, ods_minor),
            _ODS_MAP.get(ods_major, f"Desconhecido (ODS {ods_major}.{ods_minor})")
        )

        versao_instalada = _versao_instalada()

        result.update({
            "ok": True,
            "ods_major": ods_major,
            "ods_minor": ods_minor,
            "versao_arquivo": versao_arquivo,
            "versao_instalada": versao_instalada,
            "page_size": page_size,
            "erro": "",
        })

    except PermissionError:
        result["erro"] = "Sem permissão para ler o arquivo. Tente executar como Administrador."
    except Exception as e:
        result["erro"] = f"Erro ao ler arquivo: {e}"

    return result