# =============================================================================
# FUTURA SETUP — Installer
# Melhorias v2:
#   - psutil importado no topo com flag _HAS_PSUTIL (sem import tardio em loop)
#   - _copiar_arquivo: verificação de integridade via SHA-256 (não só tamanho)
#   - InstalacaoWorker.run: orquestrador limpo; lógica em _step_* privados
#   - _copiar_exes: usa Path consistentemente (sem mistura com os.path)
#   - download: reutiliza download_com_retry de core.downloader
# Melhorias v4:
#   - _BaseWorker._log: corrigido bug de recursão infinita
#     (última linha era self._log(msg, kind) → corrigido para self.log_line.emit(msg, kind))
# =============================================================================

import hashlib
import os
import shutil
import zipfile
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.logger import log
from core.network import Servidor
from config import (
    URL_DLLS, EXES_CONHECIDOS, MAX_BACKUPS, ESPACO_MIN_MB,
    MAX_TENTATIVAS_DOWNLOAD, MAX_TENTATIVAS_COPIA, BACKUP_SUBDIR
)

# psutil: importado uma vez no módulo com flag de disponibilidade
try:
    import psutil as _psutil
    _HAS_PSUTIL = True
except ImportError:
    _psutil = None
    _HAS_PSUTIL = False


# ── UTILITÁRIOS ──────────────────────────────────────────────────────────────

def _exe_dict(f: Path, desc: str) -> dict:
    """Constrói o dicionário de metadados de um executável."""
    try:
        tamanho = f.stat().st_size
    except Exception:
        tamanho = 0
    return {"nome": f.name, "descricao": desc, "caminho": str(f), "tamanho": tamanho}


def listar_executaveis(path: str) -> list[dict]:
    """Lista EXEs na pasta do servidor, priorizando os conhecidos."""
    pasta   = Path(path)
    nomes_c = {e[0] for e in EXES_CONHECIDOS}
    result  = [
        _exe_dict(pasta / nome, desc)
        for nome, desc in EXES_CONHECIDOS
        if (pasta / nome).exists()
    ]
    try:
        for f in pasta.glob("*.exe"):
            if f.name not in nomes_c:
                result.append(_exe_dict(f, "Aplicativo Futura"))
    except Exception:
        pass
    return result


def formatar_tamanho(bytes_: int) -> str:
    mb = bytes_ / (1024 * 1024)
    if mb >= 1:
        return f"{mb:.1f} MB"
    return f"{bytes_ / 1024:.0f} KB"


def espaco_livre_mb(caminho: str) -> float:
    try:
        usage = shutil.disk_usage(Path(caminho).anchor)
        return usage.free / (1024 * 1024)
    except Exception as e:
        log.warn(f"Não foi possível verificar espaço em disco em '{caminho}': {e}")
        return 9999.0


def _hash_arquivo(path: str) -> str:
    """Calcula SHA-256 do arquivo para verificação de integridade."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _validar_zip(caminho: str) -> bool:
    """Verifica se o arquivo começa com header PK (bytes mágicos do ZIP)."""
    try:
        with open(caminho, "rb") as f:
            header = f.read(4)
        return len(header) >= 2 and header[0] == 0x50 and header[1] == 0x4B
    except Exception:
        return False


def listar_processos_na_pasta(pasta: str) -> list[dict]:
    """Retorna processos em execução cujo caminho está dentro da pasta."""
    if not _HAS_PSUTIL:
        log.warn("psutil não instalado — verificação de processos ignorada")
        return []
    procs = []
    pasta_lower = str(pasta).lower().rstrip("\\")
    for p in _psutil.process_iter(["pid", "name", "exe"]):
        try:
            exe = p.info.get("exe") or ""
            if exe.lower().startswith(pasta_lower):
                procs.append({"pid": p.info["pid"], "name": p.info["name"], "exe": exe})
        except (_psutil.NoSuchProcess, _psutil.AccessDenied):
            pass
    return procs


def encerrar_processos(pids: list[int]) -> tuple[int, int]:
    """Encerra processos pelos PIDs. Retorna (encerrados, falhos)."""
    if not _HAS_PSUTIL:
        log.warn("psutil não instalado — não foi possível encerrar processos")
        return 0, 0
    ok = falhos = 0
    for pid in pids:
        try:
            p = _psutil.Process(pid)
            p.terminate()
            p.wait(timeout=5)
            ok += 1
        except Exception as e:
            log.error(f"Falha ao encerrar PID {pid}: {e}")
            falhos += 1
    return ok, falhos


def criar_atalho_windows(target: str, shortcut_name: str, description: str,
                         desktop=True, start_menu=False) -> list[str]:
    """Cria atalho .lnk via win32com. Retorna lista de locais criados."""
    criados = []
    try:
        import win32com.client
        wsh = win32com.client.Dispatch("WScript.Shell")

        def _make(folder: str) -> str:
            path = str(Path(folder) / f"{shortcut_name}.lnk")
            lnk  = wsh.CreateShortcut(path)
            lnk.TargetPath       = target
            lnk.Description      = description
            lnk.WorkingDirectory = str(Path(target).parent)
            lnk.IconLocation     = f"{target},0"
            lnk.Save()
            return path

        if desktop:
            lnk_path = _make(wsh.SpecialFolders("Desktop"))
            if Path(lnk_path).exists():
                criados.append("Desktop")
                log.ok(f"Atalho Desktop criado: {lnk_path}")
            else:
                log.error(f"Atalho Desktop não foi criado em: {lnk_path}")

        if start_menu:
            folder = str(Path(wsh.SpecialFolders("Programs")) / "Futura Sistemas")
            Path(folder).mkdir(parents=True, exist_ok=True)
            lnk_path = _make(folder)
            if Path(lnk_path).exists():
                criados.append("Menu Iniciar")
                log.ok(f"Atalho Menu Iniciar criado: {lnk_path}")
            else:
                log.error(f"Atalho Menu Iniciar não foi criado em: {lnk_path}")

    except ImportError:
        log.warn("win32com não disponível — atalhos não criados. Instale pywin32.")
    except Exception as e:
        log.error(f"Erro ao criar atalho '{shortcut_name}': {type(e).__name__}: {e}")

    return criados


def listar_backups(pasta_futura: str) -> list[dict]:
    """Lista backups disponíveis em pasta_futura/Backup_Atualizacao."""
    pasta_bk = Path(pasta_futura) / BACKUP_SUBDIR
    if not pasta_bk.exists():
        return []
    backups = []
    try:
        dirs = sorted(
            [d for d in pasta_bk.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime if d.exists() else 0.0,
            reverse=True
        )
    except Exception as e:
        log.warn(f"Erro ao listar backups em '{pasta_bk}': {e}")
        return []
    for d in dirs:
        try:
            arquivos = list(d.rglob("*"))
            n_files  = sum(1 for f in arquivos if f.is_file())
            tamanho  = sum(f.stat().st_size for f in arquivos if f.is_file())
            backups.append({
                "nome":     d.name,
                "caminho":  str(d),
                "arquivos": n_files,
                "tamanho":  tamanho,
            })
        except Exception as e:
            log.warn(f"Erro ao ler backup '{d.name}': {e}")
    return backups


# ── DOWNLOAD (compartilhado com atualizador) ─────────────────────────────────

def _download_arquivo(url: str, destino: str, progress_cb=None) -> bool:
    try:
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            total   = int(resp.headers.get("Content-Length", 0))
            baixado = 0
            with open(destino, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    baixado += len(chunk)
                    if progress_cb and total > 0:
                        progress_cb(baixado, total)

        if Path(destino).stat().st_size == 0:
            raise ValueError("Arquivo baixado está vazio")
        return True

    except Exception as e:
        log.error(f"Erro no download de {url}: {e}")
        Path(destino).unlink(missing_ok=True)
        return False


def download_com_retry(url: str, destino: str, descricao: str = "Baixando",
                       progress_cb=None,
                       max_tentativas: int = MAX_TENTATIVAS_DOWNLOAD) -> bool:
    """Tenta baixar `url` até `max_tentativas` vezes."""
    for i in range(1, max_tentativas + 1):
        log.info(f"{descricao} — tentativa {i}/{max_tentativas}")
        if _download_arquivo(url, destino, progress_cb):
            return True
    log.error(f"Falha após {max_tentativas} tentativas: {url}")
    return False


def _verificar_integridade(destino: str, hash_origem: str | None,
                            tam_origem: int) -> tuple[bool, str]:
    if hash_origem:
        try:
            if _hash_arquivo(destino) != hash_origem:
                return False, "Falha de integridade SHA-256"
        except Exception as e:
            return False, f"Erro ao verificar hash: {e}"
    else:
        try:
            if Path(destino).stat().st_size != tam_origem:
                return False, "Tamanho divergente"
        except Exception as e:
            return False, f"Erro ao verificar tamanho: {e}"
    return True, ""


# ── BASE WORKER ───────────────────────────────────────────────────────────────

class _BaseWorker(QThread):
    """
    Classe base para todos os workers de operação longa.

    Fornece:
      - stop() / _stop flag
      - _log(msg, kind)  — grava no arquivo e emite log_line
      - _pct(pct, titulo, detalhe)  — emite progress + status_text

    Subclasses devem declarar os sinais concretos adicionais (finished, etc.)
    e implementar run(). O prefixo _LOG_PREFIX é adicionado automaticamente
    nas entradas do arquivo de log para facilitar a filtragem.
    """
    log_line    = pyqtSignal(str, str)
    progress    = pyqtSignal(int, str, str)
    status_text = pyqtSignal(str)

    _LOG_PREFIX: str = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop = False

    def stop(self):
        self._stop = True

    def _log(self, msg: str, kind: str = "info"):
        prefixed = f"{self._LOG_PREFIX} {msg}".strip() if self._LOG_PREFIX else msg
        if kind == "ok":
            log.ok(prefixed)
        elif kind == "warn":
            log.warn(prefixed)
        elif kind == "err":
            log.error(prefixed)
        else:
            log.info(prefixed)
        self.log_line.emit(msg, kind)  # ← CORRIGIDO: era self._log(msg, kind) — recursão infinita

    def _pct(self, pct: int, titulo: str, detalhe: str = ""):
        self.progress.emit(pct, titulo, detalhe)
        self.status_text.emit(titulo)


# ── WORKER: INSTALAÇÃO TERMINAL ──────────────────────────────────────────────

class InstalacaoWorker(_BaseWorker):
    """
    Executa toda a instalação de terminal em background.
    Emite sinais de progresso para a UI em cada etapa.

    Índices de step (para step_done.emit):
      3=Backup  4=Servidor  5=Arquivos  6=DLLs  7=Atalhos
    step_done.emit(n) → ativa o step de índice n (marca n-1 como concluído).
    """
    step_done = pyqtSignal(int)
    finished  = pyqtSignal(bool, dict)

    _LOG_PREFIX = "[Instalacao]"

    def __init__(self, servidor: Servidor, pasta: str, exes: list[str],
                 criar_atalho_desktop: bool = True,
                 criar_atalho_menu: bool    = False,
                 exes_atalho: list[str] | None = None,
                 parent=None):
        super().__init__(parent)
        self.servidor             = servidor
        self.pasta                = pasta
        self.exes                 = exes
        self.criar_atalho_desktop = criar_atalho_desktop
        self.criar_atalho_menu    = criar_atalho_menu
        self.exes_atalho          = exes_atalho

    # ── Orquestrador ──────────────────────────────────────────────────────────

    def run(self):
        log.section(f"INSTALAÇÃO TERMINAL — {self.servidor.ip}")
        resumo = {
            "pasta":         self.pasta,
            "servidor":      self.servidor.display,
            "copiados":      0,
            "atalhos":       0,
            "atalhos_nomes": [],
            "backup":        "",
            "dlls":          False,
        }
        try:
            if not self._step_backup(resumo):
                if self._stop:
                    self._emit_cancelado(resumo)
                return
            if self._stop:
                self._emit_cancelado(resumo)
                return
            self.step_done.emit(4)

            if not self._step_verificar_servidor():
                self.finished.emit(False, resumo)
                return
            if self._stop:
                self._emit_cancelado(resumo)
                return
            self.step_done.emit(5)

            self._step_copiar_arquivos(resumo)
            if self._stop:
                self._emit_cancelado(resumo)
                return
            self.step_done.emit(6)

            resumo["dlls"] = self._step_instalar_dlls()
            if self._stop:
                self._emit_cancelado(resumo)
                return
            self.step_done.emit(7)

            atalhos, atalhos_nomes = self._step_criar_atalhos()
            resumo["atalhos"]       = atalhos
            resumo["atalhos_nomes"] = atalhos_nomes

            log.section("INSTALAÇÃO CONCLUÍDA COM SUCESSO")
            self.finished.emit(True, resumo)

        except Exception as e:
            log.error(f"Erro inesperado na instalação: {e}")
            self._log(f"Erro inesperado: {e}", "err")
            self.finished.emit(False, resumo)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _emit_cancelado(self, resumo: dict):
        resumo["cancelado"] = True
        self._log("Operação cancelada pelo usuário.", "warn")
        log.warn("InstalacaoWorker: cancelado pelo usuário")
        self.finished.emit(False, resumo)

    # ── Steps privados ────────────────────────────────────────────────────────

    def _step_backup(self, resumo: dict) -> bool:
        self._log("Preparando pasta de instalação...", "info")
        self.status_text.emit("Fazendo backup do conteúdo atual...")
        pasta_path = Path(self.pasta)
        pasta_bk   = pasta_path / BACKUP_SUBDIR
        pasta_path.mkdir(parents=True, exist_ok=True)
        pasta_bk.mkdir(parents=True, exist_ok=True)

        itens = [i for i in pasta_path.iterdir() if i != pasta_bk]
        if itens:
            ts      = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            dest_bk = pasta_bk / ts
            dest_bk.mkdir(parents=True, exist_ok=True)
            movidos = 0
            for i, item in enumerate(itens):
                if self._stop:
                    return False
                pct = int((i + 1) / len(itens) * 100)
                self.progress.emit(pct, "Backup", f"Movendo {item.name}...")
                try:
                    shutil.move(str(item), str(dest_bk / item.name))
                    movidos += 1
                except Exception as e:
                    self._log(f"Erro ao mover {item.name}: {e}", "warn")

            self._log(f"Backup: {movidos} item(s) em {dest_bk}", "ok")
            resumo["backup"] = str(dest_bk)
            log.ok(f"Backup concluído: {dest_bk}")
            self._limpar_backups_antigos(pasta_bk)
        else:
            self._log("Pasta vazia — backup não necessário", "info")
            resumo["backup"] = str(pasta_bk)

        return True

    def _step_verificar_servidor(self) -> bool:
        self.status_text.emit("Verificando acesso ao servidor...")
        self.progress.emit(0, "Conexão", f"Testando {self.servidor.path}...")
        if not Path(self.servidor.path).exists():
            self._log(f"Servidor inacessível: {self.servidor.path}", "err")
            return False
        self._log(f"Servidor acessível: {self.servidor.path}", "ok")
        return True

    def _step_copiar_arquivos(self, resumo: dict):
        self.status_text.emit("Copiando arquivos...")
        copiados  = self._copiar_ini()
        copiados += self._copiar_exes()
        resumo["copiados"] = copiados

    def _step_instalar_dlls(self) -> bool:
        self.status_text.emit("Baixando DLLs...")
        return self._instalar_dlls()

    def _step_criar_atalhos(self) -> tuple[int, list[str]]:
        self.status_text.emit("Criando atalhos...")
        return self._criar_atalhos()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _copiar_ini(self) -> int:
        ini_origem  = Path(self.servidor.path) / "Futura.ini"
        ini_destino = Path(self.pasta) / "Futura.ini"
        if ini_origem.exists():
            ok = self._copiar_arquivo(str(ini_origem), str(ini_destino), "Futura.ini")
            return 1 if ok else 0
        try:
            conteudo = f"[CONFIGURACAO]\r\nDADOS_IP={self.servidor.ip}\r\n"
            ini_destino.write_text(conteudo, encoding="latin-1")
            self._log(f"Futura.ini gerado automaticamente (IP: {self.servidor.ip})", "ok")
            return 1
        except Exception as e:
            self._log(f"Erro ao gerar Futura.ini: {e}", "err")
            return 0

    def _copiar_exes(self) -> int:
        copiados = 0
        total    = len(self.exes)
        for i, caminho in enumerate(self.exes):
            if self._stop:
                break
            nome    = Path(caminho).name
            destino = str(Path(self.pasta) / nome)
            ok = self._copiar_arquivo(
                caminho, destino, nome,
                progresso_base = int(i / total * 100),
                progresso_max  = int((i + 1) / total * 100),
            )
            if ok:
                copiados += 1
        return copiados

    def _copiar_arquivo(self, origem: str, destino: str, nome: str,
                        max_tentativas: int = MAX_TENTATIVAS_COPIA,
                        progresso_base: int = 0,
                        progresso_max: int  = 100) -> bool:
        try:
            tam_origem = Path(origem).stat().st_size
        except Exception as e:
            self._log(f"Não foi possível ler {nome}: {e}", "err")
            return False

        hash_origem = None
        try:
            hash_origem = _hash_arquivo(origem)
        except Exception:
            pass

        tam_fmt = formatar_tamanho(tam_origem)

        for tentativa in range(1, max_tentativas + 1):
            prefixo = nome if tentativa == 1 else f"{nome} (tentativa {tentativa})"
            self.progress.emit(progresso_base, prefixo, f"Copiando {tam_fmt}...")
            try:
                if tentativa > 1 and Path(destino).exists():
                    Path(destino).unlink()

                shutil.copy2(origem, destino)

                integro, motivo = _verificar_integridade(
                    destino, hash_origem, tam_origem
                )
                if not integro:
                    self._log(f"{motivo} em {nome}", "warn")
                    if tentativa < max_tentativas:
                        continue
                    return False

                self.progress.emit(progresso_max, prefixo, f"Concluído ({tam_fmt})")
                self._log(f"{nome} copiado ({tam_fmt})", "ok")
                return True

            except Exception as e:
                self._log(f"Falha ao copiar {nome} (tent. {tentativa}): {e}", "err")
                if tentativa == max_tentativas:
                    log.error(f"Falha definitiva ao copiar {nome}: {e}")

        return False

    def _instalar_dlls(self) -> bool:
        from core.network import testar_conectividade
        self._log("Verificando conectividade com a internet...", "info")
        if not testar_conectividade():
            self._log("Sem acesso à internet — DLLs não instaladas", "warn")
            log.warn("Download de DLLs abortado: sem conectividade")
            return False

        ts   = datetime.now().strftime("%Y%m%d%H%M%S")
        temp = Path(os.environ.get("TEMP", ".")) / f"dlls_{ts}.zip"

        def _prog(baixado, total):
            if total > 0:
                pct = int(baixado / total * 60)
                mb  = baixado / (1024 * 1024)
                self.progress.emit(pct, "DLLs", f"Baixando... {mb:.1f} MB")

        ok = download_com_retry(URL_DLLS, str(temp), "DLLs", _prog)
        if not ok:
            return False

        self.progress.emit(62, "DLLs", "Validando integridade do arquivo...")
        if not _validar_zip(str(temp)):
            self._log("Arquivo ZIP corrompido (header incorreto)", "err")
            temp.unlink(missing_ok=True)
            return False
        self._log("Arquivo ZIP válido", "ok")

        self.progress.emit(65, "DLLs", "Extraindo...")
        extract = Path(os.environ.get("TEMP", ".")) / f"dlls_extract_{ts}"
        try:
            with zipfile.ZipFile(temp, "r") as zf:
                members = zf.namelist()
                for i, member in enumerate(members):
                    if self._stop:
                        break
                    zf.extract(member, extract)
                    pct = 65 + int((i + 1) / len(members) * 25)
                    self.progress.emit(pct, "DLLs", f"Extraindo {i+1}/{len(members)}...")
        except Exception as e:
            self._log(f"Erro ao extrair DLLs: {e}", "err")
            temp.unlink(missing_ok=True)
            shutil.rmtree(extract, ignore_errors=True)
            return False

        if self._stop:
            temp.unlink(missing_ok=True)
            shutil.rmtree(extract, ignore_errors=True)
            return False

        self.progress.emit(90, "DLLs", "Instalando na pasta de destino...")
        n = erros = 0
        for arq in extract.rglob("*"):
            if arq.is_file():
                dest = Path(self.pasta) / arq.relative_to(extract)
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(arq, dest)
                    n += 1
                except Exception:
                    erros += 1

        temp.unlink(missing_ok=True)
        shutil.rmtree(extract, ignore_errors=True)

        self.progress.emit(100, "DLLs", f"{n} arquivo(s) instalado(s)")
        if n > 0:
            self._log(f"DLLs instaladas: {n} arquivo(s) ({erros} erro(s))", "ok")
            log.ok(f"DLLs instaladas: {n} arquivos, {erros} erros")
            return True
        self._log("Nenhuma DLL foi instalada", "err")
        return False

    def _criar_atalhos(self) -> tuple[int, list[str]]:
        total = 0
        nomes = []
        if self.exes_atalho is not None:
            candidatos = [Path(p) for p in self.exes_atalho if p.endswith(".exe")]
        else:
            try:
                candidatos = list(Path(self.pasta).glob("*.exe"))
            except Exception:
                candidatos = []

        for exe in candidatos:
            if not exe.exists():
                self._log(f"Atalho ignorado (não encontrado): {exe.name}", "warn")
                continue
            locais = criar_atalho_windows(
                str(exe), exe.stem, f"Sistema Futura — {exe.stem}",
                desktop    = self.criar_atalho_desktop,
                start_menu = self.criar_atalho_menu,
            )
            if locais:
                self._log(f"Atalho: {exe.stem} → {', '.join(locais)}", "ok")
                total += 1
                nomes.append(exe.name)
            else:
                self._log(f"Atalho falhou: {exe.stem}", "warn")
        return total, nomes

    def _limpar_backups_antigos(self, pasta_bk: Path):
        try:
            bks = sorted(pasta_bk.iterdir())
            if len(bks) > MAX_BACKUPS:
                para_apagar = len(bks) - MAX_BACKUPS
                for bk in bks[:para_apagar]:
                    shutil.rmtree(bk, ignore_errors=True)
                    log.info(f"Backup antigo removido: {bk}")
                self._log(f"{para_apagar} backup(s) antigo(s) removido(s)", "info")
        except Exception as e:
            log.warn(f"Erro ao limpar backups antigos em '{pasta_bk}': {e}")


# ── WORKER: RESTAURAÇÃO ──────────────────────────────────────────────────────

class RestauracaoWorker(_BaseWorker):
    finished = pyqtSignal(bool, dict)

    _LOG_PREFIX = "[Restauracao]"

    def __init__(self, pasta_destino: str, backup_caminho: str, parent=None):
        super().__init__(parent)
        self.pasta_destino  = pasta_destino
        self.backup_caminho = backup_caminho

    def run(self):
        log.section(f"RESTAURAÇÃO — {self.backup_caminho}")
        resumo = {"backup": Path(self.backup_caminho).name, "arquivos": 0, "erros": 0}

        try:
            pasta    = Path(self.pasta_destino)
            pasta_bk = pasta / BACKUP_SUBDIR

            self._pct(0, "Salvando estado atual em backup de segurança...")
            itens = [i for i in pasta.iterdir() if i != pasta_bk]
            if itens:
                ts      = "pre_restauracao_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                dest_bk = pasta_bk / ts
                dest_bk.mkdir(parents=True, exist_ok=True)
                for i, item in enumerate(itens):
                    if self._stop:
                        resumo["cancelado"] = True
                        self._log("Operação cancelada pelo usuário.", "warn")
                        self.finished.emit(False, resumo)
                        return
                    pct = int((i + 1) / len(itens) * 40)
                    self.progress.emit(pct, "Backup de segurança", f"Movendo {item.name}...")
                    try:
                        shutil.move(str(item), str(dest_bk / item.name))
                    except Exception as e:
                        self._log(f"Aviso ao mover {item.name}: {e}", "warn")
                self._log(f"Backup de segurança criado: {dest_bk.name}", "ok")

            self._pct(0, "Restaurando arquivos...")
            origem_path = Path(self.backup_caminho)
            arquivos    = list(origem_path.rglob("*"))
            n = erros   = 0

            for i, arq in enumerate(arquivos):
                if self._stop:
                    resumo["arquivos"]  = n
                    resumo["erros"]     = erros
                    resumo["cancelado"] = True
                    self._log("Operação cancelada pelo usuário.", "warn")
                    self.finished.emit(False, resumo)
                    return
                if arq.is_file():
                    rel  = arq.relative_to(origem_path)
                    dest = pasta / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    pct  = 40 + int((i + 1) / len(arquivos) * 60)
                    self.progress.emit(pct, "Restaurando", f"{arq.name}")
                    try:
                        shutil.copy2(arq, dest)
                        n += 1
                    except Exception as e:
                        self._log(f"Erro ao restaurar {arq.name}: {e}", "err")
                        erros += 1

            resumo["arquivos"] = n
            resumo["erros"]    = erros
            self._log(f"{n} arquivo(s) restaurado(s) — {erros} erro(s)", "ok")
            log.section("RESTAURAÇÃO CONCLUÍDA")
            self.finished.emit(True, resumo)

        except Exception as e:
            log.error(f"Erro na restauração: {e}")
            self._log(f"Erro inesperado: {e}", "err")
            self.finished.emit(False, resumo)


# ── WORKER: ATALHOS VIA REDE ─────────────────────────────────────────────────

class AtalhosWorker(_BaseWorker):
    finished = pyqtSignal(bool, int, int)

    _LOG_PREFIX = "[Atalhos]"

    def __init__(self, exes: list[dict], desktop: bool = True,
                 start_menu: bool = True, parent=None):
        super().__init__(parent)
        self.exes       = exes
        self.desktop    = desktop
        self.start_menu = start_menu

    def run(self):
        log.section("MODO: ATALHOS VIA REDE")
        criados = falhos = 0
        total   = len(self.exes)
        for i, exe in enumerate(self.exes):
            if self._stop:
                self._log("Operação cancelada pelo usuário.", "warn")
                log.warn("AtalhosWorker: cancelado pelo usuário")
                self.finished.emit(False, criados, falhos)
                return
            nome  = Path(exe["nome"]).stem
            pct   = int((i / total) * 90)
            self.progress.emit(pct, f"Criando {exe['nome']}...", "")
            locais = criar_atalho_windows(
                exe["caminho"], nome, exe["descricao"],
                desktop    = self.desktop,
                start_menu = self.start_menu,
            )
            if locais:
                self._log(f"{nome} → {', '.join(locais)}", "ok")
                log.ok(f"Atalho criado: {nome} — {', '.join(locais)}")
                criados += 1
            else:
                self._log(f"{nome} — falhou", "warn")
                falhos += 1
        self.progress.emit(100, "Concluído", f"{criados} atalho(s) criado(s)")
        self.finished.emit(criados > 0, criados, falhos)
