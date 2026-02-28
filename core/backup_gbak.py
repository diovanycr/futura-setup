"""
core/backup_gbak.py — Worker de Backup e Restaure via GBAK (Firebird)

Fluxo Backup:
  1. Detectar diretório do Firebird (x86 / x64)
  2. Parar serviços Firebird
  3. Renomear DADOS.fdb → DADOS_TEMP.fdb
  4. Executar gbak -b  (streaming de output em tempo real)
  5. Renomear DADOS_TEMP.fdb → DADOS.fdb
  6. Reiniciar serviços Firebird

Fluxo Restaure:
  1. Detectar diretório do Firebird
  2. Parar serviços Firebird
  3. Executar gbak -c  (output em tempo real) → gera DADOSNOVO.fdb
  4. Reiniciar serviços Firebird
  (usuário decide manualmente o que fazer com DADOSNOVO.fdb)
"""

from __future__ import annotations

import os
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.logger import log
from core.installer import _BaseWorker
from core.firebird_services import (
    stop_firebird_services, start_firebird_services, find_firebird_dir,
    FIREBIRD_SERVICES,
)

# Constantes e funções de controle de serviços centralizadas em core.firebird_services

GBAK_USER     = "sysdba"
GBAK_PASSWORD = "sbofutura"


# ---------------------------------------------------------------------------
# Funções auxiliares (não-bloqueantes, usadas pela UI para detecção inicial)
# ---------------------------------------------------------------------------



def find_dados_fdb(pasta_dados: str) -> Optional[str]:
    """Procura DADOS.fdb na pasta informada. Retorna o caminho completo ou None."""
    candidates = ["DADOS.fdb", "dados.fdb", "Dados.fdb"]
    for name in candidates:
        full = os.path.join(pasta_dados, name)
        if os.path.isfile(full):
            return full
    return None






def gerar_nome_backup(pasta_backup: str) -> str:
    """Gera caminho completo do .bck com data e hora."""
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    nome = f"BACKUP_{ts}.bck"
    return os.path.join(pasta_backup, nome)


# ---------------------------------------------------------------------------
# Worker de detecção (curta duração — usa SingleShotConnection na UI)
# ---------------------------------------------------------------------------

class _DetectarFirebirdWorker(QThread):
    """Detecta diretório Firebird e caminho do DADOS.fdb em background."""
    finished = pyqtSignal(str, str)   # (firebird_dir, dados_fdb)  — "" se não encontrado

    def __init__(self, pasta_dados: str):
        super().__init__()
        self._pasta_dados = pasta_dados

    def run(self):
        fb  = find_firebird_dir() or ""
        fdb = find_dados_fdb(self._pasta_dados) or ""
        self.finished.emit(fb, fdb)


# ---------------------------------------------------------------------------
# Worker de Backup
# ---------------------------------------------------------------------------

class BackupGbakWorker(_BaseWorker):
    finished = pyqtSignal(bool, dict)

    _LOG_PREFIX = "[BackupGBAK]"

    def __init__(
        self,
        firebird_dir: str,
        dados_fdb: str,       # caminho completo de DADOS.fdb
        backup_bck: str,      # caminho completo de destino .bck (já com data/hora)
    ):
        super().__init__()
        self._fb_dir         = firebird_dir
        self._dados_fdb      = dados_fdb
        self._backup_bck     = backup_bck
        self._servicos_parados: list[str] = []

    # ------------------------------------------------------------------
    def run(self):
        # REFATORAÇÃO: antes usava 3 chamadas .replace() encadeadas (frágil e
        # case-sensitive). Path.stem extrai o nome sem extensão de forma segura.
        dados_path = Path(self._dados_fdb)
        dados_temp = str(dados_path.with_name(dados_path.stem + "_TEMP.fdb"))
        sucesso = False
        info: dict = {}

        log.section("BACKUP GBAK")
        self._log("Iniciando processo de backup via GBAK...", "info")

        try:
            # --- Passo 1: Parar Firebird ---
            if self._stop:
                raise InterruptedError("Cancelado pelo usuário.")
            self._pct(5, "Parando serviços do Firebird...")
            self._log("Parando serviços do Firebird...", "info")
            self._servicos_parados = stop_firebird_services()
            if self._servicos_parados:
                self._log(f"Serviços parados: {', '.join(self._servicos_parados)}", "ok")
            else:
                self._log("Nenhum serviço Firebird ativo encontrado (ou já parado).", "warn")

            # --- Passo 2: Renomear DADOS → DADOS_TEMP ---
            if self._stop:
                raise InterruptedError("Cancelado pelo usuário.")
            self._pct(15, "Renomeando banco de dados...")
            self._log(f"Renomeando: {self._dados_fdb} → {dados_temp}", "info")
            os.rename(self._dados_fdb, dados_temp)
            self._log("Banco renomeado para DADOS_TEMP.fdb com sucesso.", "ok")

            # --- Passo 3: Criar pasta de backup se não existir ---
            pasta_bck = os.path.dirname(self._backup_bck)
            os.makedirs(pasta_bck, exist_ok=True)

            # --- Passo 4: Executar GBAK backup ---
            if self._stop:
                raise InterruptedError("Cancelado pelo usuário.")
            self._pct(20, "Executando GBAK backup...", "Isso pode levar alguns minutos")
            gbak_exe = os.path.join(self._fb_dir, "gbak.exe")
            cmd = [
                gbak_exe,
                "-b", "-v", "-garbage", "-limbo", "-ignore",
                "-user", GBAK_USER,
                "-pass", GBAK_PASSWORD,
                dados_temp,
                self._backup_bck,
            ]
            self._log(f"Comando: {' '.join(cmd)}", "dim")
            self._log("─" * 50, "dim")

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self._fb_dir,
            )

            for line in proc.stdout:
                if self._stop:
                    proc.terminate()
                    raise InterruptedError("Cancelado pelo usuário.")
                line = line.rstrip()
                if line:
                    kind = "err" if any(w in line.lower() for w in ("error", "erro", "failed")) else \
                           "warn" if any(w in line.lower() for w in ("warning", "aviso")) else "dim"
                    self._log(line, kind)

            proc.wait()
            self._log("─" * 50, "dim")

            if proc.returncode != 0:
                raise RuntimeError(f"GBAK encerrou com código {proc.returncode}.")

            # Verificar se arquivo foi gerado
            if not os.path.isfile(self._backup_bck):
                raise RuntimeError("Arquivo de backup não foi gerado.")

            tamanho = os.path.getsize(self._backup_bck)
            self._log(f"Backup gerado: {self._backup_bck}", "ok")
            self._log(f"Tamanho: {_fmt_size(tamanho)}", "ok")
            info["backup_path"] = self._backup_bck
            info["tamanho"]     = tamanho

            # --- Passo 5: Renomear DADOS_TEMP → DADOS ---
            self._pct(90, "Restaurando nome original do banco...")
            os.rename(dados_temp, self._dados_fdb)
            self._log("Banco renomeado de volta para DADOS.fdb.", "ok")

            sucesso = True
            self._pct(100, "Backup concluído com sucesso!")
            self._log("✔ Backup concluído com sucesso!", "ok")

        except InterruptedError as e:
            self._log(str(e), "warn")
            info["cancelado"] = True
            self._pct(0, "Backup cancelado.")
            self._log("Backup cancelado pelo usuário.", "warn")

        except Exception as e:
            self._log(f"Erro: {e}", "err")
            self._pct(0, "Erro durante o backup.")
            log.error(f"[BackupGBAK] Erro: {e}")

        finally:
            # Sempre tentar renomear de volta se DADOS_TEMP ainda existir
            if dados_temp != self._dados_fdb and os.path.isfile(dados_temp) \
                    and not os.path.isfile(self._dados_fdb):
                try:
                    os.rename(dados_temp, self._dados_fdb)
                    self._log("Banco renomeado de volta para DADOS.fdb (recuperação).", "warn")
                except Exception as ex:
                    self._log(f"ATENÇÃO: Não foi possível renomear de volta: {ex}", "err")

            # Reiniciar Firebird
            if self._servicos_parados:
                self._pct(95, "Reiniciando serviços do Firebird...")
                self._log("Reiniciando serviços do Firebird...", "info")
                start_firebird_services(self._servicos_parados)
                self._log("Serviços do Firebird reiniciados.", "ok")

        self.finished.emit(sucesso, info)


# ---------------------------------------------------------------------------
# Worker de Restaure
# ---------------------------------------------------------------------------

class RestaureGbakWorker(_BaseWorker):
    finished = pyqtSignal(bool, dict)

    _LOG_PREFIX = "[RestaureGBAK]"

    def __init__(
        self,
        firebird_dir: str,
        backup_bck: str,    # .bck de origem
        dados_novo: str,    # caminho completo de DADOSNOVO.fdb
    ):
        super().__init__()
        self._fb_dir           = firebird_dir
        self._backup_bck       = backup_bck
        self._dados_novo       = dados_novo
        self._servicos_parados: list[str] = []

    def run(self):
        sucesso = False
        info: dict = {}

        log.section("RESTAURE GBAK")
        self._log("Iniciando processo de restaure via GBAK...", "info")

        try:
            # --- Passo 1: Verificar .bck ---
            if not os.path.isfile(self._backup_bck):
                raise FileNotFoundError(f"Arquivo de backup não encontrado: {self._backup_bck}")
            self._log(f"Arquivo de backup: {self._backup_bck} ({_fmt_size(os.path.getsize(self._backup_bck))})", "info")

            # --- Passo 2: Parar Firebird ---
            if self._stop:
                raise InterruptedError("Cancelado pelo usuário.")
            self._pct(5, "Parando serviços do Firebird...")
            self._log("Parando serviços do Firebird...", "info")
            self._servicos_parados = stop_firebird_services()
            if self._servicos_parados:
                self._log(f"Serviços parados: {', '.join(self._servicos_parados)}", "ok")
            else:
                self._log("Nenhum serviço Firebird ativo (ou já parado).", "warn")

            # --- Passo 3: Verificar se DADOSNOVO já existe ---
            if os.path.isfile(self._dados_novo):
                self._log(f"ATENÇÃO: {self._dados_novo} já existe — será sobrescrito.", "warn")
                os.remove(self._dados_novo)

            # Criar pasta destino se não existir
            # BUG CORRIGIDO: os.path.dirname pode retornar "" se o caminho não tiver
            # separador, causando os.makedirs("") que lança FileNotFoundError.
            pasta_destino = os.path.dirname(self._dados_novo)
            if pasta_destino:
                os.makedirs(pasta_destino, exist_ok=True)

            # --- Passo 4: Executar GBAK restaure ---
            if self._stop:
                raise InterruptedError("Cancelado pelo usuário.")
            self._pct(15, "Executando GBAK restaure...", "Isso pode levar alguns minutos")
            gbak_exe = os.path.join(self._fb_dir, "gbak.exe")
            cmd = [
                gbak_exe,
                "-c", "-v",
                "-user", GBAK_USER,
                "-pass", GBAK_PASSWORD,
                self._backup_bck,
                self._dados_novo,
            ]
            self._log(f"Comando: {' '.join(cmd)}", "dim")
            self._log("─" * 50, "dim")

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self._fb_dir,
            )

            for line in proc.stdout:
                if self._stop:
                    proc.terminate()
                    raise InterruptedError("Cancelado pelo usuário.")
                line = line.rstrip()
                if line:
                    kind = "err" if any(w in line.lower() for w in ("error", "erro", "failed")) else \
                           "warn" if any(w in line.lower() for w in ("warning", "aviso")) else "dim"
                    self._log(line, kind)

            proc.wait()
            self._log("─" * 50, "dim")

            if proc.returncode != 0:
                raise RuntimeError(f"GBAK encerrou com código {proc.returncode}.")

            if not os.path.isfile(self._dados_novo):
                raise RuntimeError("Arquivo DADOSNOVO.fdb não foi gerado.")

            tamanho = os.path.getsize(self._dados_novo)
            self._log(f"Banco restaurado: {self._dados_novo}", "ok")
            self._log(f"Tamanho: {_fmt_size(tamanho)}", "ok")
            info["dados_novo"] = self._dados_novo
            info["tamanho"]    = tamanho

            sucesso = True
            self._pct(100, "Restaure concluído com sucesso!")
            self._log("✔ Restaure concluído! DADOSNOVO.fdb disponível para revisão.", "ok")
            self._log("O banco DADOS.fdb original não foi alterado.", "info")

        except InterruptedError as e:
            self._log(str(e), "warn")
            info["cancelado"] = True
            self._pct(0, "Restaure cancelado.")

        except Exception as e:
            self._log(f"Erro: {e}", "err")
            self._pct(0, "Erro durante o restaure.")
            log.error(f"[RestaureGBAK] Erro: {e}")

        finally:
            if self._servicos_parados:
                self._pct(95, "Reiniciando serviços do Firebird...")
                self._log("Reiniciando serviços do Firebird...", "info")
                start_firebird_services(self._servicos_parados)
                self._log("Serviços do Firebird reiniciados.", "ok")

        self.finished.emit(sucesso, info)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _fmt_size(b: int) -> str:
    if b >= 1_073_741_824:
        return f"{b/1_073_741_824:.1f} GB"
    if b >= 1_048_576:
        return f"{b/1_048_576:.1f} MB"
    return f"{b/1_024:.0f} KB"
