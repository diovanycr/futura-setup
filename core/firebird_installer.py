# =============================================================================
# FUTURA SETUP — Core: Instalar Firebird
# Toda a lógica de negócio: detecção, download, instalação, permissões, conf.
# Salvar em: core/firebird_installer.py
# =============================================================================

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal

from core.logger import log

# =============================================================================
# Utilitários
# =============================================================================

def _is_admin() -> bool:
    """Retorna True se o processo atual tem privilégios de administrador."""
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# =============================================================================
# Constantes públicas (consumidas pela UI)
# =============================================================================
is_admin = _is_admin  # alias público para uso na UI


def elevar_como_admin() -> bool:
    """
    Relança o processo atual com privilégios de administrador via ShellExecute runas.
    Retorna True se o pedido de elevação foi enviado (UAC exibido).
    O processo atual deve ser encerrado após chamar esta função.
    """
    import ctypes
    import sys
    try:
        args = " ".join(f'"{a}"' for a in sys.argv)
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,            # hwnd
            "runas",         # operação — solicita elevação UAC
            sys.executable,  # python.exe ou executável compilado
            args,            # argumentos originais
            None,            # diretório de trabalho (None = atual)
            1,               # SW_SHOWNORMAL
        )
        return int(ret) > 32  # > 32 = sucesso no ShellExecuteW
    except Exception:
        return False


FB_URLS: dict[str, dict[str, str]] = {
    "3": {
        "x64": "https://github.com/FirebirdSQL/firebird/releases/download/v3.0.13/Firebird-3.0.13.33818-0-x64.exe",
        "x86": "https://github.com/FirebirdSQL/firebird/releases/download/v3.0.13/Firebird-3.0.13.33818-0-Win32.exe",
    },
    "4": {
        "x64": "https://github.com/FirebirdSQL/firebird/releases/download/v4.0.6/Firebird-4.0.6.3221-0-x64.exe",
        "x86": "https://github.com/FirebirdSQL/firebird/releases/download/v4.0.6/Firebird-4.0.6.3221-0-Win32.exe",
    },
}

FB_LABEL: dict[str, str] = {
    "3": "Firebird 3.0.13",
    "4": "Firebird 4.0.6",
}

# URLs dos arquivos de configuração Futura para Firebird 4
_FB4_CONF_FILES: list[tuple[str, str]] = [
    (
        "https://repositorio.futurasistemas.com.br/download.php"
        "?dirfisico=D:/Backup//repositorio//30%20-%20Firebird%204.0/Conf/Usuarios.sql"
        "&caminho=https://repositorio.futurasistemas.com.br/repositorio/30%20-%20Firebird%204.0/Conf/Usuarios.sql"
        "&filename=Usuarios.sql",
        "Usuarios.sql",
    ),
    (
        "https://repositorio.futurasistemas.com.br/download.php"
        "?dirfisico=D:/Backup//repositorio//30%20-%20Firebird%204.0/Conf/databases.conf"
        "&caminho=https://repositorio.futurasistemas.com.br/repositorio/30%20-%20Firebird%204.0/Conf/databases.conf"
        "&filename=databases.conf",
        "databases.conf",
    ),
    (
        "https://repositorio.futurasistemas.com.br/download.php"
        "?dirfisico=D:/Backup//repositorio//30%20-%20Firebird%204.0/Conf/firebird.conf"
        "&caminho=https://repositorio.futurasistemas.com.br/repositorio/30%20-%20Firebird%204.0/Conf/firebird.conf"
        "&filename=firebird.conf",
        "firebird.conf",
    ),
]

# =============================================================================
# Funções utilitárias públicas
# =============================================================================

def detect_arch() -> str:
    """Retorna 'x64' ou 'x86' baseado na arquitetura real do Windows."""
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        return "x64"
    if os.environ.get("PROCESSOR_ARCHITEW6432", "").lower() in ("amd64", "ia64"):
        return "x64"
    if os.environ.get("PROCESSOR_ARCHITECTURE", "").lower() in ("amd64", "ia64"):
        return "x64"
    return "x86"


def check_installed_firebird() -> dict | None:
    """
    Detecta instalação do Firebird via múltiplas estratégias:
      1. Registro: chave própria do Firebird Project
      2. Registro: varredura completa de Uninstall
      3. Serviço do Windows (sc query)
      4. Pastas padrão no disco

    Retorna dict {version, path, uninstall_string} ou None.
    """
    try:
        import winreg
    except ImportError:
        return None

    info: dict[str, str] = {"version": "", "path": "", "uninstall_string": ""}

    # ── 1. Chave própria do Firebird ──────────────────────────────────────────
    for hive, key_path in [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Firebird Project\Firebird Server\Instances"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Firebird Project\Firebird Server\Instances"),
    ]:
        try:
            with winreg.OpenKey(hive, key_path) as k:
                info["path"] = winreg.QueryValueEx(k, "DefaultInstance")[0]
        except Exception:
            pass

    # ── 2. Varredura Uninstall ────────────────────────────────────────────────
    for hive, uninst_root in [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]:
        try:
            with winreg.OpenKey(hive, uninst_root) as root:
                i = 0
                while True:
                    try:
                        sub_name = winreg.EnumKey(root, i)
                        i += 1
                    except OSError:
                        break
                    try:
                        with winreg.OpenKey(root, sub_name) as sub:
                            try:
                                display = winreg.QueryValueEx(sub, "DisplayName")[0]
                            except Exception:
                                display = ""
                            if "firebird" not in sub_name.lower() and \
                               "firebird" not in display.lower():
                                continue
                            try:
                                uninst = winreg.QueryValueEx(sub, "UninstallString")[0]
                            except Exception:
                                continue
                            try:
                                ver = winreg.QueryValueEx(sub, "DisplayVersion")[0]
                            except Exception:
                                ver = ""
                            info["version"]          = ver or display or sub_name
                            info["uninstall_string"] = uninst.strip('"').strip()
                            return info
                    except Exception:
                        continue
        except Exception:
            pass

    # ── 3. Serviço do Windows ─────────────────────────────────────────────────
    for svc in ["FirebirdServerDefaultInstance", "FirebirdGuardianDefaultInstance",
                "FirebirdServer", "FirebirdGuardian"]:
        try:
            result = subprocess.run(
                ["sc", "query", svc], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                cfg = subprocess.run(
                    ["sc", "qc", svc], capture_output=True, text=True, timeout=5
                )
                path = ""
                for line in cfg.stdout.splitlines():
                    if "BINARY_PATH_NAME" in line:
                        path = line.split(":", 1)[-1].strip().strip('"')
                        break
                info["version"]          = info["version"] or svc
                info["path"]             = info["path"] or path
                info["uninstall_string"] = info["uninstall_string"] or "__service_only__"
                return info
        except Exception:
            pass

    # ── 4. Pastas padrão no disco ─────────────────────────────────────────────
    for base in [r"C:\Program Files\Firebird",
                 r"C:\Program Files (x86)\Firebird",
                 r"C:\Firebird"]:
        if not os.path.isdir(base):
            continue
        try:
            subs = os.listdir(base)
        except Exception:
            subs = []
        for sub in subs:
            for exe in ("fbserver.exe", "firebird.exe"):
                if os.path.isfile(os.path.join(base, sub, exe)):
                    info["version"]          = info["version"] or sub
                    info["path"]             = info["path"] or os.path.join(base, sub)
                    info["uninstall_string"] = info["uninstall_string"] or "__folder_only__"
                    return info
        for exe in ("fbserver.exe", "firebird.exe"):
            if os.path.isfile(os.path.join(base, exe)):
                info["version"]          = info["version"] or "Firebird (pasta)"
                info["path"]             = info["path"] or base
                info["uninstall_string"] = info["uninstall_string"] or "__folder_only__"
                return info

    return info if info["uninstall_string"] else None


def fb_install_path(fb_version: str) -> str:
    """
    Lê o caminho de instalação do Firebird no registro do Windows.
    Fallback para pastas padrão se não encontrar.
    """
    try:
        import winreg
        for key_path in [
            r"SOFTWARE\Firebird Project\Firebird Server\Instances",
            r"SOFTWARE\WOW6432Node\Firebird Project\Firebird Server\Instances",
        ]:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
                    path, _ = winreg.QueryValueEx(k, "DefaultInstance")
                    # DefaultInstance aponta para o arquivo security database (ex: security3.fdb)
                    # ou para a pasta raiz. Normaliza para obter a pasta de instalação.
                    path = path.rstrip("\\")  
                    # Se for um arquivo (.fdb), sobe um nível
                    if os.path.isfile(path):
                        path = os.path.dirname(path)
                    # Verifica se é a pasta correta (contém fbserver.exe ou firebird.exe)
                    for exe in ("firebird.exe", "fbserver.exe", "fbclient.dll"):
                        if os.path.isfile(os.path.join(path, exe)):
                            return path
                    # Tenta subpasta com versão
                    sub = os.path.join(path, f"Firebird_{fb_version}_0")
                    if os.path.isdir(sub):
                        return sub
                    if os.path.isdir(path):
                        return path
            except Exception:
                pass
    except ImportError:
        pass

    # Fallback por versão
    for candidate in [
        f"C:\\Program Files\\Firebird\\Firebird_{fb_version}_0",
        f"C:\\Program Files (x86)\\Firebird\\Firebird_{fb_version}_0",
        "C:\\Firebird",
    ]:
        if os.path.isdir(candidate):
            return candidate

    return ""


# =============================================================================
# Worker
# =============================================================================

class InstaladorFirebirdWorker(QThread):
    """
    Worker que executa todas as etapas de instalação do Firebird em background:
      1. Verificar instalação existente
      2. Desinstalar (se houver)
      3. Download do instalador
      4. Instalar silenciosamente
      5. Aplicar permissões (icacls)
      6. Copiar arquivos de configuração Futura (apenas FB4)
      7. Reiniciar serviço
    """

    log_line = pyqtSignal(str)
    progress = pyqtSignal(int, str, str)   # pct, titulo, detalhe
    finished = pyqtSignal(bool, dict)      # sucesso, info

    def __init__(self, fb_version: str, arch: str, parent=None):
        super().__init__(parent)
        self.fb_version = fb_version   # "3" ou "4"
        self.arch       = arch         # "x64" ou "x86"
        self._abort     = False

    def stop(self):
        self._abort = True

    # ── Helpers internos ──────────────────────────────────────────────────────

    def _emit(self, txt: str):
        log.info(txt)
        self.log_line.emit(txt)

    def _run_cmd(self, cmd: list[str], desc: str) -> bool:
        self._emit(f"► {desc}")
        self._emit(f"  CMD: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            for line in (result.stdout or "").splitlines():
                self._emit(f"  {line}")
            for line in (result.stderr or "").splitlines():
                self._emit(f"  [STDERR] {line}")
            ok = result.returncode in (0, 3010)  # 3010 = reboot pendente (ok)
            self._emit(f"  {'✓' if ok else '✗'} Código de saída: {result.returncode}")
            return ok
        except subprocess.TimeoutExpired:
            self._emit("  ✗ Timeout (5 min)")
            return False
        except Exception as e:
            self._emit(f"  ✗ Exceção: {e}")
            return False

    # ── Execução principal ────────────────────────────────────────────────────

    def run(self):
        url       = FB_URLS[self.fb_version][self.arch]
        ver_label = FB_LABEL[self.fb_version]

        self._emit("=" * 58)
        self._emit(f"  Instalando {ver_label} ({self.arch})")
        self._emit("=" * 58)

        # ── [0] Verificar privilégios de administrador ────────────────────────
        if not _is_admin():
            self._emit("\n✗ ERRO: O Futura Setup não está sendo executado como Administrador.")
            self._emit("  A instalação do Firebird requer privilégios elevados.")
            self._emit("  Feche o programa e execute novamente com 'Executar como administrador'.")
            self.finished.emit(False, {"cancelado": False, "sem_admin": True})
            return

        # ── [1/9] Verificar instalação existente ──────────────────────────────
        self.progress.emit(5, "Verificando sistema...", "Checando registro do Windows")
        self._emit("\n[1/9] Verificando instalação existente...")
        installed = None
        try:
            installed = check_installed_firebird()
        except Exception as e:
            self._emit(f"  [AVISO] {e}")

        if installed:
            self._emit(f"  ⚠ Encontrado: {installed['version']}")
            if installed.get("path"):
                self._emit(f"  Caminho: {installed['path']}")
        else:
            self._emit("  Nenhuma instalação anterior encontrada.")

        self.progress.emit(10, "Verificando sistema...", "Concluído")
        if self._abort:
            self.finished.emit(False, {"cancelado": True})
            return

        # ── [2/9] Backup do databases.conf (apenas se houver instalação) ──────
        databases_conf_backup: str = ""   # caminho do backup salvo
        if installed and installed.get("path"):
            self.progress.emit(13, "Fazendo backup...", "databases.conf")
            self._emit("\n[2/9] Fazendo backup do databases.conf...")
            databases_conf_backup = self._backup_databases_conf(installed["path"])
        else:
            self._emit("\n[2/9] Backup pulado — nenhuma instalação anterior.")

        if self._abort:
            self.finished.emit(False, {"cancelado": True})
            return

        # ── [3/9] Parar serviço + Desinstalar ────────────────────────────────
        pasta_antiga: str = installed["path"].rstrip("\\") if installed and installed.get("path") else ""

        if installed:
            # Para o serviço ANTES de qualquer tentativa de desinstalar/deletar
            self.progress.emit(15, "Parando serviço Firebird...", "")
            self._emit("\n[3/9] Parando serviço do Firebird antes de desinstalar...")
            self._parar_servico()

            uninst = installed.get("uninstall_string", "")
            if uninst not in ("", "__service_only__", "__folder_only__"):
                self.progress.emit(20, "Desinstalando versão atual...", installed["version"])
                self._emit("  Executando desinstalador...")
                ok = self._run_cmd([uninst, "/VERYSILENT", "/NORESTART"], "Desinstalador Firebird")
                if not ok:
                    ok = self._run_cmd([uninst, "/SILENT", "/NORESTART"], "Desinstalador (fallback)")
                if not ok:
                    self.finished.emit(False, {"cancelado": False})
                    return
            else:
                self._emit("  Desinstalador não encontrado — apenas pasta será removida.")
        else:
            self._emit("\n[3/9] Nenhuma instalação anterior — etapa pulada.")

        self.progress.emit(28, "Pronto para limpar pasta...", "")
        if self._abort:
            self.finished.emit(False, {"cancelado": True})
            return

        import time as _time
        _time.sleep(2)  # aguarda handles serem liberados

        # ── [4/9] Excluir pasta antiga ────────────────────────────────────────
        if pasta_antiga and os.path.isdir(pasta_antiga):
            self.progress.emit(30, "Removendo pasta antiga...", pasta_antiga)
            self._emit(f"\n[4/9] Excluindo pasta antiga: {pasta_antiga}")
            self._excluir_pasta(pasta_antiga)
        else:
            self._emit("\n[4/9] Exclusão de pasta pulada — pasta não encontrada.")

        self.progress.emit(33, "Pasta removida", "")
        if self._abort:
            self.finished.emit(False, {"cancelado": True})
            return

        # ── [5/9] Download ────────────────────────────────────────────────────
        # Extrai nome do arquivo: usa parâmetro "filename=" se presente (URLs do repositório)
        import urllib.parse as _urlparse
        _qs = _urlparse.parse_qs(_urlparse.urlparse(url).query)
        fname = _qs.get("filename", [url.split("/")[-1]])[0]
        tmp_path = os.path.join(tempfile.gettempdir(), fname)

        self._emit(f"\n[5/9] Baixando {ver_label} ({self.arch})...")
        self._emit(f"  URL: {url}")
        self.progress.emit(35, f"Baixando {ver_label}...", "Aguarde")

        try:
            def _hook(block_num, block_size, total_size):
                if self._abort:
                    raise InterruptedError()
                if total_size > 0:
                    pct        = min(int(block_num * block_size / total_size * 37), 37)
                    baixado    = min(block_num * block_size, total_size)
                    total_mb   = total_size / (1024 * 1024)
                    baixado_mb = baixado / (1024 * 1024)
                    self.progress.emit(
                        35 + pct,
                        f"Baixando {ver_label}...",
                        f"{baixado_mb:.1f} MB / {total_mb:.1f} MB",
                    )

            urllib.request.urlretrieve(url, tmp_path, reporthook=_hook)
            size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            self._emit(f"  ✓ Download concluído: {fname} ({size_mb:.1f} MB)")
        except InterruptedError:
            self.finished.emit(False, {"cancelado": True})
            return
        except Exception as e:
            self._emit(f"  ✗ Falha no download: {e}")
            self.finished.emit(False, {"cancelado": False})
            return

        self.progress.emit(74, "Download concluído", f"{size_mb:.1f} MB")
        if self._abort:
            self.finished.emit(False, {"cancelado": True})
            return

        # ── [6/9] Instalar ────────────────────────────────────────────────────
        self.progress.emit(76, f"Instalando {ver_label}...", "Aguarde")
        self._emit(f"\n[6/9] Instalando {ver_label}...")

        if self.fb_version == "3":
            # UseServiceTask  = registra como serviço Windows (aparece em services.msc)
            # UseGuardianTask = instala Guardian na bandeja do sistema (NÃO é serviço)
            tasks = (
                "UseSuperClassic,"
                "UseServiceTask,"
                "AutoStartTask,"
                "CopyFbClientToSysTask,"
                "GenerateClientLib"
            )
        else:
            tasks = (
                "UseSuperClassic,"
                "UseServiceTask,"
                "AutoStartTask,"
                "CopyFbClientToSysTask,"
                "GenerateClientLib"
            )

        self._emit(f"  /TASKS={tasks}")
        self._emit("  /SYSDBAPASSWORD=sbofutura  (SYSDBA)")

        # Determina diretório de instalação padrão por versão e arquitetura
        if self.arch == "x64":
            install_dir = f"C:\\Program Files\\Firebird\\Firebird_{self.fb_version}_0"
        else:
            install_dir = f"C:\\Program Files (x86)\\Firebird\\Firebird_{self.fb_version}_0"

        ok = self._run_cmd(
            [
                tmp_path,
                "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES",
                "/CLOSEAPPLICATIONS",       # fecha apps que bloqueiam arquivos
                "/FORCECLOSEAPPLICATIONS",  # força fechamento sem perguntar
                "/COMPONENTS=ServerComponent,DevAdminComponent",
                f"/TASKS={tasks}",
                f"/DIR={install_dir}",
                "/SYSDBAPASSWORD=sbofutura",
                "/SYSDBANAME=SYSDBA",
            ],
            f"Instalador {ver_label}",
        )

        try:
            os.remove(tmp_path)
            self._emit(f"  (Temporário removido: {fname})")
        except Exception:
            pass

        if not ok:
            self.finished.emit(False, {"cancelado": False})
            return

        # ── [7/9] Permissões + conf FB4 ───────────────────────────────────────
        self.progress.emit(83, "Configurando permissões...", "Aplicando acesso total para Todos")
        self._emit("\n[7/9] Parando serviço e aplicando permissões...")
        # Para apenas via serviço registrado (não mata processos aqui)
        self._parar_servico_apenas()
        self._aplicar_permissoes()

        if self.fb_version == "4":
            self.progress.emit(88, "Copiando configurações Futura...", "Firebird 4 — conf")
            self._emit("\n       Copiando arquivos de configuração Futura (FB4)...")
            self._copiar_conf_fb4()

        # ── [8/9] Restaurar databases.conf ────────────────────────────────────
        if databases_conf_backup:
            self.progress.emit(92, "Restaurando databases.conf...", "Mesclando entradas Live Databases")
            self._emit("\n[8/9] Restaurando entradas Live Databases no databases.conf...")
            self._restaurar_databases_conf(databases_conf_backup)
        else:
            self._emit("\n[8/9] Restauração do databases.conf pulada — sem backup.")

        # ── [9/9] Reiniciar serviço ───────────────────────────────────────────
        self.progress.emit(96, "Reiniciando serviço...", "Aguarde")
        self._emit("\n[9/9] Reiniciando serviço do Firebird...")
        self._iniciar_servico()

        self.progress.emit(100, "Instalação concluída!", f"{ver_label} ({self.arch})")
        self._emit(f"\n✓ {ver_label} ({self.arch}) instalado com sucesso!")
        self.finished.emit(True, {"version": ver_label, "arch": self.arch})

    # ── Métodos auxiliares ────────────────────────────────────────────────────

    def _backup_databases_conf(self, pasta_instalada: str) -> str:
        """
        Copia o databases.conf da instalação atual para um arquivo temporário.
        Retorna o caminho do backup ou string vazia em caso de falha.
        """
        src = os.path.join(pasta_instalada.rstrip("\\"), "databases.conf")
        if not os.path.isfile(src):
            self._emit(f"  [AVISO] databases.conf não encontrado em: {src}")
            return ""
        try:
            tmp = os.path.join(tempfile.gettempdir(), "fb_databases_conf_backup.conf")
            shutil.copy2(src, tmp)
            self._emit(f"  ✓ Backup salvo em: {tmp}")
            return tmp
        except Exception as e:
            self._emit(f"  ✗ Falha ao fazer backup: {e}")
            return ""

    def _excluir_pasta(self, pasta: str):
        """
        Remove a pasta de instalação antiga recursivamente.
        Estratégia:
          1. takeown + icacls para tomar posse
          2. shutil.rmtree com handler de somente-leitura
          3. Para cada arquivo ainda travado: tenta terminar processo que o segura
          4. cmd /c rd /s /q como fallback
          5. MoveFileEx MOVEFILE_DELAY_UNTIL_REBOOT para arquivos impossíveis de remover
        """
        import time
        import stat
        import ctypes

        if not os.path.isdir(pasta):
            self._emit(f"  Pasta já inexistente: {pasta}")
            return

        # 1. Toma posse e concede permissão total
        self._emit("  Tomando posse da pasta (takeown + icacls)...")
        subprocess.run(["takeown", "/F", pasta, "/R", "/D", "S"],
                       capture_output=True, timeout=30)
        subprocess.run(["icacls", pasta, "/grant", "*S-1-1-0:(OI)(CI)F", "/T", "/C", "/Q"],
                       capture_output=True, timeout=30)

        # 2. shutil.rmtree com handler para somente-leitura
        def _on_error(func, path, exc_info):
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        shutil.rmtree(pasta, onerror=_on_error)

        # 3. Para arquivos ainda existentes, tenta matar processo que os trava
        if os.path.isdir(pasta):
            self._emit("  Identificando processos com handles abertos...")
            for dirpath, dirnames, filenames in os.walk(pasta):
                for fname in filenames:
                    fpath = os.path.join(dirpath, fname)
                    # Usa openfiles ou tasklist para identificar quem usa o arquivo
                    try:
                        r = subprocess.run(
                            ["openfiles", "/query", "/fo", "csv"],
                            capture_output=True, text=True, timeout=10
                        )
                        if fname.lower() in r.stdout.lower():
                            self._emit(f"  Arquivo travado: {fname}")
                    except Exception:
                        pass
                    # Tenta forçar deleção via ctypes DeleteFile
                    try:
                        ctypes.windll.kernel32.SetFileAttributesW(fpath, 0x80)  # FILE_ATTRIBUTE_NORMAL
                        os.remove(fpath)
                    except Exception:
                        pass

        # 4. cmd rd /s /q
        if os.path.isdir(pasta):
            self._emit("  Tentando remoção forçada via cmd rd...")
            subprocess.run(
                f'cmd /c rd /s /q "{pasta}"',
                shell=True, capture_output=True, timeout=30
            )
            time.sleep(2)

        # 5. MoveFileEx — agenda exclusão no próximo boot para arquivos impossíveis
        if os.path.isdir(pasta):
            self._emit("  [AVISO] Arquivos bloqueados — agendando exclusão no próximo boot...")
            MOVEFILE_DELAY_UNTIL_REBOOT = 0x4
            for dirpath, dirnames, filenames in os.walk(pasta):
                for fname in filenames:
                    fpath = os.path.join(dirpath, fname)
                    try:
                        ctypes.windll.kernel32.MoveFileExW(fpath, None, MOVEFILE_DELAY_UNTIL_REBOOT)
                        self._emit(f"  Agendado para exclusão: {fname}")
                    except Exception:
                        pass
            # Agenda a própria pasta
            try:
                ctypes.windll.kernel32.MoveFileExW(pasta, None, MOVEFILE_DELAY_UNTIL_REBOOT)
            except Exception:
                pass
            self._emit("  A instalação continuará — arquivos serão removidos no próximo boot.")
        else:
            self._emit(f"  ✓ Pasta excluída: {pasta}")

    def _aplicar_permissoes(self):
        """Aplica icacls /grant *S-1-1-0:(OI)(CI)F na pasta de instalação."""
        pasta = fb_install_path(self.fb_version)
        if not pasta or not os.path.isdir(pasta):
            self._emit("  [AVISO] Pasta de instalação não localizada — permissões não aplicadas.")
            return
        self._emit(f"  Pasta: {pasta}")
        ok = self._run_cmd(
            ["icacls", pasta, "/grant", "*S-1-1-0:(OI)(CI)F", "/T", "/C", "/Q"],
            "icacls — Permissão total para Todos",
        )
        if ok:
            self._emit("  ✓ Permissões aplicadas com sucesso.")
        else:
            self._emit("  [AVISO] Falha ao aplicar permissões — verifique manualmente.")

    def _copiar_conf_fb4(self):
        """Baixa os 3 arquivos de configuração Futura e substitui na pasta do Firebird 4."""
        destino = fb_install_path("4")
        if not destino:
            destino = r"C:\Program Files\Firebird\Firebird_4_0"
        if not os.path.isdir(destino):
            self._emit(f"  [AVISO] Pasta não encontrada: {destino} — configurações não copiadas.")
            return
        self._emit(f"  Destino: {destino}")
        for url, filename in _FB4_CONF_FILES:
            dest_path = os.path.join(destino, filename)
            self._emit(f"  Baixando {filename}...")
            try:
                urllib.request.urlretrieve(url, dest_path)
                self._emit(f"  ✓ {filename} → {dest_path}")
            except Exception as e:
                self._emit(f"  ✗ Falha ao baixar {filename}: {e}")

    def _restaurar_databases_conf(self, backup_path: str):
        """
        Lê o backup do databases.conf antigo, extrai tudo abaixo de:
            # Live Databases:
        e mescla no novo databases.conf da pasta de instalação.
        A busca é case-insensitive e tolerante a variações de formato.
        """
        # Lê backup
        try:
            with open(backup_path, "r", encoding="utf-8", errors="replace") as f:
                linhas_backup = f.readlines()
        except Exception as e:
            self._emit(f"  ✗ Não foi possível ler o backup: {e}")
            return

        self._emit(f"  Backup contém {len(linhas_backup)} linhas.")

        # Mostra primeiras linhas para diagnóstico
        for i, l in enumerate(linhas_backup[:10]):
            self._emit(f"  [{i}] {repr(l)}")

        # Extrai entradas Live Databases
        # Estratégia: encontra a linha que contém "live databases" (case-insensitive)
        # e captura tudo após ela (ignorando linhas que são só # ou em branco do cabeçalho)
        entradas = []
        idx_marcador = None
        for i, linha in enumerate(linhas_backup):
            if "live databases" in linha.lower():
                idx_marcador = i
                break

        if idx_marcador is None:
            # Fallback: se não encontrou o marcador, considera que TUDO
            # que não é comentário de cabeçalho (# seguido de texto) são entradas
            self._emit("  Marcador 'Live Databases' não encontrado — extraindo todas as entradas não-comentário...")
            for linha in linhas_backup:
                stripped = linha.strip()
                # Captura linhas que não são linhas de comentário puro nem em branco
                if stripped and not stripped.startswith("#"):
                    entradas.append(linha)
        else:
            self._emit(f"  Marcador encontrado na linha {idx_marcador}: {repr(linhas_backup[idx_marcador])}")
            # Pula o marcador e linhas de cabeçalho logo após (linhas só com # ou vazias)
            i = idx_marcador + 1
            while i < len(linhas_backup) and linhas_backup[i].strip() in ("#", "#\n", ""):
                i += 1
            # Captura tudo após o cabeçalho
            entradas = linhas_backup[i:]

        # Remove linhas em branco do final
        while entradas and entradas[-1].strip() == "":
            entradas.pop()

        if not entradas:
            self._emit("  Nenhuma entrada encontrada após o marcador — nada a restaurar.")
            return

        self._emit(f"  {len(entradas)} linhas de Live Databases a restaurar:")
        for l in entradas:
            self._emit(f"    {l.rstrip()}")

        # Localiza o novo databases.conf
        nova_pasta = fb_install_path(self.fb_version)
        if not nova_pasta:
            self._emit("  ✗ Pasta de instalação nova não encontrada — restauração abortada.")
            return

        novo_conf = os.path.join(nova_pasta, "databases.conf")
        if not os.path.isfile(novo_conf):
            self._emit(f"  [AVISO] Novo databases.conf não encontrado em: {novo_conf}")
            self._emit("          Criando arquivo com as entradas do backup...")
            try:
                with open(novo_conf, "w", encoding="utf-8") as f:
                    f.write("# Live Databases:\n#\n")
                    f.writelines(entradas)
                self._emit(f"  ✓ databases.conf criado com entradas restauradas.")
            except Exception as e:
                self._emit(f"  ✗ Falha ao criar databases.conf: {e}")
            return

        # Lê o novo conf
        try:
            with open(novo_conf, "r", encoding="utf-8", errors="replace") as f:
                conteudo_novo = f.read()
        except Exception as e:
            self._emit(f"  ✗ Não foi possível ler o novo databases.conf: {e}")
            return

        # Localiza o marcador '# Live Databases:' no novo arquivo e substitui tudo após ele
        marcador = "# Live Databases:"
        if marcador in conteudo_novo:
            idx = conteudo_novo.index(marcador)
            # Mantém até o fim da linha do marcador + linha "#" seguinte
            ate_marcador = conteudo_novo[:idx]
            # Reconstrói: cabeçalho existente + marcador + "#" + entradas do backup
            novo_conteudo = (
                ate_marcador
                + "# Live Databases:\n#\n"
                + "".join(entradas)
                + "\n"
            )
        else:
            # Marcador não existe no novo conf — apenas acrescenta no final
            self._emit("  [AVISO] Marcador '# Live Databases:' não encontrado no novo conf. Adicionando ao final.")
            novo_conteudo = conteudo_novo.rstrip() + "\n\n# Live Databases:\n#\n" + "".join(entradas) + "\n"

        try:
            with open(novo_conf, "w", encoding="utf-8") as f:
                f.write(novo_conteudo)
            self._emit(f"  ✓ databases.conf atualizado: {novo_conf}")
        except Exception as e:
            self._emit(f"  ✗ Falha ao gravar databases.conf: {e}")

    # Todos os nomes possíveis de serviço do Firebird (ordem: Guardian primeiro para parar,
    # Server primeiro para iniciar quando não há Guardian — ex: FB4)
    _FB_SERVICES_STOP  = [
        "FirebirdGuardianDefaultInstance",
        "FirebirdServerDefaultInstance",
        "FirebirdGuardian",
        "FirebirdServer",
    ]
    _FB_SERVICES_START = [
        "FirebirdGuardianDefaultInstance",
        "FirebirdServerDefaultInstance",
        "FirebirdGuardian",
        "FirebirdServer",
    ]

    def _listar_servicos_firebird(self) -> list[str]:
        """Lista todos os serviços do Windows cujo nome contém 'firebird' (case-insensitive)."""
        found = []
        try:
            # shell=True necessário: sc exige "type= all" como token único no cmd
            r = subprocess.run(
                "sc query type= all state= all",
                shell=True, capture_output=True, text=True, timeout=15
            )
            for line in r.stdout.splitlines():
                line = line.strip()
                if line.upper().startswith("SERVICE_NAME:") and "firebird" in line.lower():
                    svc_name = line.split(":", 1)[1].strip()
                    if svc_name not in found:
                        found.append(svc_name)
        except Exception as e:
            self._emit(f"  [AVISO] Erro ao listar serviços: {e}")
        return found

    def _servico_existe(self, nome: str) -> bool:
        """Verifica se um serviço Windows existe (independente de estar rodando)."""
        try:
            r = subprocess.run(
                ["sc", "query", nome],
                capture_output=True, text=True, timeout=10
            )
            return r.returncode == 0
        except Exception:
            return False

    def _servico_rodando(self, nome: str) -> bool:
        """Verifica se um serviço Windows está no estado RUNNING."""
        try:
            r = subprocess.run(
                ["sc", "query", nome],
                capture_output=True, text=True, timeout=10
            )
            return "RUNNING" in r.stdout
        except Exception:
            return False

    def _parar_servico_apenas(self):
        """Para apenas os serviços registrados, sem matar processos.
        Usado após a instalação para parar antes de aplicar permissões.
        """
        import time
        servicos = self._listar_servicos_firebird()
        if not servicos:
            servicos = [s for s in self._FB_SERVICES_STOP if self._servico_existe(s)]
        if not servicos:
            self._emit("  Nenhum serviço registrado encontrado — continuando.")
            return
        for svc in servicos:
            self._emit(f"  Parando: {svc}")
            subprocess.run(["net", "stop", svc, "/y"], capture_output=True, timeout=15)
        time.sleep(2)

    def _parar_servico(self):
        """Para todos os processos e serviços do Firebird."""
        import time

        # ── 1. Para via serviço (sc query dinâmico + lista estática) ──────
        servicos = self._listar_servicos_firebird()
        if not servicos:
            servicos = [s for s in self._FB_SERVICES_STOP if self._servico_existe(s)]

        if servicos:
            for svc in servicos:
                self._emit(f"  Parando serviço: {svc}")
                subprocess.run(["net", "stop", svc, "/y"], capture_output=True, timeout=15)
                subprocess.run(["sc", "stop", svc], capture_output=True, timeout=10)
            time.sleep(2)
        else:
            self._emit("  Nenhum serviço Firebird encontrado pelo nome.")

        # ── 2. Mata processos diretamente por nome de executável ──────────
        # Cobre casos onde o serviço tem nome customizado ou não está registrado
        fb_processos = [
            "firebird.exe",
            "fbserver.exe",
            "fbguard.exe",
            "fb_inet_server.exe",
        ]

        # Lista processos rodando antes de matar (para diagnóstico no log)
        try:
            tl = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=10
            )
            rodando = [
                line.split(",")[0].strip('"').lower()
                for line in tl.stdout.splitlines() if line.strip()
            ]
            fb_rodando = [p for p in fb_processos if p.lower() in rodando]
            if fb_rodando:
                self._emit(f"  Processos Firebird em execução: {fb_rodando}")
            else:
                self._emit("  Nenhum processo Firebird encontrado no tasklist.")
        except Exception:
            pass

        for proc in fb_processos:
            r = subprocess.run(
                ["taskkill", "/F", "/IM", proc, "/T"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                self._emit(f"  ✓ Processo encerrado: {proc}")

        # ── 3. Garante que fbclient.dll não está carregado pelo Python ─────
        # O próprio processo Python pode ter carregado fbclient via algum driver
        try:
            import ctypes
            for dll_name in ("fbclient.dll", "fbclient32.dll"):
                try:
                    # Tenta liberar o módulo se estiver carregado
                    mod = ctypes.windll.LoadLibrary(dll_name)
                    ctypes.windll.kernel32.FreeLibrary(mod._handle)
                    self._emit(f"  DLL liberada: {dll_name}")
                except Exception:
                    pass
        except Exception:
            pass

        time.sleep(2)  # aguarda handles serem liberados pelo SO

    def _iniciar_servico(self):
        """
        Inicia o serviço do Firebird.
        FB3: inicia Guardian (ele sobe o Server automaticamente).
        FB4: inicia Server diretamente (sem Guardian).
        Detecta dinamicamente quais serviços existem.
        """
        import time

        todos = self._listar_servicos_firebird()
        if not todos:
            todos = [s for s in self._FB_SERVICES_START if self._servico_existe(s)]

        if not todos:
            self._emit("  ✗ Nenhum serviço Firebird encontrado para iniciar.")
            self._emit("    Verifique manualmente: services.msc")
            return

        self._emit(f"  Serviços detectados: {todos}")

        # Separa Guardian e Server
        guardians = [s for s in todos if "guardian" in s.lower()]
        servers   = [s for s in todos if "guardian" not in s.lower()]

        # FB3 com Guardian: inicia Guardian — ele sobe o Server automaticamente
        # FB4 sem Guardian: inicia Server diretamente
        # Ordem: Guardian primeiro se existir, senão Server
        ordem = guardians + servers

        iniciou = False
        for svc in ordem:
            self._emit(f"  Iniciando: {svc}")
            subprocess.run(["net", "start", svc], capture_output=True, timeout=30)

            # Aguarda até 30s confirmando RUNNING
            for _ in range(15):
                time.sleep(2)
                if self._servico_rodando(svc):
                    self._emit(f"  ✓ {svc} está RUNNING.")
                    iniciou = True
                    break
            else:
                # Fallback sc start
                subprocess.run(["sc", "start", svc], capture_output=True, timeout=15)
                time.sleep(4)
                if self._servico_rodando(svc):
                    self._emit(f"  ✓ {svc} iniciado via sc start.")
                    iniciou = True

            # Se iniciou o Guardian, verifica se o Server também subiu
            if iniciou and "guardian" in svc.lower() and servers:
                time.sleep(3)
                for srv in servers:
                    if self._servico_rodando(srv):
                        self._emit(f"  ✓ {srv} também está RUNNING (iniciado pelo Guardian).")
                    else:
                        self._emit(f"  [AVISO] {srv} não confirmou RUNNING após Guardian subir.")
                break  # Guardian iniciado — não inicia Server separadamente

            if iniciou:
                break

        if not iniciou:
            self._emit("  ✗ Não foi possível confirmar o início do serviço Firebird.")
            self._emit("    Verifique manualmente: services.msc")