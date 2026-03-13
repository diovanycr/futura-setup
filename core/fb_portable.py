# =============================================================================
# FUTURA SETUP — Core: Firebird Portable Manager
#
# FB3 → processo portable (porta 3050) OU serviço Windows registrado
# FB4 → processo portable (porta 3051) OU serviço Windows registrado
#
# Ambas as versões funcionam de forma simétrica:
#   - Instalação via download do zip do GitHub
#   - Modo processo: inicia fbserver.exe/firebird.exe diretamente
#   - Modo serviço:  registra como serviço Windows (start=auto)
#
# Salvar em: core/fb_portable.py
# =============================================================================
from __future__ import annotations
import ctypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from typing import Callable

# =============================================================================
# Privilégios de administrador
# =============================================================================

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def solicitar_admin() -> bool:
    if is_admin():
        return False
    try:
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            " ".join(f'"{a}"' for a in sys.argv),
            None, 1
        )
        return int(ret) > 32
    except Exception:
        return False


# =============================================================================
# Configurações por versão
# =============================================================================

FB_CONFIGS = {
    "3": {
        "dir":          r"C:\FuturaFirebird\FB3",
        "zip_url":      (
            "https://github.com/FirebirdSQL/firebird/releases/download/"
            "v3.0.13/Firebird-3.0.13.33818-0-x64.zip"
        ),
        "zip_size":     17 * 1024 * 1024,
        "porta":        3050,
        "label":        "Firebird 3 Portable",
        # Serviços do instalador oficial do Windows (detecção/convivência)
        "servicos_win_oficiais": [
            "FirebirdServerDefaultInstance",
            "FirebirdGuardianDefaultInstance",
            "FirebirdServer",
            "Firebird",
        ],
        # Nome do serviço registrado pelo Futura Setup
        "servico_nome": "FuturaFirebirdFB3",
    },
    "4": {
        "dir":          r"C:\FuturaFirebird\FB4",
        "zip_url":      (
            "https://github.com/FirebirdSQL/firebird/releases/download/"
            "v4.0.6/Firebird-4.0.6.3221-0-x64.zip"
        ),
        "zip_size":     23 * 1024 * 1024,
        "porta":        3051,
        "label":        "Firebird 4 Portable",
        "servicos_win_oficiais": [],
        "servico_nome": "FuturaFirebirdFB4",
    },
}

# Atalhos legado
FB4_DIR  = FB_CONFIGS["4"]["dir"]
FB4_GFIX = os.path.join(FB4_DIR, "gfix.exe")
FB4_GBAK = os.path.join(FB4_DIR, "gbak.exe")
FB4_ISQL = os.path.join(FB4_DIR, "isql.exe")

# Handles globais dos processos em modo portable
_processos: dict[str, subprocess.Popen | None] = {"3": None, "4": None}

_SERVIDOR_CANDIDATOS = ["firebird.exe", "fbserver.exe"]
_INSTSVC_CANDIDATOS  = ["instsvc.exe"]
_SERVIDOR_SUBDIRS    = ["", "bin"]


# =============================================================================
# Busca de executáveis
# =============================================================================

def _encontrar_exe(versao: str, nomes: list[str]) -> str | None:
    fb_dir = FB_CONFIGS[versao]["dir"]
    for subdir in _SERVIDOR_SUBDIRS:
        base = os.path.join(fb_dir, subdir) if subdir else fb_dir
        for nome in nomes:
            p = os.path.join(base, nome)
            if os.path.isfile(p):
                return p
    return None


def _encontrar_servidor(versao: str) -> str | None:
    return _encontrar_exe(versao, _SERVIDOR_CANDIDATOS)


def _encontrar_instsvc(versao: str) -> str | None:
    """Localiza instsvc.exe — utilitário oficial do Firebird para gerenciar serviço Windows."""
    return _encontrar_exe(versao, _INSTSVC_CANDIDATOS)


def _encontrar_gfix(versao: str) -> str | None:
    return _encontrar_exe(versao, ["gfix.exe"])


def _encontrar_gbak(versao: str) -> str | None:
    return _encontrar_exe(versao, ["gbak.exe"])


def diagnosticar_instalacao(versao: str = "4") -> dict:
    fb_dir = FB_CONFIGS[versao]["dir"]
    resultado = {
        "dir":      fb_dir,
        "dir_ok":   os.path.isdir(fb_dir),
        "servidor": _encontrar_servidor(versao),
        "gfix":     _encontrar_gfix(versao),
        "gbak":     _encontrar_gbak(versao),
        "arquivos": [],
    }
    if resultado["dir_ok"]:
        try:
            for raiz, _dirs, arqs in os.walk(fb_dir):
                for arq in arqs:
                    if arq.lower().endswith(".exe"):
                        resultado["arquivos"].append(
                            os.path.join(raiz, arq).replace(fb_dir, "").lstrip("\\")
                        )
        except Exception:
            pass
    return resultado


# =============================================================================
# Verificação de instalação
# =============================================================================

def fb_portable_instalado(versao: str = "4") -> bool:
    return _encontrar_gfix(versao) is not None


def fb4_portable_instalado() -> bool:
    return fb_portable_instalado("4")


def fb3_portable_instalado() -> bool:
    return fb_portable_instalado("3")


def versao_fb_portable(versao: str = "4") -> str:
    gbak = _encontrar_gbak(versao)
    if not gbak:
        return ""
    try:
        out = subprocess.check_output(
            [gbak, "-z"], timeout=5, stderr=subprocess.STDOUT
        ).decode(errors="ignore")
        m = re.search(r"WI-V([\d.]+)", out)
        return m.group(1) if m else f"{versao}.x"
    except Exception:
        return f"{versao}.x"


def versao_fb4_portable() -> str:
    return versao_fb_portable("4")


def versao_fb3_portable() -> str:
    return versao_fb_portable("3")


# =============================================================================
# Serviço Windows — utilitários genéricos
# =============================================================================

def _servico_existe(nome: str) -> bool:
    try:
        r = subprocess.run(["sc", "query", nome],
                           capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _servico_rodando(nome: str) -> bool:
    try:
        r = subprocess.run(["sc", "query", nome],
                           capture_output=True, text=True, timeout=5)
        return "RUNNING" in r.stdout
    except Exception:
        return False


def _servico_desabilitado(nome: str) -> bool:
    try:
        r = subprocess.run(["sc", "qc", nome],
                           capture_output=True, text=True, timeout=5)
        return "DISABLED" in r.stdout.upper()
    except Exception:
        return False


def _servico_iniciar(nome: str, log_fn=None, timeout_s: int = 45) -> bool:
    def log(m):
        if log_fn: log_fn(m)
    try:
        r = subprocess.run(
            ["net", "start", nome],
            capture_output=True, text=True,
            encoding="utf-8", errors="ignore",
            timeout=timeout_s,
        )
        saida = (r.stdout + r.stderr).strip()
        if saida:
            log(f"  net start: {saida[:400]}")
        for _ in range(20):
            time.sleep(1)
            if _servico_rodando(nome):
                return True
        # Serviço não subiu — pega estado atual e últimas entradas do Event Log
        try:
            sq = subprocess.run(["sc", "query", nome],
                                capture_output=True, text=True, timeout=5)
            log(f"  sc query: {sq.stdout.strip()[:300]}")
        except Exception:
            pass
        try:
            ev = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Get-EventLog -LogName System -Source '*Firebird*','*Service*' "
                 f"-Newest 5 -ErrorAction SilentlyContinue | "
                 f"Select-Object TimeGenerated,EntryType,Message | "
                 f"Format-List"],
                capture_output=True, text=True,
                encoding="utf-8", errors="ignore", timeout=10,
            )
            if ev.stdout.strip():
                log(f"  EventLog:\n{ev.stdout.strip()[:600]}")
        except Exception:
            pass
    except subprocess.TimeoutExpired:
        log(f"  net start timeout ({timeout_s}s) — servico pode estar travado na inicializacao.")
    except Exception as e:
        log(f"Erro ao iniciar servico '{nome}': {e}")
    return False


def _servico_parar(nome: str, log_fn=None, timeout_s: int = 30) -> bool:
    def log(m):
        if log_fn: log_fn(m)
    try:
        subprocess.run(["net", "stop", nome], capture_output=True, timeout=timeout_s)
        for _ in range(20):
            time.sleep(1)
            if not _servico_rodando(nome):
                return True
    except Exception as e:
        log(f"Erro ao parar servico '{nome}': {e}")
    return False


# =============================================================================
# Serviço oficial do instalador Windows — FB3 (detecção e convivência)
# =============================================================================

def _nome_servico_oficial_fb3() -> str | None:
    for nome in FB_CONFIGS["3"]["servicos_win_oficiais"]:
        if _servico_existe(nome):
            return nome
    return None


def fb3_servico_oficial_rodando() -> bool:
    nome = _nome_servico_oficial_fb3()
    return _servico_rodando(nome) if nome else False


# =============================================================================
# Modo de execução (processo | serviço) — genérico FB3 e FB4
# =============================================================================

def _modo_path(versao: str) -> str:
    return os.path.join(FB_CONFIGS[versao]["dir"], f".fb{versao}_modo")


def fb_obter_modo(versao: str) -> str:
    """Retorna 'processo' (padrão) ou 'servico'."""
    nome_svc = FB_CONFIGS[versao]["servico_nome"]
    if _servico_existe(nome_svc):
        return "servico"
    try:
        path = _modo_path(versao)
        if os.path.isfile(path):
            val = open(path).read().strip()
            if val in ("processo", "servico"):
                return val
    except Exception:
        pass
    return "processo"


def _fb_salvar_modo(versao: str, modo: str):
    try:
        with open(_modo_path(versao), "w") as f:
            f.write(modo)
    except Exception:
        pass


# =============================================================================
# Flag habilitado/desabilitado (modo processo)
# =============================================================================

def _flag_path(versao: str) -> str:
    return os.path.join(FB_CONFIGS[versao]["dir"], f".fb{versao}_habilitado")


def _ler_flag(versao: str) -> bool:
    try:
        path = _flag_path(versao)
        if os.path.isfile(path):
            return open(path).read().strip() == "1"
    except Exception:
        pass
    return True


def _salvar_flag(versao: str, habilitado: bool):
    try:
        with open(_flag_path(versao), "w") as f:
            f.write("1" if habilitado else "0")
    except Exception:
        pass


# =============================================================================
# Serviço Windows Futura — genérico FB3 e FB4
# =============================================================================

def fb_servico_existe(versao: str) -> bool:
    return _servico_existe(FB_CONFIGS[versao]["servico_nome"])


def fb_servico_rodando(versao: str) -> bool:
    return _servico_rodando(FB_CONFIGS[versao]["servico_nome"])


def registrar_fb_servico(versao: str, log_fn=None) -> dict:
    """
    Registra o Firebird portable como serviço Windows (start=auto).
    Requer privilégios de administrador.
    """
    def log(m):
        if log_fn: log_fn(m)

    if not is_admin():
        msg = "Permissao de administrador necessaria para registrar servicos Windows."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg, "requer_admin": True}

    if not fb_portable_instalado(versao):
        msg = f"FB{versao} Portable nao esta instalado. Instale-o primeiro."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg}

    servidor = _encontrar_servidor(versao)
    if not servidor:
        msg = f"Executavel do servidor FB{versao} nao encontrado."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg}

    cfg     = FB_CONFIGS[versao]
    nome    = cfg["servico_nome"]
    label_v = cfg["label"]

    # Parar processo portable se estiver rodando
    if _processo_rodando(versao):
        log(f"Parando processo portable do FB{versao} antes de registrar servico ...")
        _parar_processo(versao, log_fn)

    # Para FB3: parar serviço oficial se estiver rodando (conflito de porta)
    if versao == "3":
        nome_oficial = _nome_servico_oficial_fb3()
        if nome_oficial and _servico_rodando(nome_oficial):
            log(f"Parando servico oficial do FB3 ('{nome_oficial}') para evitar conflito de porta ...")
            _servico_parar(nome_oficial, log_fn)

    # Remover serviço Futura anterior se existir
    if _servico_existe(nome):
        log(f"Servico '{nome}' ja existe — recriando ...")
        _remover_servico_interno(versao, log_fn)

    log(f"Registrando servico '{nome}' ({label_v}) ...")
    log(f"  Executavel: {servidor}")
    fb_dir = os.path.dirname(servidor)

    try:
        registrado = False

        # ── Estratégia 1: instsvc.exe (utilitário oficial do Firebird) ──────────
        # instsvc install [-auto] [-n NomeServico] [-p Porta]
        instsvc = _encontrar_instsvc(versao)
        if instsvc:
            log(f"  Usando instsvc.exe: {instsvc}")
            porta = str(cfg["porta"])
            r = subprocess.run(
                [instsvc, "install", "-auto", "-n", nome, "-p", porta],
                capture_output=True, text=True,
                encoding="utf-8", errors="ignore",
                timeout=30, cwd=fb_dir,
            )
            saida = (r.stdout + r.stderr).strip()
            if saida:
                log(f"    instsvc: {saida[:300]}")
            if _servico_existe(nome):
                registrado = True
                log("  Registrado via instsvc.exe.")
            else:
                # Tenta sem -n (cria com nome padrão do Firebird)
                r2 = subprocess.run(
                    [instsvc, "install", "-auto", "-p", porta],
                    capture_output=True, text=True,
                    encoding="utf-8", errors="ignore",
                    timeout=30, cwd=fb_dir,
                )
                saida2 = (r2.stdout + r2.stderr).strip()
                if saida2:
                    log(f"    instsvc (sem -n): {saida2[:300]}")
                # Detecta nome criado
                for candidato in [nome, "DefaultInstance",
                                   "FirebirdDefaultInstance",
                                   "FirebirdServerDefaultInstance", "Firebird"]:
                    if _servico_existe(candidato):
                        if candidato != nome:
                            log(f"  Servico criado como '{candidato}'.")
                            FB_CONFIGS[versao]["servico_nome"] = candidato
                            nome = candidato
                        registrado = True
                        log("  Registrado via instsvc.exe (nome padrao).")
                        break
        else:
            log("  instsvc.exe nao encontrado no diretorio do Firebird.")

        # ── Estratégia 2: sc create com binPath apontando para fbserver.exe ──────
        # Usa fbserver.exe que SIM aceita rodar como serviço Windows nativo,
        # diferente de firebird.exe (que é o app de console/modo processo).
        if not registrado:
            fbserver = _encontrar_exe(versao, ["fbserver.exe"])
            exe_svc  = fbserver if fbserver else servidor
            log(f"  sc create com: {exe_svc}")
            r3 = subprocess.run(
                [
                    "sc", "create", nome,
                    "binPath=", f'"{exe_svc}" -s',
                    "DisplayName=", f"Futura {label_v}",
                    "start=", "auto",
                    "type=", "own",
                ],
                capture_output=True, text=True,
                encoding="utf-8", errors="ignore", timeout=15,
            )
            saida3 = (r3.stdout + r3.stderr).strip()
            if saida3:
                log(f"  sc create: {saida3[:300]}")
            if r3.returncode == 0 and _servico_existe(nome):
                registrado = True
                log("  Registrado via sc create.")
            else:
                return {"ok": False, "erro": (
                    f"Nao foi possivel registrar o servico. "
                    f"instsvc.exe {'nao encontrado' if not instsvc else 'falhou'}. "
                    f"sc create: {saida3}"
                )}

        if not _servico_existe(nome):
            return {"ok": False, "erro": "Servico nao foi criado. Verifique o log."}

        # Garante start=auto, descrição e recovery
        subprocess.run(["sc", "config", nome, "start=", "auto"],
                       capture_output=True, timeout=10)
        subprocess.run(
            ["sc", "description", nome,
             f"Firebird {versao} Portable gerenciado pelo Futura Setup"],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["sc", "failure", nome, "reset=", "86400",
             "actions=", "restart/5000/restart/10000//0"],
            capture_output=True, timeout=10,
        )

        _fb_salvar_modo(versao, "servico")
        log(f"Servico '{nome}' registrado com sucesso (start=auto, porta {cfg['porta']}).")
        return {"ok": True, "erro": ""}

    except Exception as e:
        log(f"Erro: {e}")
        return {"ok": False, "erro": str(e)}


def _remover_servico_interno(versao: str, log_fn=None) -> bool:
    """Remove o serviço Windows Futura da versão. Uso interno."""
    def log(m):
        if log_fn: log_fn(m)

    nome = FB_CONFIGS[versao]["servico_nome"]

    if _servico_rodando(nome):
        subprocess.run(["net", "stop", nome], capture_output=True, timeout=30)
        time.sleep(2)

    # Tenta instsvc remove primeiro (mais limpo)
    instsvc = _encontrar_instsvc(versao)
    if instsvc and _servico_existe(nome):
        r = subprocess.run(
            [instsvc, "remove", "-n", nome],
            capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=15,
            cwd=os.path.dirname(instsvc),
        )
        saida = (r.stdout + r.stderr).strip()
        if saida:
            log(f"  instsvc remove: {saida[:200]}")
        if not _servico_existe(nome):
            log(f"Servico '{nome}' removido via instsvc.")
            time.sleep(1)
            return True

    # Fallback: sc delete
    if not _servico_existe(nome):
        return True
    r2 = subprocess.run(["sc", "delete", nome],
                        capture_output=True, text=True, timeout=15)
    if r2.returncode == 0:
        log(f"Servico '{nome}' removido.")
        time.sleep(1)
        return True
    else:
        log(f"AVISO ao remover servico: {(r2.stdout + r2.stderr).strip()}")
        return False


def remover_fb_servico(versao: str, log_fn=None) -> dict:
    """
    Remove o registro do serviço Windows Futura da versão.
    Volta ao modo processo portable.
    Requer privilégios de administrador.
    """
    def log(m):
        if log_fn: log_fn(m)

    if not is_admin():
        msg = "Permissao de administrador necessaria."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg, "requer_admin": True}

    nome = FB_CONFIGS[versao]["servico_nome"]
    if not _servico_existe(nome):
        log("Servico nao estava registrado.")
        _fb_salvar_modo(versao, "processo")
        return {"ok": True, "erro": ""}

    log(f"Removendo servico '{nome}' ...")
    ok = _remover_servico_interno(versao, log_fn)
    if ok:
        _fb_salvar_modo(versao, "processo")
        log(f"FB{versao} voltou ao modo processo portable.")
        return {"ok": True, "erro": ""}
    return {"ok": False, "erro": f"Nao foi possivel remover o servico '{nome}'."}


def ativar_fb_servico(versao: str, log_fn=None) -> dict:
    """
    Inicia o serviço Windows Futura da versão.
    Se não estiver registrado, registra e inicia.
    Requer privilégios de administrador.
    """
    def log(m):
        if log_fn: log_fn(m)

    if not is_admin():
        msg = "Permissao de administrador necessaria."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg, "requer_admin": True}

    # Lê o nome após possível alteração por registrar_fb_servico
    nome = FB_CONFIGS[versao]["servico_nome"]

    if not _servico_existe(nome):
        log("Servico nao registrado — registrando agora ...")
        r = registrar_fb_servico(versao, log_fn)
        if not r["ok"]:
            return r
        # Re-lê nome pois registrar pode ter ajustado FB_CONFIGS
        nome = FB_CONFIGS[versao]["servico_nome"]

    if _servico_desabilitado(nome):
        log(f"Habilitando servico '{nome}' ...")
        subprocess.run(["sc", "config", nome, "start=", "auto"],
                       capture_output=True, timeout=10)

    if _servico_rodando(nome):
        log(f"Servico '{nome}' ja esta rodando.")
        return {"ok": True, "erro": ""}

    log(f"Iniciando servico '{nome}' ...")
    if _servico_iniciar(nome, log_fn, timeout_s=45):
        log(f"Firebird {versao} ativado como servico Windows (porta {FB_CONFIGS[versao]['porta']}).")
        return {"ok": True, "erro": ""}
    msg = f"Servico '{nome}' nao subiu no tempo esperado."
    log(f"AVISO: {msg}")
    return {"ok": False, "erro": msg}


def inativar_fb_servico(versao: str, log_fn=None) -> dict:
    """
    Para o serviço Windows Futura da versão (mantém registrado, apenas para).
    Requer privilégios de administrador.
    """
    def log(m):
        if log_fn: log_fn(m)

    if not is_admin():
        msg = "Permissao de administrador necessaria."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg, "requer_admin": True}

    nome = FB_CONFIGS[versao]["servico_nome"]
    if not _servico_existe(nome):
        log("Servico nao estava registrado.")
        return {"ok": True, "erro": ""}

    if not _servico_rodando(nome):
        log(f"Servico '{nome}' ja estava parado.")
        return {"ok": True, "erro": ""}

    log(f"Parando servico '{nome}' ...")
    if _servico_parar(nome, log_fn):
        log("Servico parado com sucesso.")
        return {"ok": True, "erro": ""}
    msg = f"Servico '{nome}' nao parou no tempo esperado."
    log(f"AVISO: {msg}")
    return {"ok": False, "erro": msg}


# Atalhos nomeados por versão
def registrar_fb3_servico(log_fn=None) -> dict: return registrar_fb_servico("3", log_fn)
def registrar_fb4_servico(log_fn=None) -> dict: return registrar_fb_servico("4", log_fn)
def remover_fb3_servico(log_fn=None)   -> dict: return remover_fb_servico("3", log_fn)
def remover_fb4_servico(log_fn=None)   -> dict: return remover_fb_servico("4", log_fn)
def fb3_servico_existe()  -> bool: return fb_servico_existe("3")
def fb4_servico_existe()  -> bool: return fb_servico_existe("4")
def fb3_servico_rodando() -> bool: return fb_servico_rodando("3")
def fb4_servico_rodando() -> bool: return fb_servico_rodando("4")
def fb3_obter_modo()      -> str:  return fb_obter_modo("3")
def fb4_obter_modo()      -> str:  return fb_obter_modo("4")


# =============================================================================
# Processo portable — genérico FB3 e FB4
# =============================================================================

def _processo_rodando(versao: str) -> bool:
    proc = _processos.get(versao)
    if proc is not None and proc.poll() is None:
        return True
    fb_dir = FB_CONFIGS[versao]["dir"].lower()
    for nome_exe in _SERVIDOR_CANDIDATOS:
        try:
            r = subprocess.run(
                ["wmic", "process", "where", f"name='{nome_exe}'",
                 "get", "ExecutablePath", "/FORMAT:CSV"],
                capture_output=True, text=True, timeout=8
            )
            for linha in r.stdout.lower().splitlines():
                if fb_dir in linha:
                    return True
        except Exception:
            pass
    return False


def _parar_processo(versao: str, log_fn=None):
    def log(m):
        if log_fn: log_fn(m)

    proc = _processos.get(versao)
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=8)
            _processos[versao] = None
            log(f"Processo portable FB{versao} encerrado.")
        except Exception:
            pass

    if _processo_rodando(versao):
        fb_dir = FB_CONFIGS[versao]["dir"].replace("\\", "\\\\")
        for nome_exe in _SERVIDOR_CANDIDATOS:
            try:
                subprocess.run(
                    ["wmic", "process", "where",
                     f"ExecutablePath like '%{fb_dir}%' and name='{nome_exe}'",
                     "delete"],
                    capture_output=True, timeout=10
                )
            except Exception:
                pass
        time.sleep(2)
        _processos[versao] = None


def fb_habilitado(versao: str) -> bool:
    if _processo_rodando(versao):
        return True
    if fb_servico_existe(versao):
        return not _servico_desabilitado(FB_CONFIGS[versao]["servico_nome"])
    return _ler_flag(versao)


# =============================================================================
# Ativar / Inativar — genérico FB3 e FB4
# =============================================================================

def ativar_fb(versao: str, log_fn=None) -> dict:
    """
    Ativa o Firebird da versão indicada.
    Detecta automaticamente o modo (processo | serviço).
    """
    def log(m):
        if log_fn: log_fn(m)

    modo = fb_obter_modo(versao)
    if modo == "servico":
        log(f"Modo servico Windows detectado para FB{versao}.")
        return ativar_fb_servico(versao, log_fn)

    # ── Modo processo portable ──────────────────────────────────────────────
    if not fb_portable_instalado(versao):
        msg = f"FB{versao} Portable nao esta instalado. Instale-o primeiro."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg}

    servidor = _encontrar_servidor(versao)
    if servidor is None:
        diag = diagnosticar_instalacao(versao)
        exes = ", ".join(diag["arquivos"]) if diag["arquivos"] else "nenhum"
        msg  = f"Executavel do servidor nao encontrado. EXEs presentes: [{exes}]."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg}

    _salvar_flag(versao, True)
    log(f"Firebird {versao} Portable habilitado (modo processo).")

    if _processo_rodando(versao):
        log(f"Firebird {versao} Portable ja esta ativo (porta {FB_CONFIGS[versao]['porta']}).")
        return {"ok": True, "erro": ""}

    porta = FB_CONFIGS[versao]["porta"]
    log(f"Iniciando processo fbserver FB{versao} (porta {porta}) ...")
    log(f"Servidor: {servidor}")
    try:
        proc = subprocess.Popen(
            [servidor, "-a"],
            cwd=os.path.dirname(servidor),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        _processos[versao] = proc
        for _ in range(10):
            time.sleep(1)
            if proc.poll() is not None:
                saida = ""
                try:
                    saida = proc.stdout.read().decode(errors="ignore")
                except Exception:
                    pass
                log(f"ERRO: servidor encerrou inesperadamente.\n{saida}")
                _processos[versao] = None
                return {"ok": False, "erro": "Servidor encerrou inesperadamente. Veja o log."}
            if _processo_rodando(versao):
                log(f"Firebird {versao} Portable ativado com sucesso (porta {porta}).")
                return {"ok": True, "erro": ""}

        msg = f"FB{versao} pode nao ter subido completamente."
        log(f"AVISO: {msg}")
        ok = _processos[versao] is not None
        return {"ok": ok, "erro": "" if ok else msg}
    except Exception as e:
        log(f"Erro: {e}")
        _processos[versao] = None
        return {"ok": False, "erro": str(e)}


def inativar_fb(versao: str, log_fn=None) -> dict:
    """
    Inativa o Firebird da versão indicada.
    Detecta automaticamente o modo (processo | serviço).
    """
    def log(m):
        if log_fn: log_fn(m)

    modo = fb_obter_modo(versao)
    if modo == "servico":
        log(f"Modo servico Windows detectado para FB{versao}.")
        return inativar_fb_servico(versao, log_fn)

    # ── Modo processo portable ──────────────────────────────────────────────
    if _processo_rodando(versao):
        log(f"Parando processo Firebird {versao} Portable ...")
        _parar_processo(versao, log_fn)
        if _processo_rodando(versao):
            msg = f"Nao foi possivel confirmar a parada do processo FB{versao}."
            log(f"AVISO: {msg}")
            return {"ok": False, "erro": msg}
        log("Processo parado com sucesso.")
    else:
        log(f"Processo Firebird {versao} Portable ja estava parado.")

    _salvar_flag(versao, False)
    log(f"Firebird {versao} Portable desabilitado e inativado com sucesso.")
    return {"ok": True, "erro": ""}


# Atalhos por versão (compatibilidade)
def ativar_fb3(log_fn=None)   -> dict: return ativar_fb("3", log_fn)
def inativar_fb3(log_fn=None) -> dict: return inativar_fb("3", log_fn)
def ativar_fb4(log_fn=None)   -> dict: return ativar_fb("4", log_fn)
def inativar_fb4(log_fn=None) -> dict: return inativar_fb("4", log_fn)


# =============================================================================
# Status consolidado
# =============================================================================

def status_detalhado() -> dict:
    st = {}
    for v in ("3", "4"):
        cfg        = FB_CONFIGS[v]
        inst       = fb_portable_instalado(v)
        modo       = fb_obter_modo(v) if inst else "processo"
        svc_nome   = cfg["servico_nome"]
        svc_reg    = fb_servico_existe(v)
        svc_rod    = _servico_rodando(svc_nome) if svc_reg else False
        proc_rod   = _processo_rodando(v)
        rodando    = svc_rod or proc_rod
        habilitado = fb_habilitado(v) if inst else False

        svc_oficial     = None
        svc_oficial_rod = False
        if v == "3":
            svc_oficial     = _nome_servico_oficial_fb3()
            svc_oficial_rod = _servico_rodando(svc_oficial) if svc_oficial else False
            if svc_oficial_rod:
                rodando    = True
                habilitado = True

        st[v] = {
            "instalado":           inst,
            "modo":                modo,
            "servico_nome":        svc_nome,
            "servico_reg":         svc_reg,
            "servico_rod":         svc_rod,
            "processo_rod":        proc_rod,
            "rodando":             rodando,
            "habilitado":          habilitado,
            "servico_oficial":     svc_oficial,
            "servico_oficial_rod": svc_oficial_rod,
        }

    conflito = st["3"]["rodando"] and st["4"]["rodando"]
    ativa    = None
    if not conflito:
        if st["4"]["rodando"]:
            ativa = "4"
        elif st["3"]["rodando"]:
            ativa = "3"

    return {
        "fb3": st["3"],
        "fb4": st["4"],
        "versao_ativa": ativa,
        "conflito":     conflito,
        # Chaves planas legado
        "fb3_servico_nome":      st["3"]["servico_nome"],
        "fb3_rodando":           st["3"]["rodando"],
        "fb3_habilitado":        st["3"]["habilitado"],
        "fb3_instalado":         st["3"]["instalado"],
        "fb3_modo":              st["3"]["modo"],
        "fb3_servico_reg":       st["3"]["servico_reg"],
        "fb3_servico_rod":       st["3"]["servico_rod"],
        "fb3_processo_rod":      st["3"]["processo_rod"],
        "fb3_servico_oficial":   st["3"]["servico_oficial"],
        "fb3_servico_oficial_rod": st["3"]["servico_oficial_rod"],
        "fb4_instalado":         st["4"]["instalado"],
        "fb4_modo":              st["4"]["modo"],
        "fb4_servico_nome":      st["4"]["servico_nome"],
        "fb4_servico_reg":       st["4"]["servico_reg"],
        "fb4_servico_rod":       st["4"]["servico_rod"],
        "fb4_processo_rod":      st["4"]["processo_rod"],
        "fb4_rodando":           st["4"]["rodando"],
        "fb4_habilitado":        st["4"]["habilitado"],
    }


def versao_ativa_agora() -> str | None:
    return status_detalhado()["versao_ativa"]


# Atalho legado — retorna serviço oficial se existir, senão Futura
def _nome_servico_fb3() -> str | None:
    oficial = _nome_servico_oficial_fb3()
    if oficial:
        return oficial
    nome = FB_CONFIGS["3"]["servico_nome"]
    return nome if _servico_existe(nome) else None


# =============================================================================
# Alternância exclusiva (compatibilidade)
# =============================================================================

def alternar_versao_ativa(
    versao_alvo: str,
    log_fn: Callable[[str], None] | None = None,
) -> dict:
    def log(m: str):
        if log_fn: log_fn(m)

    if versao_alvo not in ("3", "4"):
        return {"ok": False, "erro": f"Versao invalida: {versao_alvo}", "versao": ""}

    outra   = "4" if versao_alvo == "3" else "3"
    label_v = FB_CONFIGS[versao_alvo]["label"]
    log(f"=== Alternando para {label_v} ===")
    log(f"--- Passo 1: Inativando FB{outra} ---")
    inativar_fb(outra, log_fn)
    log(f"--- Passo 2: Ativando FB{versao_alvo} ---")
    r = ativar_fb(versao_alvo, log_fn)

    if r["ok"]:
        log(f"=== {label_v} esta ativo! ===")
        return {"ok": True, "erro": "", "versao": versao_alvo}
    return {"ok": False, "erro": r["erro"], "versao": ""}


# =============================================================================
# Instalação / Remoção
# =============================================================================

def instalar_fb_portable(
    versao: str = "4",
    log_fn: Callable[[str], None] | None = None,
    progresso_fn: Callable[[int], None] | None = None,
) -> dict:
    cfg = FB_CONFIGS.get(versao)
    if not cfg:
        return {"ok": False, "erro": f"Versao invalida: {versao}.", "versao": ""}

    fb_dir   = cfg["dir"]
    zip_url  = cfg["zip_url"]
    zip_size = cfg["zip_size"]
    porta    = cfg["porta"]
    label_v  = cfg["label"]

    def log(m):
        if log_fn: log_fn(m)

    def prog(p):
        if progresso_fn: progresso_fn(p)

    result = {"ok": False, "erro": "", "versao": ""}
    try:
        log(f"Criando pasta: {fb_dir}")
        os.makedirs(fb_dir, exist_ok=True)
        prog(5)

        zip_path = os.path.join(tempfile.gettempdir(), f"firebird{versao}_portable.zip")
        mb = zip_size // (1024 * 1024)
        log(f"Baixando {label_v} de:\n  {zip_url}")
        log(f"Aguarde, o arquivo tem ~{mb} MB...")

        _baixar_arquivo(zip_url, zip_path, zip_size,
                        progresso_fn=lambda p: prog(5 + int(p * 0.6)))
        prog(65)
        log("Download concluido.")

        log(f"Extraindo para: {fb_dir}")
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = zf.namelist()
            total   = len(members)
            raiz    = ""
            if members and "/" in members[0]:
                raiz = members[0].split("/")[0] + "/"
            for i, member in enumerate(members):
                nome_dest = member[len(raiz):] if raiz and member.startswith(raiz) else member
                if not nome_dest:
                    continue
                dest = os.path.join(fb_dir, nome_dest)
                if member.endswith("/"):
                    os.makedirs(dest, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with zf.open(member) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                prog(65 + int((i / total) * 25))

        prog(90)
        log("Extracao concluida.")

        diag = diagnosticar_instalacao(versao)
        log("Executaveis encontrados:")
        for arq in diag["arquivos"]:
            log(f"  {arq}")

        _configurar_firebird_conf(fb_dir, porta, versao)
        log(f"firebird.conf configurado (porta {porta}).")
        prog(95)

        gfix = _encontrar_gfix(versao)
        if not gfix:
            result["erro"] = (
                f"gfix.exe nao encontrado em {fb_dir} apos extracao. "
                f"EXEs presentes: {diag['arquivos']}"
            )
            return result

        ver = versao_fb_portable(versao)
        log(f"{label_v} instalado com sucesso! Versao: {ver}")
        prog(100)

        try:
            os.remove(zip_path)
        except Exception:
            pass

        result.update({"ok": True, "versao": ver})

    except Exception as e:
        result["erro"] = str(e)

    return result


def instalar_fb3_portable(log_fn=None, progresso_fn=None) -> dict:
    return instalar_fb_portable("3", log_fn, progresso_fn)


def instalar_fb4_portable(log_fn=None, progresso_fn=None) -> dict:
    return instalar_fb_portable("4", log_fn, progresso_fn)


def _baixar_arquivo(url, destino, tamanho_aprox, progresso_fn=None):
    req = urllib.request.Request(url, headers={"User-Agent": "FuturaSetup/4.3"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total   = int(resp.headers.get("Content-Length", tamanho_aprox))
        baixado = 0
        with open(destino, "wb") as f:
            while True:
                bloco = resp.read(65536)
                if not bloco:
                    break
                f.write(bloco)
                baixado += len(bloco)
                if progresso_fn:
                    progresso_fn(min(99, int(baixado / total * 100)))


def _configurar_firebird_conf(fb_dir, porta, versao):
    for subdir in _SERVIDOR_SUBDIRS:
        pasta = os.path.join(fb_dir, subdir) if subdir else fb_dir
        if os.path.isdir(pasta):
            conf_path = os.path.join(pasta, "firebird.conf")
            with open(conf_path, "w", encoding="utf-8") as f:
                f.write(
                    f"# Firebird {versao} Portable — configurado pelo Futura Setup\n"
                    f"RemoteServicePort = {porta}\n"
                    "GuardianOption = 0\n"
                )


def remover_fb_portable(versao: str = "4", log_fn=None) -> dict:
    cfg = FB_CONFIGS.get(versao)
    if not cfg:
        return {"ok": False, "erro": f"Versao invalida: {versao}."}

    def log(m):
        if log_fn: log_fn(m)

    fb_dir  = cfg["dir"]
    label_v = cfg["label"]

    if fb_servico_existe(versao):
        log(f"Removendo servico Windows do FB{versao} ...")
        _remover_servico_interno(versao, log_fn)

    inativar_fb(versao, log_fn)

    result = {"ok": False, "erro": ""}
    try:
        if not os.path.isdir(fb_dir):
            result["erro"] = f"Pasta nao encontrada: {fb_dir}"
            return result
        log(f"Removendo: {fb_dir}")
        shutil.rmtree(fb_dir)
        log(f"{label_v} removido com sucesso.")
        result["ok"] = True
    except Exception as e:
        result["erro"] = str(e)
    return result


def remover_fb3_portable(log_fn=None) -> dict:
    return remover_fb_portable("3", log_fn)


def remover_fb4_portable(log_fn=None) -> dict:
    return remover_fb_portable("4", log_fn)


# =============================================================================
# gfix
# =============================================================================

def gfix_fb(path, versao="4", user="SYSDBA", password="sbofutura") -> dict:
    gfix = _encontrar_gfix(versao)
    resultado = {
        "executado": False, "ok": False,
        "erros": [], "avisos": [], "saida_bruta": "", "msg": "",
    }
    if not gfix:
        resultado["msg"] = f"FB{versao} Portable nao instalado."
        return resultado
    try:
        proc = subprocess.run(
            [gfix, "-validate", "-full", "-user", user, "-password", password, path],
            capture_output=True, timeout=120,
            text=True, encoding="utf-8", errors="ignore",
        )
        saida = (proc.stdout + proc.stderr).strip()
        resultado["executado"]   = True
        resultado["saida_bruta"] = saida
        if not saida:
            resultado["ok"] = True
            return resultado
        for linha in saida.splitlines():
            l = linha.strip(); ll = l.lower()
            if not l:
                continue
            if any(k in ll for k in ["error", "corrupt", "wrong", "bad", "invalid", "damaged"]):
                resultado["erros"].append(l)
            elif any(k in ll for k in ["warning", "warn"]):
                resultado["avisos"].append(l)
        resultado["ok"] = len(resultado["erros"]) == 0
    except subprocess.TimeoutExpired:
        resultado["executado"] = True
        resultado["avisos"].append("Validacao excedeu 120s.")
    except Exception as e:
        resultado["msg"] = f"Erro ao rodar gfix: {e}"
    return resultado


def gfix_fb3(path, user="SYSDBA", password="sbofutura") -> dict:
    return gfix_fb(path, "3", user, password)


def gfix_fb4(path, user="SYSDBA", password="sbofutura") -> dict:
    return gfix_fb(path, "4", user, password)