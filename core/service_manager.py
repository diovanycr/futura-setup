# =============================================================================
# FUTURA SETUP — Core: Windows Service Manager
# Gerenciamento de serviços Windows para Firebird Portable
# =============================================================================
from __future__ import annotations
import ctypes
import os
import subprocess
import sys
import time
from typing import Callable

from config import FB_PORTABLE_CONFIGS, CREATE_NO_WINDOW
from core.fb_utils import (
    encontrar_servidor, encontrar_instsvc, encontrar_exe,
    FB_CONFIGS
)

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
# Utilitários de Serviço Windows (sc.exe / net.exe)
# =============================================================================

def servico_existe(nome: str) -> bool:
    try:
        r = subprocess.run(["sc", "query", nome],
                           capture_output=True, text=True, timeout=5,
                           creationflags=CREATE_NO_WINDOW)
        return r.returncode == 0
    except Exception:
        return False


def servico_rodando(nome: str) -> bool:
    try:
        r = subprocess.run(["sc", "query", nome],
                           capture_output=True, text=True, timeout=5,
                           creationflags=CREATE_NO_WINDOW)
        return "RUNNING" in r.stdout
    except Exception:
        return False


def servico_desabilitado(nome: str) -> bool:
    try:
        r = subprocess.run(["sc", "qc", nome],
                           capture_output=True, text=True, timeout=5,
                           creationflags=CREATE_NO_WINDOW)
        return "DISABLED" in r.stdout.upper()
    except Exception:
        return False


def iniciar_servico(nome: str, log_fn: Callable = None, timeout_s: int = 45) -> bool:
    def log(m):
        if log_fn: log_fn(m)
    try:
        r = subprocess.run(
            ["net", "start", nome],
            capture_output=True, text=True,
            encoding="utf-8", errors="ignore",
            timeout=timeout_s,
            creationflags=CREATE_NO_WINDOW,
        )
        saida = (r.stdout + r.stderr).strip()
        if saida:
            log(f"  net start: {saida[:400]}")
        for _ in range(20):
            time.sleep(1)
            if servico_rodando(nome):
                return True
    except Exception as e:
        log(f"Erro ao iniciar servico '{nome}': {e}")
    return False


def parar_servico(nome: str, log_fn: Callable = None, timeout_s: int = 30) -> bool:
    def log(m):
        if log_fn: log_fn(m)
    try:
        subprocess.run(["net", "stop", nome], capture_output=True, timeout=timeout_s,
                       creationflags=CREATE_NO_WINDOW)
        for _ in range(20):
            time.sleep(1)
            if not servico_rodando(nome):
                return True
    except Exception as e:
        log(f"Erro ao parar servico '{nome}': {e}")
    return False


# =============================================================================
# Gerenciamento de Wrapper PyWin32 (para FB3)
# =============================================================================

def pywin32_disponivel() -> bool:
    try:
        import win32serviceutil  # noqa: F401
        return True
    except ImportError:
        return False


def gerar_svc_wrapper(versao: str, fbserver_path: str, log_fn: Callable = None) -> str | None:
    def log(m):
        if log_fn: log_fn(m)

    cfg      = FB_CONFIGS[versao]
    fb_dir   = cfg["dir"]
    svc_name = cfg["servico_nome"]
    svc_lbl  = cfg["label"]
    fbdir    = os.path.dirname(fbserver_path)

    fbserver_esc = fbserver_path.replace("\\", "\\\\")
    fbdir_esc    = fbdir.replace("\\", "\\\\")

    linhas = [
        "# AUTO-GERADO pelo Futura Setup --- NAO EDITE MANUALMENTE",
        "import subprocess, sys, os",
        "import win32serviceutil, win32service, win32event, servicemanager",
        "",
        "FBSERVER_EXE = r'" + fbserver_esc + "'",
        "FBSERVER_DIR = r'" + fbdir_esc    + "'",
        "SVC_NAME     = '" + svc_name      + "'",
        "SVC_LABEL    = '" + svc_lbl       + "'",
        "",
        "",
        "class FirebirdPortableSvc(win32serviceutil.ServiceFramework):",
        "    _svc_name_         = SVC_NAME",
        "    _svc_display_name_ = SVC_LABEL",
        "    _svc_description_  = 'Firebird Portable gerenciado pelo Futura Setup'",
        "",
        "    def __init__(self, args):",
        "        win32serviceutil.ServiceFramework.__init__(self, args)",
        "        self._stop_event = win32event.CreateEvent(None, 0, 0, None)",
        "        self._proc = None",
        "",
        "    def SvcStop(self):",
        "        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)",
        "        if self._proc and self._proc.poll() is None:",
        "            try:",
        "                self._proc.terminate()",
        "                self._proc.wait(timeout=10)",
        "            except Exception:",
        "                pass",
        "        win32event.SetEvent(self._stop_event)",
        "",
        "    def SvcDoRun(self):",
        "        servicemanager.LogMsg(",
        "            servicemanager.EVENTLOG_INFORMATION_TYPE,",
        "            servicemanager.PYS_SERVICE_STARTING,",
        "            (self._svc_name_, ''),",
        "        )",
        "        self._proc = subprocess.Popen(",
        "            [FBSERVER_EXE, '-a'],",
        "            cwd=FBSERVER_DIR,",
        "            stdout=subprocess.DEVNULL,",
        "            stderr=subprocess.DEVNULL,",
        "        )",
        "        servicemanager.LogMsg(",
        "            servicemanager.EVENTLOG_INFORMATION_TYPE,",
        "            servicemanager.PYS_SERVICE_STARTED,",
        "            (self._svc_name_, ''),",
        "        )",
        "        while True:",
        "            rc = win32event.WaitForSingleObject(self._stop_event, 2000)",
        "            if rc == win32event.WAIT_OBJECT_0:",
        "                break",
        "            if self._proc.poll() is not None:",
        "                servicemanager.LogErrorMsg(",
        "                    SVC_NAME + ': fbserver.exe encerrou inesperadamente.'",
        "                )",
        "                break",
        "",
        "",
        "if __name__ == '__main__':",
        "    win32serviceutil.HandleCommandLine(FirebirdPortableSvc)",
        "",
    ]

    conteudo     = "\n".join(linhas)
    wrapper_path = os.path.join(fb_dir, "fb_svc_wrapper.py")
    try:
        if not os.path.isdir(fb_dir):
            os.makedirs(fb_dir, exist_ok=True)
        with open(wrapper_path, "w", encoding="utf-8") as f:
            f.write(conteudo)
        log(f"  Wrapper gerado: {wrapper_path}")
        return wrapper_path
    except Exception as e:
        log(f"  ERRO ao gerar wrapper: {e}")
        return None


def get_wrapper_path(versao: str) -> str:
    return os.path.join(FB_CONFIGS[versao]["dir"], "fb_svc_wrapper.py")


def servico_binpath_valido(versao: str) -> bool:
    nome   = FB_CONFIGS[versao]["servico_nome"]
    fb_dir = FB_CONFIGS[versao]["dir"].lower()
    try:
        r = subprocess.run(
            ["sc", "qc", nome],
            capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=5,
            creationflags=CREATE_NO_WINDOW
        )
        bin_path = ""
        for linha in (r.stdout + r.stderr).splitlines():
            l = linha.strip()
            if any(k in l.upper() for k in [
                "BINARY_PATH_NAME", "CAMINHO_DO_BINARIO", "CAMINHO_DO_BIN"
            ]):
                partes = l.split(":", 1)
                if len(partes) == 2:
                    bin_path = partes[1].strip().lower()
                break
        if not bin_path:
            return False
        if fb_dir not in bin_path:
            return False
        if versao == "3":
            return "fb_svc_wrapper.py" in bin_path
        else:
            return "fbserver.exe" in bin_path or "firebird.exe" in bin_path
    except Exception:
        return False

# =============================================================================
# Serviços Oficiais
# =============================================================================

def nome_servico_oficial_fb3() -> str | None:
    for nome in FB_CONFIGS["3"]["servicos_win_oficiais"]:
        if servico_existe(nome):
            return nome
    return None

def is_fb3_oficial_rodando() -> bool:
    nome = nome_servico_oficial_fb3()
    return servico_rodando(nome) if nome else False


# =============================================================================
# Modo de Execução (Persistência)
# =============================================================================

def _modo_path(versao: str) -> str:
    return os.path.join(FB_CONFIGS[versao]["dir"], f".fb{versao}_modo")


def get_fb_modo(versao: str) -> str:
    if servico_existe(FB_CONFIGS[versao]["servico_nome"]):
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


def set_fb_modo(versao: str, modo: str):
    try:
        os.makedirs(FB_CONFIGS[versao]["dir"], exist_ok=True)
        with open(_modo_path(versao), "w") as f:
            f.write(modo)
    except Exception:
        pass


# =============================================================================
# Registro e Remoção de Serviços Futura (FIREBIRD PORTABLE)
# =============================================================================

def registrar_fb_servico(versao: str, stop_proc_fn: Callable = None, log_fn: Callable = None) -> dict:
    def log(m):
        if log_fn: log_fn(m)

    if not is_admin():
        msg = "Permissao de administrador necessaria para registrar servicos Windows."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg, "requer_admin": True}

    servidor = encontrar_servidor(versao)
    if not servidor:
        msg = f"Executavel do servidor FB{versao} nao encontrado."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg}

    cfg     = FB_CONFIGS[versao]
    nome    = cfg["servico_nome"]
    label_v = cfg["label"]
    instsvc = encontrar_instsvc(versao)

    if stop_proc_fn:
        log(f"Parando processos portable ativos do FB{versao} ...")
        stop_proc_fn(versao, log_fn)

    if versao == "3":
        nome_oficial = nome_servico_oficial_fb3()
        if nome_oficial and servico_rodando(nome_oficial):
            log(f"Parando servico oficial FB3 ('{nome_oficial}') ...")
            parar_servico(nome_oficial, log_fn)

    if servico_existe(nome):
        log(f"Removendo servico anterior '{nome}' ...")
        _remover_servico_interno(versao, log_fn)

    log(f"Registrando servico '{nome}' ({label_v}) ...")

    try:
        registrado = False
        if versao == "4":
            instsvc4 = encontrar_instsvc("4")
            if instsvc4:
                r = subprocess.run(
                    [instsvc4, "install", "-auto", "-n", nome],
                    capture_output=True, text=True,
                    encoding="utf-8", errors="ignore",
                    timeout=30, cwd=cfg["dir"],
                )
                if servico_existe(nome):
                    registrado = True
            
            if not registrado:
                fbexe    = encontrar_exe(versao, ["firebird.exe"]) or servidor
                bin_path = f'"{fbexe}" -s'
                subprocess.run(
                    ["sc", "create", nome, f"binPath={bin_path}", f"DisplayName=Futura {label_v}", "start=auto", "type=own"],
                    capture_output=True, timeout=15
                )
                if servico_existe(nome):
                    registrado = True

        else: # FB3
            res = _registrar_fb3_via_wrapper(nome, label_v, servidor, log_fn)
            if res["ok"]:
                registrado = True
            elif instsvc:
                subprocess.run([instsvc, "install", "-auto", "-n", nome], capture_output=True, timeout=30, cwd=cfg["dir"])
                if servico_existe(nome):
                    registrado = True

        if registrado:
            subprocess.run(["sc", "config", nome, "start=", "auto"], capture_output=True, timeout=10)
            subprocess.run(["sc", "description", nome, f"Firebird {versao} Portable gerenciado pelo Futura Setup"], capture_output=True, timeout=10)
            subprocess.run(["sc", "failure", nome, "reset=", "86400", "actions=", "restart/5000/restart/10000//0"], capture_output=True, timeout=10)
            set_fb_modo(versao, "servico")
            return {"ok": True, "erro": ""}
        
        return {"ok": False, "erro": "Nao foi possivel registrar o servico."}

    except Exception as e:
        return {"ok": False, "erro": str(e)}


def _registrar_fb3_via_wrapper(nome: str, label_v: str, servidor: str, log_fn=None) -> dict:
    def log(m):
        if log_fn: log_fn(m)

    if not pywin32_disponivel():
        return {"ok": False, "erro": "pywin32 nao disponivel."}

    wrapper_path = gerar_svc_wrapper("3", servidor, log_fn)
    if not wrapper_path:
        return {"ok": False, "erro": "Falha ao gerar wrapper."}

    python_exe = (getattr(sys, "frozen", False) and __import__("shutil").which("python")) or sys.executable
    try:
        subprocess.run([python_exe, wrapper_path, "--startup", "auto", "install"], capture_output=True, timeout=30)
        if servico_existe(nome):
            return {"ok": True, "erro": ""}
    except Exception:
        pass

    bin_path = f'"{python_exe}" "{wrapper_path}"'
    subprocess.run(["sc", "create", nome, f"binPath={bin_path}", f"DisplayName=Futura {label_v}", "start=auto", "type=own"], capture_output=True, timeout=15)
    if servico_existe(nome):
        return {"ok": True, "erro": ""}

    return {"ok": False, "erro": "Falha ao registrar via wrapper."}


def remover_fb_servico(versao: str, log_fn=None) -> dict:
    def log(m):
        if log_fn: log_fn(m)

    if not is_admin():
        return {"ok": False, "erro": "Admin necessario.", "requer_admin": True}

    nome = FB_CONFIGS[versao]["servico_nome"]
    if not servico_existe(nome):
        set_fb_modo(versao, "processo")
        return {"ok": True, "erro": ""}

    ok = _remover_servico_interno(versao, log_fn)
    if ok:
        set_fb_modo(versao, "processo")
        return {"ok": True, "erro": ""}
    return {"ok": False, "erro": "Falha ao remover servico."}


def _remover_servico_interno(versao: str, log_fn=None) -> bool:
    nome = FB_CONFIGS[versao]["servico_nome"]
    if servico_rodando(nome):
        parar_servico(nome, log_fn)

    wp = get_wrapper_path(versao)
    if versao == "3" and os.path.isfile(wp) and pywin32_disponivel():
        python_exe = (getattr(sys, "frozen", False) and __import__("shutil").which("python")) or sys.executable
        try:
            subprocess.run([python_exe, wp, "remove"], capture_output=True, timeout=15, creationflags=CREATE_NO_WINDOW)
            if not servico_existe(nome): return True
        except Exception: pass

    instsvc = encontrar_instsvc(versao)
    if instsvc and servico_existe(nome):
        subprocess.run([instsvc, "remove", "-n", nome], capture_output=True, timeout=15, cwd=os.path.dirname(instsvc), creationflags=CREATE_NO_WINDOW)
        if not servico_existe(nome): return True

    if not servico_existe(nome): return True
    r = subprocess.run(["sc", "delete", nome], capture_output=True, timeout=15, creationflags=CREATE_NO_WINDOW)
    return r.returncode == 0
