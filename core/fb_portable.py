# =============================================================================
# FUTURA SETUP — Core: Firebird Portable Manager
#
# FB3 → processo portable (porta 3050) OU serviço Windows registrado
# FB4 → processo portable (porta 3050) OU serviço Windows registrado
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
import psutil
from typing import Callable

from config import (
    FB_PORTABLE_CONFIGS, FB3_INSTALLER_URL, FB4_REPO_ARQUIVOS,
    MAX_TENTATIVAS_DOWNLOAD, CREATE_NO_WINDOW
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
# Configurações por versão
# =============================================================================

# Redefine para compatibilidade com o código legado que usa FB_CONFIGS
FB_CONFIGS = FB_PORTABLE_CONFIGS

# Credenciais padrão do Futura
_FB_USER     = "SYSDBA"
_FB_PASSWORD = "sbofutura"

# Senhas padrão de fábrica do Firebird
_SENHAS_FABRICA = ["masterkey", "masterke", ""]

# URL do instalador oficial do FB3 (necessário para gerar o security3.fdb correto)
_FB3_INSTALLER_URL = FB3_INSTALLER_URL

FB4_DIR  = FB_CONFIGS["4"]["dir"]
FB4_GFIX = os.path.join(FB4_DIR, "gfix.exe")
FB4_GBAK = os.path.join(FB4_DIR, "gbak.exe")
FB4_ISQL = os.path.join(FB4_DIR, "isql.exe")

_processos: dict[str, subprocess.Popen | None] = {"3": None, "4": None}

_SERVIDOR_CANDIDATOS = ["firebird.exe", "fbserver.exe"]
_INSTSVC_CANDIDATOS  = ["instsvc.exe"]
_SERVIDOR_SUBDIRS    = ["", "bin"]


# =============================================================================
# Wrapper pywin32 para FB3
# =============================================================================

def _gerar_wrapper(versao: str, fbserver: str, log_fn=None) -> str | None:
    def log(m):
        if log_fn: log_fn(m)

    cfg      = FB_CONFIGS[versao]
    fb_dir   = cfg["dir"]
    svc_name = cfg["servico_nome"]
    svc_lbl  = cfg["label"]
    fbdir    = os.path.dirname(fbserver)

    fbserver_esc = fbserver.replace("\\", "\\\\")
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
        with open(wrapper_path, "w", encoding="utf-8") as f:
            f.write(conteudo)
        log(f"  Wrapper gerado: {wrapper_path}")
        return wrapper_path
    except Exception as e:
        log(f"  ERRO ao gerar wrapper: {e}")
        return None


def _pywin32_disponivel() -> bool:
    try:
        import win32serviceutil  # noqa: F401
        return True
    except ImportError:
        return False


def _wrapper_path(versao: str) -> str:
    return os.path.join(FB_CONFIGS[versao]["dir"], "fb_svc_wrapper.py")


def _servico_binpath_valido(versao: str) -> bool:
    nome   = FB_CONFIGS[versao]["servico_nome"]
    fb_dir = FB_CONFIGS[versao]["dir"].lower()
    try:
        r = subprocess.run(
            ["sc", "qc", nome],
            capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=5,
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
    return _encontrar_exe(versao, _INSTSVC_CANDIDATOS)

def _encontrar_gfix(versao: str) -> str | None:
    return _encontrar_exe(versao, ["gfix.exe"])

def _encontrar_gbak(versao: str) -> str | None:
    return _encontrar_exe(versao, ["gbak.exe"])

def _encontrar_isql(versao: str) -> str | None:
    return _encontrar_exe(versao, ["isql.exe"])

def _encontrar_gsec(versao: str) -> str | None:
    return _encontrar_exe(versao, ["gsec.exe"])


def diagnosticar_instalacao(versao: str = "4") -> dict:
    fb_dir = FB_CONFIGS[versao]["dir"]
    resultado = {
        "dir":      fb_dir,
        "dir_ok":   os.path.isdir(fb_dir),
        "servidor": _encontrar_servidor(versao),
        "instsvc":  _encontrar_instsvc(versao),
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

def fb4_portable_instalado() -> bool: return fb_portable_instalado("4")
def fb3_portable_instalado() -> bool: return fb_portable_instalado("3")


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

def versao_fb4_portable() -> str: return versao_fb_portable("4")
def versao_fb3_portable() -> str: return versao_fb_portable("3")


# =============================================================================
# Inicialização do Security Database
# =============================================================================

def _security_db_path(versao: str) -> str:
    """Retorna o caminho do security DB (exista ou não)."""
    cfg    = FB_CONFIGS[versao]
    fb_dir = cfg["dir"]
    nome   = cfg["security_db"]
    for subdir in _SERVIDOR_SUBDIRS:
        base = os.path.join(fb_dir, subdir) if subdir else fb_dir
        p    = os.path.join(base, nome)
        if os.path.isfile(p):
            return p
    return os.path.join(fb_dir, nome)


def _security_db_incompleto(versao: str) -> bool:
    """
    Verifica funcionalmente se o security DB está no estado 'Install incomplete'
    (arquivo existe e tem tamanho, mas o SYSDBA não foi provisionado).
    Usa gsec -list sem servidor em execução.
    """
    gsec     = _encontrar_gsec(versao)
    sec_path = _security_db_path(versao)
    fb_dir   = FB_CONFIGS[versao]["dir"]

    if not gsec or not os.path.isfile(sec_path):
        return False

    env = os.environ.copy()
    env["FIREBIRD"] = fb_dir

    try:
        r = subprocess.run(
            [gsec, "-database", sec_path, "-user", _FB_USER,
             "-password", "masterkey", "-list"],
            cwd=fb_dir, env=env,
            capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=10,
        )
        saida = (r.stdout + r.stderr).lower()
        return "install incomplete" in saida
    except Exception:
        return False


def _security_db_ok(versao: str) -> bool:
    """
    True se o security DB existe, tem tamanho real (>= 512 KB)
    e NÃO está no estado 'Install incomplete'.
    Arquivos menores foram criados incorretamente e devem ser descartados.
    O arquivo do instalador oficial tem ~1.6-1.7 MB.
    """
    p = _security_db_path(versao)
    if not os.path.isfile(p):
        return False
    try:
        if os.path.getsize(p) < 512 * 1024:
            return False
    except Exception:
        return False
    # Arquivo existe e tem tamanho correto — verifica se está funcional
    return not _security_db_incompleto(versao)


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
    """Retorna True se a saída contém erro real (ignora warnings de configuração)."""
    s = saida.lower()
    for trecho in ["install incomplete", "please read", "compatibility", "release notes"]:
        s = s.replace(trecho, "")
    return any(k in s for k in ["error", "failed", "invalid", "denied", "cannot", "unable"])


def _parar_e_remover_fb3_oficial(log_fn=None):
    """
    Para e desinstala o FB3 oficial caso tenha sido instalado pelo instalador.
    Chamado após copiar o security3.fdb para não deixar serviço residual.
    """
    def log(m):
        if log_fn: log_fn(m)

    # Para todos os serviços oficiais conhecidos
    servicos = [
        "FirebirdServerDefaultInstance",
        "FirebirdGuardianDefaultInstance",
        "FirebirdServer",
        "Firebird",
    ]
    for svc in servicos:
        if _servico_existe(svc):
            log(f"  [FB3] Parando serviço oficial '{svc}' ...")
            subprocess.run(["net", "stop", svc], capture_output=True, timeout=20)
            time.sleep(2)

    # Mata processos residuais do FB3 oficial (em Program Files)
    pf = r"C:\Program Files\Firebird\Firebird_3_0".lower()
    pf86 = r"C:\Program Files (x86)\Firebird\Firebird_3_0".lower()
    for proc in psutil.process_iter(['name', 'exe', 'pid']):
        try:
            name = proc.info['name'].lower()
            if name in ["firebird.exe", "fbserver.exe", "fbguard.exe"]:
                exe_path = proc.info['exe']
                if exe_path:
                    exe_path_l = exe_path.lower()
                    if pf in exe_path_l or pf86 in exe_path_l:
                        pid = proc.info['pid']
                        log(f"  [FB3] Encerrando processo oficial {name} (PID {pid}) ...")
                        proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    time.sleep(2)

    # Tenta desinstalar silenciosamente via unins000.exe
    unins_candidatos = [
        r"C:\Program Files\Firebird\Firebird_3_0\unins000.exe",
        r"C:\Program Files (x86)\Firebird\Firebird_3_0\unins000.exe",
    ]
    for unins in unins_candidatos:
        if os.path.isfile(unins):
            log(f"  [FB3] Desinstalando FB3 oficial ({unins}) ...")
            try:
                subprocess.run(
                    [unins, "/VERYSILENT", "/NORESTART"],
                    capture_output=True, timeout=60,
                    creationflags=CREATE_NO_WINDOW
                )
                time.sleep(3)
                log("  [FB3] FB3 oficial desinstalado.")
            except Exception as e:
                log(f"  [FB3] Desinstalação falhou: {e}")
            break

    # Remove pasta residual se ainda existir
    for pasta in [
        r"C:\Program Files\Firebird\Firebird_3_0",
        r"C:\Program Files (x86)\Firebird\Firebird_3_0",
    ]:
        if os.path.isdir(pasta):
            try:
                shutil.rmtree(pasta, ignore_errors=True)
                log(f"  [FB3] Pasta removida: {pasta}")
            except Exception:
                pass


def _obter_security3_fdb_via_instalador(log_fn=None) -> bool:
    """
    FB3: obtém o security3.fdb correto via instalador oficial.

    O zip portable do FB3 inclui um security3.fdb com tamanho ~1.6MB mas no
    estado 'Install incomplete' — sem SYSDBA provisionado. O arquivo correto
    (~1.7MB) só é gerado pelo instalador oficial .exe.

    IMPORTANTE: usa threshold de 1.5MB para distinguir o arquivo correto
    (instalador oficial >= 1.7MB) do arquivo inválido do zip (~1.6MB mas
    que passa em checagens de tamanho menores).

    Fluxo:
      1. Verifica se já existe instalação oficial em Program Files → copia
      2. Se não, baixa o instalador .exe (~10MB) e executa silenciosamente
         (o instalador ignora /DIR e sempre instala em Program Files)
      3. Copia o security3.fdb de Program Files para C:\\FuturaFirebird\\FB3\\
      4. Para e desinstala o FB3 oficial que foi instalado no passo 2
    """
    def log(m):
        if log_fn: log_fn(m)

    fb_dir   = FB_CONFIGS["3"]["dir"]
    dst_path = os.path.join(fb_dir, "security3.fdb")

    _CANDIDATOS_SISTEMA = [
        r"C:\Program Files\Firebird\Firebird_3_0\security3.fdb",
        r"C:\Program Files (x86)\Firebird\Firebird_3_0\security3.fdb",
    ]

    def _copiar_de_program_files() -> bool:
        for src in _CANDIDATOS_SISTEMA:
            if os.path.isfile(src) and os.path.getsize(src) >= 1_500_000:
                log(f"  [FB3] security3.fdb encontrado: {src} ({os.path.getsize(src):,} bytes)")
                try:
                    shutil.copy2(src, dst_path)
                    log(f"  [FB3] Copiado para FB3 dir ({os.path.getsize(dst_path):,} bytes).")
                    return True
                except Exception as e:
                    log(f"    cópia falhou: {e}")
        return False

    # ── Passo 1: instalação oficial já existente no sistema ──────────────
    if _copiar_de_program_files():
        return True
    # ─────────────────────────────────────────────────────────────────────

    # ── Passo 2: baixa e executa o instalador oficial ────────────────────
    log("  [FB3] Instalação oficial não encontrada — baixando instalador FB3 (~10MB) ...")
    installer_path = os.path.join(tempfile.gettempdir(), "fb3_setup_futura.exe")

    instalador_executado = False
    try:
        def _tentar_download():
            req = urllib.request.Request(
                _FB3_INSTALLER_URL,
                headers={"User-Agent": "FuturaSetup/4.3"}
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                with open(installer_path, "wb") as f:
                    shutil.copyfileobj(resp, f)
            return True

        tentativas = 0
        sucesso = False
        while tentativas < MAX_TENTATIVAS_DOWNLOAD:
            try:
                if _tentar_download():
                    sucesso = True
                    break
            except Exception as e:
                tentativas += 1
                log(f"    Falha no download (tentativa {tentativas}/{MAX_TENTATIVAS_DOWNLOAD}): {e}")
                if tentativas < MAX_TENTATIVAS_DOWNLOAD:
                    time.sleep(2)
        
        if not sucesso:
            log("  [FB3] Falha definitiva no download do instalador.")
            return False

        log(f"  [FB3] Instalador baixado ({os.path.getsize(installer_path):,} bytes).")

        log("  [FB3] Executando instalador silenciosamente ...")
        subprocess.run(
            [installer_path, "/VERYSILENT", "/NOICONS", '/TASKS=""', "/NORESTART"],
            capture_output=True, timeout=120,
        )
        instalador_executado = True
        time.sleep(5)

        # ── Passo 3: copia o security3.fdb de Program Files ──────────────
        if _copiar_de_program_files():
            return True

        log("  [FB3] security3.fdb não encontrado após instalação.")

    except Exception as e:
        log(f"  [FB3] Erro ao obter security3.fdb via instalador: {e}")
    finally:
        try:
            if os.path.isfile(installer_path):
                os.remove(installer_path)
        except Exception:
            pass
        # ── Passo 4: para e desinstala o FB3 oficial instalado ───────────
        if instalador_executado:
            log("  [FB3] Removendo FB3 oficial instalado temporariamente ...")
            _parar_e_remover_fb3_oficial(log_fn)

    return False


def _configurar_sysdba_fb3_via_gsec(log_fn=None) -> bool:
    """
    FB3: altera a senha do SYSDBA via gsec -database.
    Funciona sem servidor rodando, direto no arquivo.
    Requer que o security3.fdb seja o arquivo real do instalador oficial.
    """
    def log(m):
        if log_fn: log_fn(m)

    gsec     = _encontrar_gsec("3")
    sec_path = _security_db_path("3")
    fb_dir   = FB_CONFIGS["3"]["dir"]

    if not gsec:
        log("  [FB3] gsec.exe não encontrado.")
        return False
    if not os.path.isfile(sec_path):
        log("  [FB3] security3.fdb não encontrado.")
        return False

    env = os.environ.copy()
    env["FIREBIRD"] = fb_dir

    log("  [FB3] Configurando SYSDBA via gsec -database ...")

    for senha_atual in _SENHAS_FABRICA:
        cmd = [gsec, "-database", sec_path, "-user", _FB_USER]
        if senha_atual:
            cmd += ["-password", senha_atual]
        cmd += ["-modify", _FB_USER, "-pw", _FB_PASSWORD]

        try:
            r = subprocess.run(
                cmd, cwd=fb_dir, env=env,
                capture_output=True, text=True,
                encoding="utf-8", errors="ignore", timeout=15,
            )
            saida = (r.stdout + r.stderr).strip()
            if saida:
                log(f"    gsec (pw={senha_atual!r}): {saida[:200]}")
            if r.returncode == 0 and not _contem_erro_fatal(saida):
                log(f"  [FB3] SYSDBA configurado (senha anterior: {senha_atual!r}).")
                return True
        except Exception as e:
            log(f"    gsec erro: {e}")

    return False


def _configurar_sysdba_fb4_via_gsec(log_fn=None) -> bool:
    """
    FB4: tenta configurar SYSDBA via gsec -database (sem servidor).
    Na prática o FB4 portable não suporta bem esse modo — use
    _inicializar_security_fb4_via_isql_embedded como método principal.
    Mantido como fallback para compatibilidade.
    """
    def log(m):
        if log_fn: log_fn(m)

    gsec     = _encontrar_gsec("4")
    sec_path = _security_db_path("4")
    fb_dir   = FB_CONFIGS["4"]["dir"]

    if not gsec or not os.path.isfile(sec_path):
        return False

    env = os.environ.copy()
    env["FIREBIRD"] = fb_dir

    for senha_atual in _SENHAS_FABRICA:
        cmd = [gsec, "-database", sec_path, "-user", _FB_USER]
        if senha_atual:
            cmd += ["-password", senha_atual]
        cmd += ["-modify", _FB_USER, "-pw", _FB_PASSWORD]
        try:
            r = subprocess.run(
                cmd, cwd=fb_dir, env=env,
                capture_output=True, text=True,
                encoding="utf-8", errors="ignore", timeout=15,
            )
            saida = (r.stdout + r.stderr).strip()
            if saida:
                log(f"    gsec FB4 (pw={senha_atual!r}): {saida[:200]}")
            if r.returncode == 0 and not _contem_erro_fatal(saida):
                log(f"  [FB4] SYSDBA configurado via gsec.")
                return True
        except Exception as e:
            log(f"    gsec FB4 erro: {e}")
    return False


def _inicializar_security_fb4_via_isql_embedded(log_fn=None) -> bool:
    """
    FB4: inicializa o security4.fdb do zero via isql embedded.

    O zip portable do FB4 inclui um security4.fdb no estado 'Install incomplete'.
    A solução correta conforme README.security_database.txt do FB4:
      1. Para o servidor se estiver rodando
      2. Deleta o security4.fdb inválido
      3. Cria um novo security4.fdb via isql embedded (CREATE DATABASE)
      4. Conecta nele e executa CREATE USER SYSDBA PASSWORD '...'

    Não requer servidor rodando — usa conexão embedded direta no arquivo.
    """
    def log(m):
        if log_fn: log_fn(m)

    isql   = _encontrar_isql("4")
    fb_dir = FB_CONFIGS["4"]["dir"]
    sec_path = os.path.join(fb_dir, "security4.fdb")

    if not isql:
        log("  [FB4] isql.exe não encontrado.")
        return False

    env = os.environ.copy()
    env["FIREBIRD"] = fb_dir

    # Passo 1: remove security4.fdb inválido
    if os.path.isfile(sec_path):
        log("  [FB4] Removendo security4.fdb inválido ...")
        try:
            os.remove(sec_path)
        except Exception as e:
            log(f"    falha ao remover: {e}")
            return False

    # Passo 2: cria novo security4.fdb via isql embedded + CREATE USER
    log("  [FB4] Criando security4.fdb e usuário SYSDBA via isql embedded ...")
    sql = (
        f"CREATE DATABASE '{sec_path}';\n"
        f"CREATE USER {_FB_USER} PASSWORD '{_FB_PASSWORD}';\n"
        "EXIT;\n"
    )
    try:
        r = subprocess.run(
            [isql, "-user", _FB_USER],
            input=sql,
            cwd=fb_dir, env=env,
            capture_output=True, text=True,
            encoding="utf-8", errors="ignore",
            timeout=30,
        )
        saida = (r.stdout + r.stderr).strip()
        if saida:
            log(f"    isql embedded: {saida[:300]}")

        # Verifica se o arquivo foi criado
        if not os.path.isfile(sec_path):
            log("  [FB4] security4.fdb não foi criado.")
            return False

        # Verifica se o SYSDBA foi criado conectando no arquivo
        r2 = subprocess.run(
            [isql, "-user", _FB_USER, "-password", _FB_PASSWORD, sec_path],
            input="SELECT SEC$USER_NAME FROM SEC$USERS;\nEXIT;\n",
            cwd=fb_dir, env=env,
            capture_output=True, text=True,
            encoding="utf-8", errors="ignore",
            timeout=15,
        )
        saida2 = (r2.stdout + r2.stderr)
        if "SYSDBA" in saida2.upper():
            log(f"  [FB4] security4.fdb criado com SYSDBA ({os.path.getsize(sec_path):,} bytes).")
            return True
        else:
            log(f"  [FB4] SYSDBA não encontrado no security4.fdb: {saida2[:200]}")
            return False

    except Exception as e:
        log(f"  [FB4] isql embedded erro: {e}")
        return False


def _configurar_sysdba_fb4_via_isql(log_fn=None) -> bool:
    """
    FB4: o security4.fdb já vem no zip com masterkey.
    Sobe o servidor temporariamente e altera a senha via isql TCP.
    Usado como fallback quando gsec -database não funciona.
    """
    def log(m):
        if log_fn: log_fn(m)

    isql     = _encontrar_isql("4")
    servidor = _encontrar_servidor("4")
    sec_path = _security_db_path("4")
    porta    = FB_CONFIGS["4"]["porta"]
    fb_dir   = FB_CONFIGS["4"]["dir"]

    if not isql or not servidor:
        log("  [FB4] isql.exe ou servidor não encontrado.")
        return False

    log("  [FB4] Configurando SYSDBA via isql TCP ...")

    proc_tmp = None
    if not _processo_rodando("4"):
        log("  [FB4] Subindo servidor temporário ...")
        env = os.environ.copy()
        env["FIREBIRD"] = fb_dir
        try:
            proc_tmp = subprocess.Popen(
                [servidor, "-a"], cwd=fb_dir,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env,
            )
            time.sleep(5)
        except Exception as e:
            log(f"    servidor temp erro: {e}")

    ok = False
    for senha_atual in ["masterkey", "masterke"]:
        sql = f"ALTER USER {_FB_USER} PASSWORD '{_FB_PASSWORD}';\nCOMMIT;\nQUIT;\n"
        try:
            r = subprocess.run(
                [
                    isql,
                    f"localhost/{porta}:{sec_path}",
                    "-user", _FB_USER,
                    "-password", senha_atual,
                ],
                input=sql, cwd=fb_dir,
                capture_output=True, text=True,
                encoding="utf-8", errors="ignore", timeout=20,
            )
            saida = (r.stdout + r.stderr).strip()
            if saida:
                log(f"    isql FB4 (pw={senha_atual!r}): {saida[:200]}")
            if r.returncode == 0 and not _contem_erro_fatal(saida):
                log(f"  [FB4] SYSDBA configurado (senha anterior: {senha_atual!r}).")
                ok = True
                break
        except Exception as e:
            log(f"    isql FB4 erro: {e}")

    if proc_tmp:
        try:
            proc_tmp.terminate()
            proc_tmp.wait(timeout=5)
        except Exception:
            pass

    return ok


def inicializar_security_db(versao: str, log_fn=None) -> bool:
    """
    Garante que o security database existe e o SYSDBA tem a senha correta.
    Chamado na instalação e antes de cada ativação.

    FB3:
      1. Obtém o security3.fdb correto via instalador oficial
         (copia de instalação existente OU baixa e extrai o .exe)
      2. Configura SYSDBA via gsec -database (sem precisar de servidor)

    FB4:
      1. Remove security4.fdb inválido/incompleto se existir
         (estado 'Install incomplete' — zip portable não inicializa corretamente)
      2. Tenta configurar SYSDBA via gsec -database (sem servidor)
      3. Fallback: configura via isql TCP (sobe servidor temporário)
    """
    def log(m):
        if log_fn: log_fn(m)

    if _sysdba_configurado(versao) and _security_db_ok(versao):
        log(f"  Security database FB{versao} OK (já configurado).")
        return True

    label = FB_CONFIGS[versao]["label"]
    log(f"Inicializando security database do {label} ...")

    ok = False

    if versao == "3":
        sec_path = _security_db_path("3")

        # Remove o security3.fdb do zip portable se existir — ele tem tamanho
        # normal (~1.6MB) mas está no estado 'Install incomplete'. O arquivo
        # correto (~1.7MB) só vem do instalador oficial e tem >= 1.5MB.
        # Sempre substitui para garantir que é o arquivo correto.
        if os.path.isfile(sec_path):
            tamanho = os.path.getsize(sec_path)
            if tamanho < 1_500_000:
                log(f"  [FB3] security3.fdb com tamanho suspeito ({tamanho:,} bytes) — removendo ...")
                try:
                    os.remove(sec_path)
                except Exception:
                    pass
            elif _security_db_incompleto("3"):
                log("  [FB3] security3.fdb com 'Install incomplete' — substituindo pelo do instalador oficial ...")
                try:
                    os.remove(sec_path)
                except Exception:
                    pass

        # Obtém o security3.fdb correto via instalador oficial
        if not os.path.isfile(sec_path) or not _security_db_ok("3"):
            _obter_security3_fdb_via_instalador(log_fn)

        # Configura SYSDBA
        if _security_db_ok("3"):
            ok = _configurar_sysdba_fb3_via_gsec(log_fn)
        else:
            log("  [FB3] Não foi possível obter o security3.fdb.")

    else:  # versao == "4"
        # FB4: o security4.fdb do zip está sempre no estado 'Install incomplete'.
        # A solução correta é recriar do zero via isql embedded (sem servidor).
        # Conforme README.security_database.txt do próprio FB4.
        log("  [FB4] Inicializando security4.fdb via isql embedded ...")
        ok = _inicializar_security_fb4_via_isql_embedded(log_fn)

        # Fallback: via isql TCP (sobe servidor temporário)
        if not ok:
            log("  [FB4] Fallback: configurando SYSDBA via isql TCP ...")
            ok = _configurar_sysdba_fb4_via_isql(log_fn)

    if ok:
        _marcar_sysdba_ok(versao)
        log(f"  Security database {label} configurado com sucesso.")
        log(f"  Usuário: {_FB_USER}  |  Senha: {_FB_PASSWORD}")
    else:
        log(
            f"  AVISO: não foi possível configurar o SYSDBA automaticamente.\n"
            f"  Corrija manualmente:\n"
            f"    cd C:\\FuturaFirebird\\FB{versao}\n"
            f"    gsec.exe -database security{versao}.fdb "
            f"-user SYSDBA -password masterkey -modify SYSDBA -pw {_FB_PASSWORD}"
        )

    return ok


# =============================================================================
# Serviço Windows — utilitários genéricos
# =============================================================================

def _servico_existe(nome: str) -> bool:
    try:
        r = subprocess.run(["sc", "query", nome],
                           capture_output=True, text=True, timeout=5,
                           creationflags=CREATE_NO_WINDOW)
        return r.returncode == 0
    except Exception:
        return False


def _servico_rodando(nome: str) -> bool:
    try:
        r = subprocess.run(["sc", "query", nome],
                           capture_output=True, text=True, timeout=5,
                           creationflags=CREATE_NO_WINDOW)
        return "RUNNING" in r.stdout
    except Exception:
        return False


def _servico_desabilitado(nome: str) -> bool:
    try:
        r = subprocess.run(["sc", "qc", nome],
                           capture_output=True, text=True, timeout=5,
                           creationflags=CREATE_NO_WINDOW)
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
            creationflags=CREATE_NO_WINDOW,
        )
        saida = (r.stdout + r.stderr).strip()
        if saida:
            log(f"  net start: {saida[:400]}")
        for _ in range(20):
            time.sleep(1)
            if _servico_rodando(nome):
                return True
        try:
            sq = subprocess.run(["sc", "query", nome],
                                capture_output=True, text=True, timeout=5)
            log(f"  sc query: {sq.stdout.strip()[:300]}")
        except Exception:
            pass
        try:
            ev = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-EventLog -LogName System -Source '*Firebird*','*Service*' "
                 "-Newest 5 -ErrorAction SilentlyContinue | "
                 "Select-Object TimeGenerated,EntryType,Message | "
                 "Format-List"],
                capture_output=True, text=True,
                encoding="utf-8", errors="ignore", timeout=10,
            )
            if ev.stdout.strip():
                log(f"  EventLog:\n{ev.stdout.strip()[:600]}")
        except Exception:
            pass
    except subprocess.TimeoutExpired:
        log(f"  net start timeout ({timeout_s}s).")
    except Exception as e:
        log(f"Erro ao iniciar servico '{nome}': {e}")
    return False


def _servico_parar(nome: str, log_fn=None, timeout_s: int = 30) -> bool:
    def log(m):
        if log_fn: log_fn(m)
    try:
        subprocess.run(["net", "stop", nome], capture_output=True, timeout=timeout_s,
                       creationflags=CREATE_NO_WINDOW)
        for _ in range(20):
            time.sleep(1)
            if not _servico_rodando(nome):
                return True
    except Exception as e:
        log(f"Erro ao parar servico '{nome}': {e}")
    return False


# =============================================================================
# Serviço oficial FB3
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
# Modo de execução
# =============================================================================

def _modo_path(versao: str) -> str:
    return os.path.join(FB_CONFIGS[versao]["dir"], f".fb{versao}_modo")


def fb_obter_modo(versao: str) -> str:
    if _servico_existe(FB_CONFIGS[versao]["servico_nome"]):
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
# Flag habilitado/desabilitado
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
# Serviço Windows Futura
# =============================================================================

def fb_servico_existe(versao: str) -> bool:
    return _servico_existe(FB_CONFIGS[versao]["servico_nome"])

def fb_servico_rodando(versao: str) -> bool:
    return _servico_rodando(FB_CONFIGS[versao]["servico_nome"])


def registrar_fb_servico(versao: str, log_fn=None) -> dict:
    def log(m):
        if log_fn: log_fn(m)

    if not is_admin():
        msg = "Permissao de administrador necessaria para registrar servicos Windows."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg, "requer_admin": True}

    if not fb_portable_instalado(versao):
        msg = f"FB{versao} Portable nao esta instalado."
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
    instsvc = _encontrar_instsvc(versao)

    log(f"Diagnostico FB{versao}:")
    log(f"  servidor : {servidor}")
    log(f"  instsvc  : {instsvc if instsvc else 'NAO ENCONTRADO'}")
    log(f"  fb_dir   : {cfg['dir']}")
    log(f"  pywin32  : {'disponivel' if _pywin32_disponivel() else 'NAO DISPONIVEL'}")

    if _processo_rodando(versao):
        log(f"Parando processo portable do FB{versao} ...")
        _parar_processo(versao, log_fn)

    if versao == "3":
        nome_oficial = _nome_servico_oficial_fb3()
        if nome_oficial and _servico_rodando(nome_oficial):
            log(f"Parando servico oficial FB3 ('{nome_oficial}') ...")
            _servico_parar(nome_oficial, log_fn)

    if _servico_existe(nome):
        log(f"Removendo servico anterior '{nome}' ...")
        _remover_servico_interno(versao, log_fn)

    log(f"Registrando servico '{nome}' ({label_v}) ...")
    log(f"  Executavel: {servidor}")

    try:
        registrado = False

        if versao == "4":
            # FB4: usa instsvc.exe nativo que configura corretamente o serviço
            instsvc4 = _encontrar_instsvc("4")
            if instsvc4:
                log(f"  FB4: registrando via instsvc.exe nativo ...")
                r = subprocess.run(
                    [instsvc4, "install", "-auto", "-n", nome],
                    capture_output=True, text=True,
                    encoding="utf-8", errors="ignore",
                    timeout=30, cwd=cfg["dir"],
                )
                saida = (r.stdout + r.stderr).strip()
                if saida:
                    log(f"    instsvc: {saida[:300]}")
                if _servico_existe(nome):
                    registrado = True
                    log(f"  Registrado via instsvc.exe (FB4) com nome '{nome}'.")
                else:
                    # Fallback: sc create
                    log("  Fallback FB4: sc create ...")
                    fbexe    = _encontrar_exe(versao, ["firebird.exe"]) or servidor
                    bin_path = f'"{fbexe}" -s'
                    r2 = subprocess.run(
                        ["sc", "create", nome,
                         f"binPath={bin_path}",
                         f"DisplayName=Futura {label_v}",
                         "start=auto", "type=own"],
                        capture_output=True, text=True,
                        encoding="utf-8", errors="ignore", timeout=15,
                    )
                    saida2 = (r2.stdout + r2.stderr).strip()
                    if saida2:
                        log(f"  sc create: {saida2[:300]}")
                    if r2.returncode == 0 and _servico_existe(nome):
                        registrado = True
                        log(f"  Registrado via sc create (FB4).")
                    else:
                        return {"ok": False, "erro": (
                            f"Nao foi possivel registrar o servico FB4. "
                            f"instsvc rc={r.returncode}, sc create rc={r2.returncode}"
                        )}
            else:
                # Sem instsvc, usa sc create direto
                fbexe    = _encontrar_exe(versao, ["firebird.exe"]) or servidor
                bin_path = f'"{fbexe}" -s'
                r = subprocess.run(
                    ["sc", "create", nome,
                     f"binPath={bin_path}",
                     f"DisplayName=Futura {label_v}",
                     "start=auto", "type=own"],
                    capture_output=True, text=True,
                    encoding="utf-8", errors="ignore", timeout=15,
                )
                saida = (r.stdout + r.stderr).strip()
                if saida:
                    log(f"  sc create: {saida[:300]}")
                if r.returncode == 0 and _servico_existe(nome):
                    registrado = True
                    log(f"  Registrado via sc create (FB4).")
                else:
                    return {"ok": False, "erro": (
                        f"Nao foi possivel registrar o servico FB4. "
                        f"sc create rc={r.returncode}: {saida}"
                    )}

        else:
            log("  FB3: wrapper pywin32")
            res = _registrar_fb3_via_wrapper(nome, label_v, servidor, log_fn)
            if res["ok"]:
                registrado = True
                nome = FB_CONFIGS[versao]["servico_nome"]
            else:
                if instsvc:
                    log("  Fallback FB3: instsvc.exe")
                    r = subprocess.run(
                        [instsvc, "install", "-auto", "-n", nome],
                        capture_output=True, text=True,
                        encoding="utf-8", errors="ignore",
                        timeout=30, cwd=os.path.dirname(servidor),
                    )
                    saida = (r.stdout + r.stderr).strip()
                    if saida:
                        log(f"    instsvc: {saida[:300]}")
                    if _servico_existe(nome):
                        registrado = True
                        log("  Registrado via instsvc.exe (fallback).")
                if not registrado:
                    return res

        if not _servico_existe(nome):
            return {"ok": False, "erro": "Servico nao foi criado."}

        subprocess.run(["sc", "config",      nome, "start=", "auto"],
                       capture_output=True, timeout=10)
        subprocess.run(["sc", "description", nome,
                        f"Firebird {versao} Portable gerenciado pelo Futura Setup"],
                       capture_output=True, timeout=10)
        subprocess.run(["sc", "failure", nome, "reset=", "86400",
                        "actions=", "restart/5000/restart/10000//0"],
                       capture_output=True, timeout=10)

        _fb_salvar_modo(versao, "servico")
        log(f"Servico '{nome}' registrado com sucesso (start=auto, porta {cfg['porta']}).")
        return {"ok": True, "erro": ""}

    except Exception as e:
        log(f"Erro: {e}")
        return {"ok": False, "erro": str(e)}


def _registrar_fb3_via_wrapper(nome: str, label_v: str, servidor: str, log_fn=None) -> dict:
    def log(m):
        if log_fn: log_fn(m)

    if not _pywin32_disponivel():
        msg = ("pywin32 nao disponivel. "
               "Instale: pip install pywin32 && python -m pywin32_postinstall -install")
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg}

    wrapper_path = _gerar_wrapper("3", servidor, log_fn)
    if not wrapper_path:
        return {"ok": False, "erro": "Falha ao gerar wrapper pywin32."}

    python_exe = sys.executable
    log(f"  Python exe: {python_exe}")
    log(f"  Wrapper   : {wrapper_path}")

    log("  Instalando via HandleCommandLine ...")
    try:
        r = subprocess.run(
            [python_exe, wrapper_path, "--startup", "auto", "install"],
            capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=30,
        )
        saida = (r.stdout + r.stderr).strip()
        if saida:
            log(f"    wrapper install: {saida[:300]}")
        if _servico_existe(nome):
            log("  Registrado via HandleCommandLine.")
            return {"ok": True, "erro": ""}
    except Exception as e:
        log(f"  HandleCommandLine falhou: {e}")

    log("  Fallback: sc create com python.exe + wrapper ...")
    bin_path = f'"{python_exe}" "{wrapper_path}"'
    r2 = subprocess.run(
        [
            "sc", "create", nome,
            f"binPath={bin_path}",
            f"DisplayName=Futura {label_v}",
            "start=auto", "type=own",
        ],
        capture_output=True, text=True,
        encoding="utf-8", errors="ignore", timeout=15,
    )
    saida2 = (r2.stdout + r2.stderr).strip()
    if saida2:
        log(f"  sc create: {saida2[:300]}")
    if r2.returncode == 0 and _servico_existe(nome):
        log("  Registrado via sc create + wrapper pywin32.")
        return {"ok": True, "erro": ""}

    return {"ok": False, "erro": (
        f"Nao foi possivel registrar FB3 via wrapper. "
        f"sc create rc={r2.returncode}: {saida2}"
    )}


def _remover_servico_interno(versao: str, log_fn=None) -> bool:
    def log(m):
        if log_fn: log_fn(m)

    nome = FB_CONFIGS[versao]["servico_nome"]
    if _servico_rodando(nome):
        subprocess.run(["net", "stop", nome], capture_output=True, timeout=30)
        time.sleep(2)

    wp = _wrapper_path(versao)
    if versao == "3" and os.path.isfile(wp) and _pywin32_disponivel():
        try:
            r = subprocess.run(
                [sys.executable, wp, "remove"],
                capture_output=True, text=True,
                encoding="utf-8", errors="ignore", timeout=15,
                creationflags=CREATE_NO_WINDOW,
            )
            saida = (r.stdout + r.stderr).strip()
            if saida:
                log(f"  wrapper remove: {saida[:200]}")
            if not _servico_existe(nome):
                log(f"Servico '{nome}' removido via wrapper.")
                time.sleep(1)
                return True
        except Exception as e:
            log(f"  wrapper remove falhou: {e}")

    instsvc = _encontrar_instsvc(versao)
    if instsvc and _servico_existe(nome):
        r = subprocess.run(
            [instsvc, "remove", "-n", nome],
            capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=15,
            cwd=os.path.dirname(instsvc),
            creationflags=CREATE_NO_WINDOW,
        )
        saida = (r.stdout + r.stderr).strip()
        if saida:
            log(f"  instsvc remove: {saida[:200]}")
        if not _servico_existe(nome):
            log(f"Servico '{nome}' removido via instsvc.")
            time.sleep(1)
            return True

    if not _servico_existe(nome):
        return True
    r2 = subprocess.run(["sc", "delete", nome], capture_output=True, text=True, timeout=15,
                        creationflags=CREATE_NO_WINDOW)
    if r2.returncode == 0:
        log(f"Servico '{nome}' removido.")
        time.sleep(1)
        return True
    log(f"AVISO ao remover: {(r2.stdout + r2.stderr).strip()}")
    return False


def remover_fb_servico(versao: str, log_fn=None) -> dict:
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
    def log(m):
        if log_fn: log_fn(m)
    if not is_admin():
        msg = "Permissao de administrador necessaria."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg, "requer_admin": True}

    log(f"Verificando security database do FB{versao} ...")
    inicializar_security_db(versao, log_fn)

    nome = FB_CONFIGS[versao]["servico_nome"]

    if not _servico_existe(nome):
        log("Servico nao registrado — registrando agora ...")
        r = registrar_fb_servico(versao, log_fn)
        if not r["ok"]:
            return r
        nome = FB_CONFIGS[versao]["servico_nome"]
    elif not _servico_binpath_valido(versao):
        log(f"Servico '{nome}' com binPath incompativel. Recriando ...")
        r = registrar_fb_servico(versao, log_fn)
        if not r["ok"]:
            return r
        nome = FB_CONFIGS[versao]["servico_nome"]
    else:
        log(f"Servico '{nome}' com binPath valido — prosseguindo.")

    if _servico_desabilitado(nome):
        log(f"Habilitando servico '{nome}' ...")
        subprocess.run(["sc", "config", nome, "start=", "auto"], capture_output=True, timeout=10)

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
    def log(m):
        if log_fn: log_fn(m)
    if not is_admin():
        msg = "Permissao de administrador necessaria."
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg, "requer_admin": True}
    nome = FB_CONFIGS[versao]["servico_nome"]
    if not _servico_existe(nome):
        log(f"Servico Futura '{nome}' nao estava registrado.")
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
# Processo portable
# =============================================================================

def _processo_rodando(versao: str) -> bool:
    proc = _processos.get(versao)
    if proc is not None and proc.poll() is None:
        return True
    fb_dir = FB_CONFIGS[versao]["dir"].lower()
    # Usando psutil para detecção mais moderna e performática
    for proc in psutil.process_iter(['name', 'exe']):
        try:
            if proc.info['name'].lower() in _SERVIDOR_CANDIDATOS:
                exe = proc.info['exe']
                if exe and fb_dir in exe.lower():
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
        msg = f"{outra_lbl} está ativo. Inative-o antes de ativar o {esta_lbl}."
        log(f"BLOQUEADO: {msg}")
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

        ver = versao_fb_portable(versao)
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
            return # Sucesso
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

    # ── Porta 3050 já é o padrão oficial — nenhuma correção necessária ──────────
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
    resultado = {"executado": False, "ok": False, "erros": [], "avisos": [], "saida_bruta": "", "msg": ""}
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

    fb_dir   = FB_CONFIGS[versao]["dir"]
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
            idx       = conteudo.index(marcador)
            cabecalho = conteudo[:idx]
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