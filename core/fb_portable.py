# =============================================================================
# FUTURA SETUP — Core: Firebird Portable Manager
# Orquestração de ativação, inativação e instalação do Firebird Portable
# =============================================================================
from __future__ import annotations
import os
import re
import shutil
import subprocess
import tempfile
import time
import sys
import urllib.request
import zipfile
import psutil
from typing import Callable

from config import (
    FB_PORTABLE_CONFIGS, FB3_INSTALLER_URL, FB4_REPO_ARQUIVOS,
    MAX_TENTATIVAS_DOWNLOAD, CREATE_NO_WINDOW
)
from core.service_manager import (
    is_admin, solicitar_admin, servico_existe, servico_rodando, 
    servico_desabilitado, iniciar_servico, parar_servico,
    registrar_fb_servico, remover_fb_servico,
    nome_servico_oficial_fb3, is_fb3_oficial_rodando,
    get_fb_modo, set_fb_modo, servico_binpath_valido,
    pywin32_disponivel, gerar_svc_wrapper, get_wrapper_path
)
from core.fb_utils import (
    encontrar_servidor, encontrar_instsvc, encontrar_gfix,
    encontrar_gbak, encontrar_isql, encontrar_gsec, encontrar_exe,
    security_db_path, get_fb_versao_bin, ler_flag_habilitado, 
    salvar_flag_habilitado, FB_CONFIGS, fb_portable_instalado,
    diagnosticar_instalacao
)

# Credenciais padrão do Futura
_FB_USER     = "SYSDBA"
_FB_PASSWORD = "sbofutura"
_SENHAS_FABRICA = ["masterkey", "masterke", ""]

_processos: dict[str, subprocess.Popen | None] = {"3": None, "4": None}
_SERVIDOR_CANDIDATOS = ["firebird.exe", "fbserver.exe"]
_SERVIDOR_SUBDIRS    = ["", "bin"]

# (O código do wrapper PyWin32 foi movido para service_manager.py)


# =============================================================================
# Wrapper pywin32 para FB3
# =============================================================================

# =============================================================================
# Helper Aliases (Legacy compatibility)
# =============================================================================

def _encontrar_exe(v, n): return encontrar_exe(v, n)
def _encontrar_servidor(v): return encontrar_servidor(v)
def _encontrar_instsvc(v): return encontrar_instsvc(v)
def _encontrar_gfix(v): return encontrar_gfix(v)
def _encontrar_gbak(v): return encontrar_gbak(v)
def _encontrar_isql(v): return encontrar_isql(v)
def _encontrar_gsec(v): return encontrar_gsec(v)

def _servico_existe(n): return servico_existe(n)
def _servico_rodando(n): return servico_rodando(n)
def _servico_desabilitado(n): return servico_desabilitado(n)
def _servico_iniciar(n, log=None, t=45): return iniciar_servico(n, log, t)
def _servico_parar(n, log=None, t=30): return parar_servico(n, log, t)
def _servico_binpath_valido(v): return servico_binpath_valido(v)
def _security_db_path(v): return security_db_path(v)
def _ler_flag(v): return ler_flag_habilitado(v)
def _salvar_flag(v, h): return salvar_flag_habilitado(v, h)
def fb_obter_modo(v): return get_fb_modo(v)
def _fb_salvar_modo(v, m): return set_fb_modo(v, m)
def _nome_servico_oficial_fb3(): return nome_servico_oficial_fb3()
def _pywin32_disponivel(): return pywin32_disponivel()
def _gerar_wrapper(v, s, l): return gerar_svc_wrapper(v, s, l)
def _wrapper_path(v): return get_wrapper_path(v)
def versao_fb_portable(v): return get_fb_versao_bin(v)


# =============================================================================
# Inicialização do Security Database
# =============================================================================

def _security_db_ok(versao: str) -> bool:
    path = security_db_path(versao)
    if not os.path.isfile(path) or os.path.getsize(path) < 500000: return False
    # ZIP portable FB3 original traz um security3.fdb de ~1.6MB que é 'incompleto'
    if versao == "3" and os.path.getsize(path) < 1650000: return False
    return True

def _security_db_incompleto(versao: str) -> bool:
    # Versão simplificada usando a lógica de tamanho já presente no security_db_ok
    return not _security_db_ok(versao)



def _flag_sysdba_path(versao: str) -> str:
    return os.path.join(FB_CONFIGS[versao]["dir"], f".fb{versao}_sysdba_ok")


def _sysdba_configurado(versao: str) -> bool:
    return os.path.isfile(_flag_sysdba_path(versao))


def _marcar_sysdba_ok(versao: str):
    try:
        open(_flag_sysdba_path(versao), "w").close()
    except Exception:
        pass


def _contem_erro_fatal(saida: str) -> bool:
    s = saida.lower()
    for t in ["install incomplete", "please read", "compatibility", "release notes"]:
        s = s.replace(t, "")
    return any(k in s for k in ["error", "failed", "invalid", "denied", "cannot", "unable"])

def _parar_e_remover_fb3_oficial(log_fn=None):
    def log(m):
        if log_fn: log_fn(m)
    for svc in ["FirebirdServerDefaultInstance", "FirebirdGuardianDefaultInstance", "FirebirdServer", "Firebird"]:
        if servico_existe(svc):
            log(f"  [FB3] Parando serviço oficial '{svc}'...")
            subprocess.run(["net", "stop", svc], capture_output=True, timeout=20)
    for proc in psutil.process_iter(['name', 'exe']):
        try:
            if proc.info['name'].lower() in ["firebird.exe", "fbserver.exe", "fbguard.exe"]:
                exe = proc.info.get('exe')
                if exe and ("Program Files" in exe or "Program Files (x86)" in exe):
                    proc.kill()
        except Exception: pass

def _obter_security3_fdb_via_instalador(log_fn=None) -> bool:
    def log(m):
        if log_fn: log_fn(m)
    dst = os.path.join(FB_CONFIGS["3"]["dir"], "security3.fdb")
    for src in [r"C:\Program Files\Firebird\Firebird_3_0\security3.fdb", r"C:\Program Files (x86)\Firebird\Firebird_3_0\security3.fdb"]:
        if os.path.isfile(src) and os.path.getsize(src) >= 1500000:
            try: shutil.copy2(src, dst); log(f"  [FB3] security3.fdb copiado."); return True
            except Exception: pass
    log("  [FB3] Baixando instalador FB3..."); inst = os.path.join(tempfile.gettempdir(), "fb3_setup.exe")
    try:
        urllib.request.urlretrieve(FB3_INSTALLER_URL, inst)
        subprocess.run([inst, "/VERYSILENT", "/NOICONS", '/TASKS=""', "/NORESTART"], capture_output=True, timeout=120)
        time.sleep(5)
        for src in [r"C:\Program Files\Firebird\Firebird_3_0\security3.fdb", r"C:\Program Files (x86)\Firebird\Firebird_3_0\security3.fdb"]:
            if os.path.isfile(src) and os.path.getsize(src) >= 1500000:
                shutil.copy2(src, dst); log("  [FB3] security3.fdb obtido."); break
        _parar_e_remover_fb3_oficial(log_fn)
    except Exception as e: log(f"  [FB3] Erro: {e}")
    finally:
        if os.path.isfile(inst): 
            try: os.remove(inst)
            except Exception: pass
    return os.path.isfile(dst)

def _configurar_sysdba_fb3_via_gsec(log_fn=None) -> bool:
    def log(m):
        if log_fn: log_fn(m)
    gsec = encontrar_gsec("3"); sec_path = security_db_path("3"); fb_dir = FB_CONFIGS["3"]["dir"]
    if not gsec or not os.path.isfile(sec_path): return False
    env = os.environ.copy(); env["FIREBIRD"] = fb_dir
    for senha in _SENHAS_FABRICA:
        cmd = [gsec, "-database", sec_path, "-user", _FB_USER, "-password", senha, "-modify", _FB_USER, "-pw", _FB_PASSWORD]
        try:
            r = subprocess.run(cmd, cwd=fb_dir, env=env, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=15)
            if r.returncode == 0: log("  [FB3] SYSDBA configurado."); return True
        except Exception: pass
    return False

def _inicializar_security_fb4_via_isql_embedded(log_fn=None) -> bool:
    def log(m):
        if log_fn: log_fn(m)
    isql = encontrar_isql("4"); fb_dir = FB_CONFIGS["4"]["dir"]; sec_path = os.path.join(fb_dir, "security4.fdb")
    if not isql: return False
    if os.path.isfile(sec_path):
        try: os.remove(sec_path)
        except Exception: return False
    log("  [FB4] Criando security4.fdb via isql embedded...")
    sql = f"CREATE DATABASE '{sec_path}';\nCREATE USER {_FB_USER} PASSWORD '{_FB_PASSWORD}';\nEXIT;\n"
    try:
        subprocess.run([isql, "-user", _FB_USER], input=sql, cwd=fb_dir, env=os.environ.copy(), capture_output=True, text=True, encoding="utf-8", timeout=30)
        return os.path.isfile(sec_path)
    except Exception: return False

def inicializar_security_db(versao: str, log_fn=None) -> bool:
    def log(m):
        if log_fn: log_fn(m)
    if _sysdba_configurado(versao) and _security_db_ok(versao): return True
    log(f"Inicializando security database do FB{versao} ...")
    if versao == "3":
        if not _security_db_ok("3"): _obter_security3_fdb_via_instalador(log_fn)
        ok = _configurar_sysdba_fb3_via_gsec(log_fn)
    else:
        ok = _inicializar_security_fb4_via_isql_embedded(log_fn)
    if ok: _marcar_sysdba_ok(versao)
    return ok
# --- Seção de serviços e persistência movida para service_manager.py e fb_utils.py ---


# =============================================================================
# Serviço Windows Futura
# =============================================================================

# --- Orquestração de Serviço ---

def fb_servico_existe(versao: str) -> bool:
    return _servico_existe(FB_CONFIGS[versao]["servico_nome"])

def fb_servico_rodando(versao: str) -> bool:
    return _servico_rodando(FB_CONFIGS[versao]["servico_nome"])

def ativar_fb_servico(versao: str, log_fn=None) -> dict:
    def log(m):
        if log_fn: log_fn(m)
    if not is_admin():
        msg = "Permissao de administrador necessaria."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg, "requer_admin": True}

    log(f"Verificando security database do FB{versao} ...")
    inicializar_security_db(versao, log_fn)

    nome = FB_CONFIGS[versao]["servico_nome"]
    if not _servico_existe(nome) or not _servico_binpath_valido(versao):
        log(f"Servico '{nome}' inexistente ou binPath invalido. Registrando ...")
        # Usa a função importada do service_manager
        r = registrar_fb_servico(versao, _parar_processo, log_fn)
        if not r["ok"]: return r

    # Para outra versão se estiver rodando
    outra = "4" if versao == "3" else "3"
    if _outra_versao_rodando(versao):
        log(f"Detectada outra versao rodando — inativando {FB_CONFIGS[outra]['label']}...")
        inativar_fb(outra, log_fn)
        time.sleep(1)

    if _servico_desabilitado(nome):
        log(f"Habilitando servico '{nome}' ...")
        subprocess.run(["sc", "config", nome, "start=", "auto"], capture_output=True, timeout=10, creationflags=CREATE_NO_WINDOW)

    if _servico_rodando(nome):
        log(f"Servico '{nome}' ja esta rodando.")
        return {"ok": True, "erro": ""}

    log(f"Iniciando servico '{nome}' ...")
    if _servico_iniciar(nome, log_fn):
        log(f"Firebird {versao} ativado como servico (porta {FB_CONFIGS[versao]['porta']}).")
        return {"ok": True, "erro": ""}
    return {"ok": False, "erro": f"Servico '{nome}' nao subiu."}

def inativar_fb_servico(versao: str, log_fn=None) -> dict:
    def log(m):
        if log_fn: log_fn(m)
    if not is_admin():
        return {"ok": False, "erro": "Admin necessario.", "requer_admin": True}
    nome = FB_CONFIGS[versao]["servico_nome"]
    if not _servico_existe(nome): return {"ok": True, "erro": ""}
    if not _servico_rodando(nome): return {"ok": True, "erro": ""}
    log(f"Parando servico '{nome}' ...")
    if _servico_parar(nome, log_fn):
        log("Servico parado com sucesso.")
        return {"ok": True, "erro": ""}
    return {"ok": False, "erro": f"Servico '{nome}' nao parou."}

# Redundant legacy wrappers removed. Use high-level functions above or core directly.
def fb3_servico_existe()  -> bool: return fb_servico_existe("3")
def fb4_servico_existe()  -> bool: return fb_servico_existe("4")
def fb3_servico_rodando() -> bool: return fb_servico_rodando("3")
def fb4_servico_rodando() -> bool: return fb_servico_rodando("4")
def fb3_obter_modo()      -> str:  return fb_obter_modo("3")
def fb4_obter_modo()      -> str:  return fb_obter_modo("4")


# =============================================================================
# Processo portable
# =============================================================================

def _processo_rodando(versao: str) -> bool:
    v_proc = _processos.get(versao)
    if v_proc is not None and v_proc.poll() is None:
        return True
    fb_dir = FB_CONFIGS[versao]["dir"].lower()
    for p in psutil.process_iter(['name']):
        try:
            if p.info['name'].lower() in _SERVIDOR_CANDIDATOS:
                exe_p = p.exe()
                if exe_p and fb_dir in exe_p.lower():
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
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
        fb_dir = FB_CONFIGS[versao]["dir"].lower()
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                if proc.info['name'].lower() in _SERVIDOR_CANDIDATOS:
                    exe = proc.info['exe']
                    if exe and fb_dir in exe.lower():
                        log(f"  Encerrando processo portable {proc.info['name']} (PID {proc.pid}) ...")
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
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
# Ativar / Inativar
# =============================================================================

def _outra_versao_rodando(versao: str) -> bool:
    outra = "4" if versao == "3" else "3"
    if _processo_rodando(outra):
        return True
    if _servico_rodando(FB_CONFIGS[outra]["servico_nome"]):
        return True
    if outra == "3":
        nome_oficial = _nome_servico_oficial_fb3()
        if nome_oficial and _servico_rodando(nome_oficial):
            return True
    return False


def ativar_fb(versao: str, log_fn=None) -> dict:
    def log(m):
        if log_fn: log_fn(m)

    if _outra_versao_rodando(versao):
        outra     = "4" if versao == "3" else "3"
        outra_lbl = FB_CONFIGS[outra]["label"]
        esta_lbl  = FB_CONFIGS[versao]["label"]
        log(f"Detectada outra versao rodando — inativando {outra_lbl} para ativar o {esta_lbl}...")
        inativar_fb(outra, log_fn)
        time.sleep(1)
        if _outra_versao_rodando(versao):
            msg = f"Nao foi possivel inativar o {outra_lbl} automaticamente."
            log(f"ERRO: {msg}")
            return {"ok": False, "erro": msg}

    modo = fb_obter_modo(versao)
    if modo == "servico":
        log(f"Modo servico Windows detectado para FB{versao}.")
        return ativar_fb_servico(versao, log_fn)

    if not fb_portable_instalado(versao):
        msg = f"FB{versao} Portable nao esta instalado."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg}

    servidor = _encontrar_servidor(versao)
    if servidor is None:
        diag = diagnosticar_instalacao(versao)
        exes = ", ".join(diag["arquivos"]) if diag["arquivos"] else "nenhum"
        msg  = f"Executavel do servidor nao encontrado. EXEs: [{exes}]."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg}

    log(f"Verificando security database do FB{versao} ...")
    inicializar_security_db(versao, log_fn)

    _salvar_flag(versao, True)
    log(f"Firebird {versao} Portable habilitado (modo processo).")

    if _processo_rodando(versao):
        log(f"Firebird {versao} Portable ja esta ativo (porta {FB_CONFIGS[versao]['porta']}).")
        return {"ok": True, "erro": ""}

    porta = FB_CONFIGS[versao]["porta"]
    log(f"Iniciando processo FB{versao} (porta {porta}) ...")
    log(f"Servidor: {servidor}")
    try:
        proc = subprocess.Popen(
            [servidor, "-a"],
            cwd=os.path.dirname(servidor),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW,
        )
        _processos[versao] = proc
        for _ in range(10):
            time.sleep(1)
            if proc.poll() is not None:
                saida = ""
                try:
                    if proc.stdout:
                        saida = proc.stdout.read().decode(errors="ignore")
                except Exception:
                    pass
                log(f"ERRO: servidor encerrou inesperadamente.\n{saida}")
                _processos[versao] = None
                return {"ok": False, "erro": "Servidor encerrou inesperadamente."}
            if _processo_rodando(versao):
                log(f"Firebird {versao} Portable ativado (porta {porta}).")
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
    def log(m):
        if log_fn: log_fn(m)

    modo = fb_obter_modo(versao)
    if modo == "servico":
        log(f"Modo servico Windows detectado para FB{versao}.")
        inativar_fb_servico(versao, log_fn)

    if versao == "3":
        nome_oficial = _nome_servico_oficial_fb3()
        if nome_oficial and _servico_rodando(nome_oficial):
            log(f"Parando servico oficial FB3 '{nome_oficial}' ...")
            ok_oficial = _servico_parar(nome_oficial, log_fn)
            if ok_oficial:
                log(f"Servico oficial '{nome_oficial}' parado com sucesso.")
            else:
                log(f"AVISO: nao foi possivel parar o servico oficial '{nome_oficial}'.")

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
    log(f"Firebird {versao} Portable desabilitado.")
    return {"ok": True, "erro": ""}


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

        svc_oficial = svc_oficial_rod = None
        if v == "3":
            svc_oficial     = _nome_servico_oficial_fb3()
            svc_oficial_rod = _servico_rodando(svc_oficial) if svc_oficial else False
            if svc_oficial_rod:
                rodando = habilitado = True

        st[v] = {
            "instalado": inst, "modo": modo,
            "servico_nome": svc_nome, "servico_reg": svc_reg,
            "servico_rod": svc_rod, "processo_rod": proc_rod,
            "rodando": rodando, "habilitado": habilitado,
            "servico_oficial": svc_oficial,
            "servico_oficial_rod": svc_oficial_rod,
        }

    conflito = st["3"]["rodando"] and st["4"]["rodando"]
    ativa    = None
    if not conflito:
        ativa = "4" if st["4"]["rodando"] else ("3" if st["3"]["rodando"] else None)

    return {
        "fb3": st["3"], "fb4": st["4"],
        "versao_ativa": ativa, "conflito": conflito,
        "fb3_servico_nome":        st["3"]["servico_nome"],
        "fb3_rodando":             st["3"]["rodando"],
        "fb3_habilitado":          st["3"]["habilitado"],
        "fb3_instalado":           st["3"]["instalado"],
        "fb3_modo":                st["3"]["modo"],
        "fb3_servico_reg":         st["3"]["servico_reg"],
        "fb3_servico_rod":         st["3"]["servico_rod"],
        "fb3_processo_rod":        st["3"]["processo_rod"],
        "fb3_servico_oficial":     st["3"]["servico_oficial"],
        "fb3_servico_oficial_rod": st["3"]["servico_oficial_rod"],
        "fb4_instalado":           st["4"]["instalado"],
        "fb4_modo":                st["4"]["modo"],
        "fb4_servico_nome":        st["4"]["servico_nome"],
        "fb4_servico_reg":         st["4"]["servico_reg"],
        "fb4_servico_rod":         st["4"]["servico_rod"],
        "fb4_processo_rod":        st["4"]["processo_rod"],
        "fb4_rodando":             st["4"]["rodando"],
        "fb4_habilitado":          st["4"]["habilitado"],
    }


def versao_ativa_agora() -> str | None:
    return status_detalhado()["versao_ativa"]


def _nome_servico_fb3() -> str | None:
    oficial = _nome_servico_oficial_fb3()
    if oficial:
        return oficial
    nome = FB_CONFIGS["3"]["servico_nome"]
    return nome if _servico_existe(nome) else None


# =============================================================================
# Alternância exclusiva
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
    inativar_fb(outra, log_fn)
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
        log(f"Baixando {label_v} (~{zip_size//(1024*1024)} MB) ...")
        _baixar_arquivo(zip_url, zip_path, zip_size,
                        progresso_fn=lambda p: prog(5 + int(p * 0.6)))
        prog(65)
        log("Download concluido.")

        log(f"Extraindo para: {fb_dir}")
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = zf.namelist(); total = len(members); raiz = ""
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
                prog(65 + int((i / total) * 20))

        prog(85)
        log("Extracao concluida.")
        diag = diagnosticar_instalacao(versao)
        log("Executaveis encontrados:")
        for arq in diag["arquivos"]:
            log(f"  {arq}")

        _configurar_firebird_conf(fb_dir, porta, versao)
        log(f"firebird.conf configurado (porta {porta}).")
        prog(88)

        # FB3: remove o security3.fdb que veio no zip (estado 'Install incomplete')
        # e limpa a flag antiga para forcar reconfiguração completa.
        if versao == "3":
            sec_path_zip = os.path.join(fb_dir, "security3.fdb")
            if os.path.isfile(sec_path_zip):
                log("  [FB3] Removendo security3.fdb do zip (Install incomplete) ...")
                try:
                    os.remove(sec_path_zip)
                except Exception as e:
                    log(f"    falha ao remover: {e}")
            flag = os.path.join(fb_dir, ".fb3_sysdba_ok")
            if os.path.isfile(flag):
                try:
                    os.remove(flag)
                except Exception:
                    pass

        log("Configurando security database e usuario SYSDBA ...")
        inicializar_security_db(versao, log_fn)
        prog(96)

        gfix = _encontrar_gfix(versao)
        if not gfix:
            result["erro"] = f"gfix.exe nao encontrado. EXEs: {diag['arquivos']}"
            return result

        ver = get_fb_versao_bin(versao)
        log(f"{label_v} instalado! Versao: {ver}")
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


def _baixar_arquivo(url, destino, tamanho_aprox, progresso_fn=None, log_fn=None):
    def log(m):
        if log_fn: log_fn(m)

    tentativas = 0
    while tentativas < MAX_TENTATIVAS_DOWNLOAD:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FuturaSetup/4.3"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", tamanho_aprox))
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
            return  # Sucesso
        except Exception as e:
            tentativas += 1
            if log_fn:
                log(f"    Download falhou (tentativa {tentativas}/{MAX_TENTATIVAS_DOWNLOAD}): {e}")
            if tentativas >= MAX_TENTATIVAS_DOWNLOAD:
                raise
            time.sleep(2)


def _configurar_firebird_conf(fb_dir, porta, versao):
    for subdir in _SERVIDOR_SUBDIRS:
        pasta = os.path.join(fb_dir, subdir) if subdir else fb_dir
        if os.path.isdir(pasta):
            conf_path = os.path.join(pasta, "firebird.conf")
            sec_db    = os.path.join(fb_dir, f"security{versao}.fdb")
            if versao == "4":
                # FB4: IpcName unico evita conflito de mutex XNET com FB3
                conteudo = (
                    f"# Firebird {versao} Portable — configurado pelo Futura Setup\n"
                    f"RemoteServicePort = {porta}\n"
                    "GuardianOption = 0\n"
                    f"SecurityDatabase = {sec_db}\n"
                    "IpcName = FB_FB4_IPC\n"
                    "ServerMode = Super\n"
                )
            else:
                conteudo = (
                    f"# Firebird {versao} Portable — configurado pelo Futura Setup\n"
                    f"RemoteServicePort = {porta}\n"
                    "GuardianOption = 0\n"
                )
            with open(conf_path, "w", encoding="utf-8") as f:
                f.write(conteudo)


def remover_fb_portable(versao: str = "4", log_fn=None) -> dict:
    cfg = FB_CONFIGS.get(versao)
    if not cfg:
        return {"ok": False, "erro": f"Versao invalida: {versao}."}

    def log(m):
        if log_fn: log_fn(m)

    fb_dir  = cfg["dir"]
    label_v = cfg["label"]

    # Remove o serviço se existir (usa a função centralizada)
    if fb_servico_existe(versao):
        log(f"Removendo servico Windows do FB{versao} ...")
        res_svc = remover_fb_servico(versao, log_fn)
        if not res_svc["ok"] and res_svc.get("requer_admin"):
            log(f"AVISO: servico Windows detectado mas sem permissao de admin para remover.")
            log(f"  O servico '{cfg['servico_nome']}' permanecera registrado.")
            log(f"  Reinicie como Administrador para remove-lo completamente.")

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


def remover_fb3_portable(log_fn=None) -> dict: return remover_fb_portable("3", log_fn)
def remover_fb4_portable(log_fn=None) -> dict: return remover_fb_portable("4", log_fn)


# =============================================================================
# Configuração oficial FB4 — arquivos do repositório Futura
# =============================================================================

_FB4_REPO_ARQUIVOS = FB4_REPO_ARQUIVOS


def aplicar_configs_oficiais_fb4(
    caminho_dados: str = "",
    caminho_cep: str = "",
    log_fn=None,
) -> dict:
    """
    Baixa os 3 arquivos oficiais de configuração do FB4 do repositório Futura,
    copia na raiz do FB4 e reinicia o serviço.

    - firebird.conf : configurações do servidor (porta 3050 padrão oficial)
    - databases.conf: aliases de bancos (Dados e CEP adicionados ao final)
    - Usuarios.sql  : script de usuários (copiado apenas)

    caminho_dados e caminho_cep são opcionais — se não informados, usa os
    aliases já existentes no databases.conf baixado.
    """
    def log(m):
        if log_fn: log_fn(m)

    fb_dir   = FB_CONFIGS["4"]["dir"]
    svc_nome = FB_CONFIGS["4"]["servico_nome"]
    result   = {"ok": False, "erro": ""}

    if not os.path.isdir(fb_dir):
        result["erro"] = f"FB4 não está instalado em {fb_dir}."
        log(f"ERRO: {result['erro']}")
        return result

    # ── Baixa os arquivos ────────────────────────────────────────────────
    log("Baixando arquivos de configuração oficiais do FB4 ...")
    for nome, url in _FB4_REPO_ARQUIVOS.items():
        destino = os.path.join(fb_dir, nome)
        log(f"  Baixando {nome} ...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FuturaSetup/4.3"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                with open(destino, "wb") as f:
                    shutil.copyfileobj(resp, f)
            log(f"  {nome} copiado ({os.path.getsize(destino):,} bytes).")
        except Exception as e:
            result["erro"] = f"Erro ao baixar {nome}: {e}"
            log(f"  ERRO: {result['erro']}")
            return result

    # ── Porta 3050 já é o padrão oficial — nenhuma correção necessária ───
    conf_path = os.path.join(fb_dir, "firebird.conf")
    try:
        with open(conf_path, "r", encoding="utf-8", errors="ignore") as f:
            conf = f.read()
        with open(conf_path, "w", encoding="utf-8") as f:
            f.write(conf)
        log("  firebird.conf: porta mantida como 3050 (padrão oficial).")
    except Exception as e:
        log(f"  AVISO: não foi possível ajustar porta no firebird.conf: {e}")

    # ── Adiciona aliases Dados e CEP no databases.conf se informados ──────
    if caminho_dados or caminho_cep:
        try:
            atualizar_databases_conf("4", caminho_dados, log_fn)
        except Exception as e:
            log(f"  AVISO: não foi possível atualizar databases.conf: {e}")

    # ── Reinicia o serviço ────────────────────────────────────────────────
    log("Reiniciando serviço FB4 ...")
    try:
        if _servico_rodando(svc_nome):
            subprocess.run(["net", "stop", svc_nome], capture_output=True, timeout=30)
            time.sleep(2)
        if _servico_existe(svc_nome):
            subprocess.run(["net", "start", svc_nome], capture_output=True, timeout=30)
            time.sleep(3)
            if _servico_rodando(svc_nome):
                log("Serviço FB4 reiniciado com sucesso.")
            else:
                log("AVISO: serviço FB4 não subiu após reinício.")
        else:
            log("AVISO: serviço FB4 não está registrado — registre antes de aplicar configs.")
    except Exception as e:
        log(f"  AVISO: erro ao reiniciar serviço: {e}")

    result["ok"] = True
    log("Configuração oficial FB4 aplicada com sucesso.")
    return result


# =============================================================================
# gfix
# =============================================================================

def gfix_fb(path, versao="4", user="SYSDBA", password="sbofutura") -> dict:
    gfix = _encontrar_gfix(versao)
    # Inicializa explicitamente como listas para evitar confusão do linter
    errs: list[str] = []
    avis: list[str] = []
    resultado = {"executado": False, "ok": False, "erros": errs, "avisos": avis, "saida_bruta": "", "msg": ""}
    if not gfix:
        resultado["msg"] = f"FB{versao} Portable nao instalado."
        return resultado
    try:
        proc = subprocess.run(
            [gfix, "-validate", "-full", "-user", user, "-password", password, path],
            capture_output=True, timeout=120, text=True, encoding="utf-8", errors="ignore",
            creationflags=CREATE_NO_WINDOW,
        )
        saida = (proc.stdout + proc.stderr).strip()
        resultado["executado"] = True
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

def gfix_fb3(path, user="SYSDBA", password="sbofutura") -> dict: return gfix_fb(path, "3", user, password)
def gfix_fb4(path, user="SYSDBA", password="sbofutura") -> dict: return gfix_fb(path, "4", user, password)


# =============================================================================
# databases.conf — varredura e atualização
# =============================================================================

# Arquivos a ignorar na varredura
_FDB_IGNORAR_PREFIXOS = ["security"]
_FDB_IGNORAR_SUFIXOS  = ["-journal", ".tmp"]
_FDB_IGNORAR_NOMES    = ["security3.fdb", "security4.fdb"]


def _fdb_ignorar(caminho: str) -> bool:
    """Retorna True se o arquivo deve ser ignorado na varredura."""
    nome = os.path.basename(caminho).lower()
    for pref in _FDB_IGNORAR_PREFIXOS:
        if nome.startswith(pref):
            return True
    for suf in _FDB_IGNORAR_SUFIXOS:
        if nome.endswith(suf):
            return True
    if nome in _FDB_IGNORAR_NOMES:
        return True
    return False


def varrer_fdb(
    raiz: str = "C:\\",
    log_fn=None,
    progresso_fn=None,
) -> list[str]:
    """
    Varre o HD a partir de 'raiz' e retorna lista de caminhos .fdb encontrados,
    ignorando security*.fdb e arquivos temporários.

    Retorna lista ordenada de caminhos absolutos.
    """
    def log(m):
        if log_fn: log_fn(m)
    def prog(p):
        if progresso_fn: progresso_fn(p)

    encontrados = []
    pastas_ignorar = {
        "windows", "program files", "program files (x86)",
        "$recycle.bin", "system volume information",
        "futurafirebird",  # ignora os próprios bancos do portable
    }

    log(f"Varrendo {raiz} em busca de arquivos .fdb ...")
    prog(0)

    try:
        for raiz_dir, dirs, arquivos in os.walk(raiz, topdown=True):
            # Remove pastas que não precisam ser varridas
            dirs[:] = [
                d for d in dirs
                if d.lower() not in pastas_ignorar
                and not d.startswith(".")
            ]

            for arq in arquivos:
                if not arq.lower().endswith(".fdb"):
                    continue
                caminho = os.path.join(raiz_dir, arq)
                if not _fdb_ignorar(caminho):
                    encontrados.append(caminho)

    except Exception as e:
        log(f"  Erro durante varredura: {e}")

    encontrados.sort()
    log(f"Varredura concluída. {len(encontrados)} arquivo(s) .fdb encontrado(s).")
    prog(100)
    return encontrados


def atualizar_databases_conf(
    versao: str,
    caminho_dados: str,
    log_fn=None,
) -> dict:
    """
    Atualiza (ou cria) o databases.conf do Firebird Portable com as entradas
    Dados e Cep.

    - caminho_dados : caminho completo do dados.fdb selecionado pelo usuário
    - cep.fdb       : inferido automaticamente — mesma pasta, nome 'cep.fdb'

    Formato gerado abaixo do marcador '# Live Databases:':

        # Live Databases:
        #
        Dados = "C:\\caminho\\para\\dados.fdb"
        Cep   = "C:\\caminho\\para\\cep.fdb"

    Se o marcador não existir no arquivo, as entradas são adicionadas ao final.
    Atualiza se já existir, cria se não existir.
    """
    def log(m):
        if log_fn: log_fn(m)

    fb_dir    = FB_CONFIGS[versao]["dir"]
    conf_path = os.path.join(fb_dir, "databases.conf")

    pasta_dados  = os.path.dirname(caminho_dados)
    caminho_cep  = os.path.join(pasta_dados, "cep.fdb")

    # Bloco Live Databases a inserir/substituir
    bloco_live = (
        "# Live Databases:\n"
        "#\n"
        f'Dados = {caminho_dados}\n'
        f'Cep   = {caminho_cep}\n'
    )

    try:
        # Lê conteúdo existente ou inicia vazio
        if os.path.isfile(conf_path):
            with open(conf_path, "r", encoding="utf-8") as f:
                conteudo = f.read()
            log(f"databases.conf existente encontrado: {conf_path}")
        else:
            conteudo = ""
            log(f"databases.conf não encontrado — será criado: {conf_path}")

        marcador = "# Live Databases:"

        if marcador in conteudo:
            # Substitui apenas o bloco Live Databases, preservando tudo antes
            idx            = conteudo.index(marcador)
            cabecalho      = conteudo[:idx]
            conteudo_final = cabecalho + bloco_live
        else:
            # Marcador não existe — preserva conteúdo original e adiciona ao final
            # Remove entradas Dados/Cep antigas se existirem
            linhas_limpas = []
            for linha in conteudo.splitlines():
                l = linha.strip().lower()
                if l.startswith("dados =") or l.startswith("cep =") or l.startswith("cep   ="):
                    continue
                linhas_limpas.append(linha)
            conteudo_limpo = "\n".join(linhas_limpas)
            sep = "\n" if conteudo_limpo and not conteudo_limpo.endswith("\n") else ""
            conteudo_final = conteudo_limpo + sep + "\n" + bloco_live

        with open(conf_path, "w", encoding="utf-8") as f:
            f.write(conteudo_final)

        log(f"databases.conf atualizado com sucesso.")
        log(f"  Dados = {caminho_dados}")
        log(f"  Cep   = {caminho_cep}")
        return {"ok": True, "erro": "", "conf_path": conf_path}

    except Exception as e:
        log(f"Erro ao atualizar databases.conf: {e}")
        return {"ok": False, "erro": str(e), "conf_path": conf_path}


def configurar_databases_fb3(caminho_dados: str, log_fn=None) -> dict:
    return atualizar_databases_conf("3", caminho_dados, log_fn)

def configurar_databases_fb4(caminho_dados: str, log_fn=None) -> dict:
    return atualizar_databases_conf("4", caminho_dados, log_fn)


def reiniciar_fb(versao: str, log_fn=None) -> dict:
    """Para e inicia o Firebird novamente, respeitando o modo atual."""

    def log(m):
        if log_fn:
            log_fn(m)

    log(f"Reiniciando Firebird {versao} ...")

    # Garante que a outra versão pare se estiver rodando
    outra = "4" if versao == "3" else "3"
    if _outra_versao_rodando(versao):
        log(f"Detectada outra versao rodando — inativando {FB_CONFIGS[outra]['label']} para evitar conflitos...")
        inativar_fb(outra, log_fn)
        time.sleep(1)

    st = status_detalhado()
    d  = st[f"fb{versao}"]

    if d["modo"] == "servico" and d["servico_reg"]:
        log("Modo: Servico Windows")
        inativar_fb_servico(versao, log_fn)
        time.sleep(1)
        return ativar_fb_servico(versao, log_fn)
    else:
        log("Modo: Processo portable")
        inativar_fb(versao, log_fn)
        time.sleep(1)
        return ativar_fb(versao, log_fn)