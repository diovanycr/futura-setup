"""
core/backup_gbak.py — Worker de Backup e Restaure via GBAK (Firebird)

CORRECAO PRINCIPAL (restaure falhando):
  Com o servico Firebird PARADO, o gbak opera em modo embedded (acesso direto
  ao arquivo .fdb). Nesse modo, -user/-pass nao sao suportados pois nao ha
  servidor para autenticar — causava falha imediata com "unavailable database".
  Solucao: omitir -user/-pass nos comandos gbak.

  Tambem substituido -c por -r (replace) para evitar conflito se o arquivo
  de destino ainda existir. Fallback automatico para -c caso -r nao seja
  suportado na versao instalada.

Fluxo Backup:
  1. Parar servicos Firebird
  2. Renomear .fdb para _TEMP.fdb
  3. gbak -b (sem -user/-pass: modo embedded com servico parado)
  4. Renomear _TEMP.fdb de volta
  5. Reiniciar servicos Firebird

Fluxo Restaure:
  1. Parar servicos Firebird
  2. Remover _NOVO.fdb se existir
  3. gbak -r (sem -user/-pass: modo embedded com servico parado)
  4. Reiniciar servicos Firebird

PROGRESSO POR TIMER:
  Durante a execucao do gbak (parte mais longa), um thread de timer avanca
  o progresso suavemente de pct_start ate pct_soft_end ao longo de
  estimated_seconds. Ao terminar o gbak, o progresso salta para pct_end.

  O timer usa interpolacao exponencial: avanca rapido no inicio e desacelera
  perto do teto — evitando que a barra "pare" perto do fim enquanto o gbak
  ainda esta rodando.

  Backup  — faixas:
    0–5%   : parar servicos
    5–15%  : renomear .fdb
    15–88% : execucao gbak (timer: estimativa 3 min, teto suave 85%)
    88–95% : renomear de volta
    95–100%: reiniciar servicos + conclusao

  Restaure — faixas:
    0–5%   : verificacoes
    5–88%  : execucao gbak (timer: estimativa 3 min, teto suave 85%)
    88–95% : finalizacoes
    95–100%: conclusao
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from core.logger import log
from core.installer import _BaseWorker
from core.firebird_services import (
    stop_firebird_services,
    start_firebird_services,
    find_firebird_dir,
    FIREBIRD_SERVICES,
)

GBAK_USER     = "sysdba"
GBAK_PASSWORD = "sbofutura"

# Tempo estimado (segundos) para o gbak completar.
# Nao precisa ser exato: o timer so avanca ate o teto suave (pct_soft_end),
# nunca bloqueia o processo. Ajuste conforme o tamanho tipico do banco.
_GBAK_ESTIMATED_SECONDS = 180   # 3 minutos


# ---------------------------------------------------------------------------
# Timer de progresso suave
# ---------------------------------------------------------------------------

class _ProgressTimer:
    """Avanca o progresso suavemente em background durante a execucao do gbak.

    Interpolacao exponencial: pct = start + span * (1 - e^(-k*t))
    onde k e calculado para atingir 95% do intervalo no tempo estimado.

    Isso faz a barra andar rapido no inicio e desacelerar perto do teto,
    evitando o efeito de "travar" proximo ao fim caso o gbak demore mais
    que o estimado.

    Uso:
        timer = _ProgressTimer(
            progress_fn, pct_start=15, pct_soft_end=85,
            estimated_seconds=180, tick=0.5
        )
        timer.start()
        # ... rodar gbak ...
        timer.stop()
        progress_fn(pct_hard_end, "Concluido")
    """

    def __init__(
        self,
        progress_fn,            # callable(pct: int, descricao: str)
        pct_start: int,
        pct_soft_end: int,
        estimated_seconds: float = 180.0,
        tick: float = 0.5,
        descricao: str = "Processando...",
    ):
        self._progress_fn  = progress_fn
        self._pct_start    = pct_start
        self._pct_soft_end = pct_soft_end
        self._estimated    = estimated_seconds
        self._tick         = tick
        self._descricao    = descricao
        self._stop_evt     = threading.Event()
        self._thread: threading.Thread | None = None

        import math
        # k tal que (1 - e^{-k * estimated}) = 0.95  =>  k = -ln(0.05) / estimated
        self._k = -math.log(0.05) / max(estimated_seconds, 1.0)

    def start(self):
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_evt.set()
        if self._thread:
            self._thread.join(timeout=self._tick * 3)

    def _run(self):
        import math
        t0   = time.monotonic()
        span = self._pct_soft_end - self._pct_start
        last = self._pct_start - 1   # garante que o primeiro tick sempre emite

        while not self._stop_evt.is_set():
            elapsed = time.monotonic() - t0
            frac    = 1.0 - math.exp(-self._k * elapsed)
            pct     = int(self._pct_start + span * frac)
            pct     = min(pct, self._pct_soft_end)

            if pct > last:
                last = pct
                self._progress_fn(pct, self._descricao)

            self._stop_evt.wait(self._tick)


# ---------------------------------------------------------------------------
# Funcoes auxiliares
# ---------------------------------------------------------------------------

def gerar_nome_backup(pasta_backup: str) -> str:
    """Gera caminho completo do .bck com data e hora."""
    ts   = datetime.now().strftime("%Y-%m-%d_%H-%M")
    nome = f"BACKUP_{ts}.bck"
    return os.path.join(pasta_backup, nome)


def _rodar_gbak(cmd: list, fb_dir: str, log_fn, stop_fn) -> int:
    """Executa gbak com streaming de output linha a linha. Retorna returncode.

    As credenciais sao passadas via variavel de ambiente ISC_USER / ISC_PASSWORD.
    Com o servico Firebird PARADO, o gbak opera em modo embedded e os flags
    -user/-pass da linha de comando sao ignorados — o unico meio de autenticar
    nesse modo e pelas variaveis de ambiente do processo.
    """
    env = os.environ.copy()
    env["ISC_USER"]     = GBAK_USER
    env["ISC_PASSWORD"] = GBAK_PASSWORD

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=fb_dir,
        env=env,
    )
    for line in proc.stdout:
        if stop_fn():
            proc.terminate()
            proc.wait()
            raise InterruptedError("Cancelado pelo usuario.")
        line = line.rstrip()
        if line:
            kind = (
                "err"  if any(w in line.lower() for w in ("error", "erro", "failed")) else
                "warn" if any(w in line.lower() for w in ("warning", "aviso"))         else
                "dim"
            )
            log_fn(line, kind)
    proc.wait()
    return proc.returncode if proc.returncode is not None else -1


# ---------------------------------------------------------------------------
# Worker de deteccao (curta duracao)
# ---------------------------------------------------------------------------

class _DetectarFirebirdWorker(QThread):
    """Detecta diretorio do Firebird em background.

    Signal 'finished' emite apenas o diretorio (str), vazio se nao encontrado.
    O try/except garante que o signal SEMPRE e emitido, mesmo em caso de erro.
    """
    finished = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            fb = find_firebird_dir() or ""
        except Exception as e:
            log.warn(f"[DetectarFirebird] Erro durante deteccao: {e}")
            fb = ""
        finally:
            self.finished.emit(fb)


# ---------------------------------------------------------------------------
# Worker de Backup
# ---------------------------------------------------------------------------

class BackupGbakWorker(_BaseWorker):
    finished = pyqtSignal(bool, dict)

    _LOG_PREFIX = "[BackupGBAK]"

    def __init__(self, firebird_dir: str, dados_fdb: str, backup_bck: str):
        super().__init__()
        self._fb_dir     = firebird_dir
        self._dados_fdb  = dados_fdb
        self._backup_bck = backup_bck
        self._servicos_parados: list[str] = []

    def run(self):
        dados_path = Path(self._dados_fdb)
        dados_temp = str(dados_path.with_name(dados_path.stem + "_TEMP.fdb"))
        sucesso    = False
        info: dict = {}
        timer: _ProgressTimer | None = None

        log.section("BACKUP GBAK")
        self._log("Iniciando processo de backup via GBAK...", "info")

        try:
            # --- Passo 1: Parar Firebird (0–5%) ---
            if self._stop:
                raise InterruptedError("Cancelado pelo usuario.")
            self._pct(2, "Parando servicos do Firebird...")
            self._log("Parando servicos do Firebird...", "info")
            self._servicos_parados = stop_firebird_services()
            if self._servicos_parados:
                self._log(f"Servicos parados: {', '.join(self._servicos_parados)}", "ok")
            else:
                self._log("Nenhum servico Firebird ativo encontrado (ou ja parado).", "warn")
            self._pct(5, "Servicos parados.")

            # --- Passo 2: Renomear .fdb para _TEMP (5–15%) ---
            if self._stop:
                raise InterruptedError("Cancelado pelo usuario.")
            self._pct(10, "Renomeando banco de dados...")
            self._log(f"Renomeando: {self._dados_fdb} -> {dados_temp}", "info")
            os.rename(self._dados_fdb, dados_temp)
            self._log("Banco renomeado para _TEMP com sucesso.", "ok")
            self._pct(15, "Banco renomeado. Preparando backup...")

            # --- Passo 3: Criar pasta de backup ---
            pasta_bck = os.path.dirname(self._backup_bck)
            if pasta_bck:
                os.makedirs(pasta_bck, exist_ok=True)

            # --- Passo 4: Executar GBAK backup (15–88%) ---
            if self._stop:
                raise InterruptedError("Cancelado pelo usuario.")

            gbak_exe = os.path.join(self._fb_dir, "gbak.exe")
            cmd = [
                gbak_exe,
                "-b", "-v", "-garbage", "-limbo", "-ignore",
                dados_temp,
                self._backup_bck,
            ]
            self._log(f"Comando: {' '.join(cmd)}", "dim")
            self._log("-" * 50, "dim")

            # Timer: avanca suavemente de 15% ate 85% enquanto o gbak roda
            timer = _ProgressTimer(
                progress_fn=lambda pct, desc: self._pct(pct, desc),
                pct_start=15,
                pct_soft_end=85,
                estimated_seconds=_GBAK_ESTIMATED_SECONDS,
                descricao="Executando backup...",
            )
            timer.start()

            rc = _rodar_gbak(cmd, self._fb_dir, self._log, lambda: self._stop)

            timer.stop()
            timer = None
            self._log("-" * 50, "dim")

            if rc != 0:
                raise RuntimeError(f"GBAK encerrou com codigo {rc}.")
            if not os.path.isfile(self._backup_bck):
                raise RuntimeError("Arquivo de backup nao foi gerado.")

            tamanho = os.path.getsize(self._backup_bck)
            self._log(f"Backup gerado: {self._backup_bck}", "ok")
            self._log(f"Tamanho: {_fmt_size(tamanho)}", "ok")
            info["backup_path"] = self._backup_bck
            info["tamanho"]     = tamanho

            # --- Passo 5: Renomear _TEMP de volta (88–95%) ---
            self._pct(88, "Backup concluido. Restaurando nome do banco...")
            os.rename(dados_temp, self._dados_fdb)
            self._log("Banco renomeado de volta para o nome original.", "ok")
            self._pct(92, "Aguardando reinicio dos servicos...")

            sucesso = True

        except InterruptedError as e:
            self._log(str(e), "warn")
            info["cancelado"] = True
            self._pct(0, "Backup cancelado.")
            self._log("Backup cancelado pelo usuario.", "warn")

        except Exception as e:
            self._log(f"Erro: {e}", "err")
            self._pct(0, "Erro durante o backup.")
            log.error(f"[BackupGBAK] Erro: {e}")

        finally:
            # Garante que o timer para mesmo em caso de excecao
            if timer is not None:
                timer.stop()

            # Recuperacao: renomear _TEMP de volta se o original nao existir
            if (
                dados_temp != self._dados_fdb
                and os.path.isfile(dados_temp)
                and not os.path.isfile(self._dados_fdb)
            ):
                try:
                    os.rename(dados_temp, self._dados_fdb)
                    self._log("Banco renomeado de volta (recuperacao).", "warn")
                except Exception as ex:
                    self._log(f"ATENCAO: Nao foi possivel renomear de volta: {ex}", "err")

            if self._servicos_parados:
                self._pct(95, "Reiniciando servicos do Firebird...")
                self._log("Reiniciando servicos do Firebird...", "info")
                start_firebird_services(self._servicos_parados)
                self._log("Servicos do Firebird reiniciados.", "ok")

            if sucesso:
                self._pct(100, "Backup concluido com sucesso!")
                self._log("Backup concluido com sucesso!", "ok")

        self.finished.emit(sucesso, info)


# ---------------------------------------------------------------------------
# Worker de Restaure
# ---------------------------------------------------------------------------

class RestaureGbakWorker(_BaseWorker):
    finished = pyqtSignal(bool, dict)

    _LOG_PREFIX = "[RestaureGBAK]"

    def __init__(self, firebird_dir: str, backup_bck: str, dados_novo: str):
        super().__init__()
        self._fb_dir     = firebird_dir
        self._backup_bck = backup_bck
        self._dados_novo = dados_novo
        self._servicos_parados: list[str] = []

    def run(self):
        sucesso    = False
        info: dict = {}
        timer: _ProgressTimer | None = None

        log.section("RESTAURE GBAK")
        self._log("Iniciando processo de restaure via GBAK...", "info")

        try:
            # --- Passo 1: Verificar .bck (0–5%) ---
            self._pct(2, "Verificando arquivo de backup...")
            if not os.path.isfile(self._backup_bck):
                raise FileNotFoundError(
                    f"Arquivo de backup nao encontrado: {self._backup_bck}"
                )
            tamanho_bck = os.path.getsize(self._backup_bck)
            self._log(
                f"Arquivo de backup: {self._backup_bck} ({_fmt_size(tamanho_bck)})",
                "info",
            )
            self._pct(5, "Arquivo verificado. Preparando restaure...")

            # --- Passo 2: Remover _NOVO se existir ---
            if self._stop:
                raise InterruptedError("Cancelado pelo usuario.")

            if os.path.isfile(self._dados_novo):
                self._log(f"Removendo arquivo existente: {self._dados_novo}", "warn")
                os.remove(self._dados_novo)

            pasta_destino = os.path.dirname(self._dados_novo)
            if pasta_destino:
                os.makedirs(pasta_destino, exist_ok=True)

            # --- Passo 3: Executar GBAK restaure via servidor (5–88%) ---
            if self._stop:
                raise InterruptedError("Cancelado pelo usuario.")

            gbak_exe  = os.path.join(self._fb_dir, "gbak.exe")
            dest_tcp  = f"localhost:{self._dados_novo}"

            cmd = [
                gbak_exe,
                "-c", "-v",
                "-user", GBAK_USER,
                "-pass", GBAK_PASSWORD,
                self._backup_bck,
                dest_tcp,
            ]
            cmd_log = cmd[:]
            cmd_log[cmd_log.index("-pass") + 1] = "***"
            self._log(f"Comando: {' '.join(cmd_log)}", "dim")
            self._log("-" * 50, "dim")

            # Timer: avanca suavemente de 5% ate 85% enquanto o gbak roda
            timer = _ProgressTimer(
                progress_fn=lambda pct, desc: self._pct(pct, desc),
                pct_start=5,
                pct_soft_end=85,
                estimated_seconds=_GBAK_ESTIMATED_SECONDS,
                descricao="Executando restaure...",
            )
            timer.start()

            rc = _rodar_gbak(cmd, self._fb_dir, self._log, lambda: self._stop)

            timer.stop()
            timer = None
            self._log("-" * 50, "dim")

            if not os.path.isfile(self._dados_novo):
                raise RuntimeError(
                    f"GBAK nao gerou o arquivo de destino (rc={rc}). "
                    "Verifique o log acima para detalhes do erro."
                )

            tamanho = os.path.getsize(self._dados_novo)
            self._log(f"Banco restaurado: {self._dados_novo}", "ok")
            self._log(f"Tamanho: {_fmt_size(tamanho)}", "ok")
            info["dados_novo"] = self._dados_novo
            info["tamanho"]    = tamanho

            self._pct(90, "Restaure concluido. Finalizando...")
            sucesso = True

        except InterruptedError as e:
            self._log(str(e), "warn")
            info["cancelado"] = True
            self._pct(0, "Restaure cancelado.")

        except Exception as e:
            self._log(f"Erro: {e}", "err")
            self._pct(0, "Erro durante o restaure.")
            log.error(f"[RestaureGBAK] Erro: {e}")

        finally:
            # Garante que o timer para mesmo em caso de excecao
            if timer is not None:
                timer.stop()

            if self._servicos_parados:
                self._pct(95, "Reiniciando servicos do Firebird...")
                self._log("Reiniciando servicos do Firebird...", "info")
                start_firebird_services(self._servicos_parados)
                self._log("Servicos do Firebird reiniciados.", "ok")

            if sucesso:
                self._pct(100, "Restaure concluido com sucesso!")
                self._log("Restaure concluido! Arquivo _NOVO.fdb disponivel para revisao.", "ok")
                self._log("O banco original nao foi alterado.", "info")

        self.finished.emit(sucesso, info)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _fmt_size(b: int) -> str:
    if b >= 1_073_741_824:
        return f"{b / 1_073_741_824:.1f} GB"
    if b >= 1_048_576:
        return f"{b / 1_048_576:.1f} MB"
    return f"{b / 1_024:.0f} KB"