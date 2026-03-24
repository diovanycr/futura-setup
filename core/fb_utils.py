# =============================================================================
# FUTURA SETUP — Core: Firebird Utilities
# Helpers para busca de executáveis e flags de estado
# =============================================================================
import os
import subprocess
import re
from config import FB_PORTABLE_CONFIGS

# Redefine para compatibilidade
FB_CONFIGS = FB_PORTABLE_CONFIGS

_SERVIDOR_CANDIDATOS = ["firebird.exe", "fbserver.exe"]
_INSTSVC_CANDIDATOS  = ["instsvc.exe"]
_SERVIDOR_SUBDIRS    = ["", "bin"]

def encontrar_exe(versao: str, nomes: list[str]) -> str | None:
    fb_dir = FB_CONFIGS[versao]["dir"]
    for subdir in _SERVIDOR_SUBDIRS:
        base = os.path.join(fb_dir, subdir) if subdir else fb_dir
        for nome in nomes:
            p = os.path.join(base, nome)
            if os.path.isfile(p):
                return p
    return None

def encontrar_servidor(versao: str) -> str | None:
    return encontrar_exe(versao, _SERVIDOR_CANDIDATOS)

def encontrar_instsvc(versao: str) -> str | None:
    return encontrar_exe(versao, _INSTSVC_CANDIDATOS)

def encontrar_gfix(versao: str) -> str | None:
    return encontrar_exe(versao, ["gfix.exe"])

def encontrar_gbak(versao: str) -> str | None:
    return encontrar_exe(versao, ["gbak.exe"])

def encontrar_isql(versao: str) -> str | None:
    return encontrar_exe(versao, ["isql.exe"])

def encontrar_gsec(versao: str) -> str | None:
    return encontrar_exe(versao, ["gsec.exe"])


def security_db_path(versao: str) -> str:
    cfg = FB_CONFIGS[versao]
    return os.path.join(cfg["dir"], cfg["security_db"])


def get_fb_versao_bin(versao_base: str) -> str:
    gbak = encontrar_gbak(versao_base)
    if not gbak:
        return ""
    try:
        out = subprocess.check_output(
            [gbak, "-z"], timeout=5, stderr=subprocess.STDOUT
        ).decode(errors="ignore")
        m = re.search(r"WI-V([\d.]+)", out)
        return m.group(1) if m else f"{versao_base}.x"
    except Exception:
        return f"{versao_base}.x"

def flag_habilitado_path(versao: str) -> str:
    return os.path.join(FB_CONFIGS[versao]["dir"], f".fb{versao}_habilitado")

def ler_flag_habilitado(versao: str) -> bool:
    try:
        path = flag_habilitado_path(versao)
        if os.path.isfile(path):
            return open(path).read().strip() == "1"
    except Exception:
        pass
    return True

def salvar_flag_habilitado(versao: str, habilitado: bool):
    try:
        path = flag_habilitado_path(versao)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("1" if habilitado else "0")
    except Exception:
        pass


def fb_portable_instalado(versao: str) -> bool:
    """Retorna True se o executável principal do servidor existir."""
    return encontrar_servidor(versao) is not None


def diagnosticar_instalacao(versao: str) -> dict:
    """Verifica quais executáveis essenciais estão presentes."""
    arquivos = []
    exes = ["firebird.exe", "fbserver.exe", "instsvc.exe", "gfix.exe", "gbak.exe", "isql.exe", "gsec.exe"]
    for e in exes:
        if encontrar_exe(versao, [e]):
            arquivos.append(e)
    
    return {
        "ok": len(arquivos) > 0,
        "arquivos": arquivos,
        "servidor": encontrar_servidor(versao),
        "instsvc": encontrar_instsvc(versao)
    }
