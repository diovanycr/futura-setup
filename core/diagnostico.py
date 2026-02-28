# =============================================================================
# FUTURA SETUP — core/diagnostico.py
# Worker de diagnóstico de conectividade com um servidor Futura.
#
# Testes executados:
#   1. Ping (ICMP via subprocess)
#   2. Resolução de hostname (DNS/NetBIOS)
#   3. Acesso ao share \\servidor\Futura
#   4. Porta 3050 aberta (Firebird)
#   5. Leitura da versão (Futura.ini)
#
# Uso:
#   worker = DiagnosticoWorker("192.168.1.10")
#   worker.item_pronto.connect(self._on_item_pronto)   # (int, DiagItem)
#   worker.progresso.connect(self._on_pct)             # int 0-100
#   worker.finalizado.connect(self._on_finalizado)     # list[DiagItem]
#   worker.start()
# =============================================================================

from __future__ import annotations

import os
import re
import socket
import subprocess
import traceback
from dataclasses import dataclass

from PyQt6.QtCore import QThread, pyqtSignal


# ── MODELO ────────────────────────────────────────────────────────────────────

@dataclass
class DiagItem:
    """Resultado de um teste individual."""
    nome:    str
    status:  str          # "ok" | "warn" | "error" | "running"
    detalhe: str = ""


# ── WORKER ────────────────────────────────────────────────────────────────────

class DiagnosticoWorker(QThread):
    """
    Executa os testes de conectividade em background.

    Sinais:
      progresso(int)             — percentual 0-100 conforme testes concluem
      item_pronto(int, DiagItem) — índice e item atualizado a cada teste
      finalizado(list[DiagItem]) — emitido UMA ÚNICA VEZ ao término de todos os testes
    """
    progresso   = pyqtSignal(int)
    item_pronto = pyqtSignal(int, object)   # (índice, DiagItem)
    finalizado  = pyqtSignal(list)          # list[DiagItem] — emitido só no fim

    TIMEOUT_TCP  = 3   # segundos para teste de porta
    TIMEOUT_PING = 2   # segundos para ping

    # FIX: CREATE_NO_WINDOW só existe no Windows; fallback 0 evita AttributeError.
    _CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def __init__(self, alvo: str, parent=None):
        super().__init__(parent)
        self.alvo   = alvo
        self._parar = False

    def stop(self):
        self._parar = True

    def run(self):
        # FIX: try/except global — exceções não tratadas não fecham mais o processo.
        try:
            self._executar()
        except Exception:
            tb = traceback.format_exc()
            self.finalizado.emit([
                DiagItem("Erro interno", "error", tb)
            ])

    def _executar(self):
        testes = [
            DiagItem("Ping (ICMP)",                          "running"),
            DiagItem("Resolução de hostname",                "running"),
            DiagItem(f"Share \\\\{self.alvo}\\Futura",      "running"),
            DiagItem("Porta 3050 (Firebird)",                "running"),
            DiagItem("Versão do Futura",                     "running"),
        ]

        # FIX: removido o emit inicial de `finalizado` com estado "running".
        # A UI já cria os cards antes de chamar worker.start(), portanto esse
        # emit era desnecessário e causava _on_finalizado ser chamado duas vezes:
        # na primeira chamada a UI tentava montar a tela de resultado com itens
        # ainda "running" e navegava para _IDX_RESULTADO, gerando conflito de
        # estado que fechava o app.

        total = len(testes)

        def _atualizar(idx: int, item: DiagItem):
            testes[idx] = item
            pct = int((idx + 1) / total * 100)
            self.progresso.emit(pct)
            self.item_pronto.emit(idx, item)

        if self._parar:
            self.finalizado.emit(list(testes))
            return

        # 1. Ping
        ok_ping, detalhe_ping = self._ping(self.alvo)
        _atualizar(0, DiagItem(
            "Ping (ICMP)",
            "ok" if ok_ping else "error",
            detalhe_ping,
        ))

        if self._parar:
            self.finalizado.emit(list(testes))
            return

        # 2. Hostname
        hostname = self._resolver_hostname(self.alvo)
        _atualizar(1, DiagItem(
            "Resolução de hostname",
            "ok" if hostname else "warn",
            hostname if hostname else "Não foi possível resolver — usando IP diretamente",
        ))

        if self._parar:
            self.finalizado.emit(list(testes))
            return

        # 3. Share Futura
        ok_share, detalhe_share = self._testar_share(self.alvo)
        _atualizar(2, DiagItem(
            f"Share \\\\{self.alvo}\\Futura",
            "ok" if ok_share else "error",
            detalhe_share,
        ))

        if self._parar:
            self.finalizado.emit(list(testes))
            return

        # 4. Porta 3050 (Firebird)
        ok_fb, detalhe_fb = self._testar_porta(self.alvo, 3050)
        _atualizar(3, DiagItem(
            "Porta 3050 (Firebird)",
            "ok" if ok_fb else "warn",
            detalhe_fb,
        ))

        if self._parar:
            self.finalizado.emit(list(testes))
            return

        # 5. Versão
        versao = self._ler_versao(self.alvo) if ok_share else ""
        _atualizar(4, DiagItem(
            "Versão do Futura",
            "ok" if versao else "warn",
            versao if versao else "Não encontrada (Futura.ini ausente ou ilegível)",
        ))

        # Emit único e definitivo ao final
        self.finalizado.emit(list(testes))

    # ── TESTES INDIVIDUAIS ────────────────────────────────────────────────────

    def _ping(self, alvo: str) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                ["ping", "-n", "1", "-w", str(self.TIMEOUT_PING * 1000), alvo],
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT_PING + 2,
                creationflags=self._CREATE_NO_WINDOW,
            )
            ok = result.returncode == 0
            for line in result.stdout.splitlines():
                if "tempo=" in line.lower() or "time=" in line.lower():
                    return ok, line.strip()
            return ok, "Resposta recebida" if ok else "Sem resposta — host pode estar bloqueando ICMP"
        except subprocess.TimeoutExpired:
            return False, f"Timeout — ping não respondeu em {self.TIMEOUT_PING + 2}s"
        except FileNotFoundError:
            return False, "Comando 'ping' não encontrado no sistema"
        except Exception as e:
            return False, f"Erro ao executar ping: {e}"

    def _resolver_hostname(self, alvo: str) -> str:
        try:
            fqdn = socket.getfqdn(alvo)
            if fqdn and fqdn != alvo:
                return fqdn.split(".")[0].upper()
        except Exception:
            pass
        return ""

    def _testar_share(self, alvo: str) -> tuple[bool, str]:
        share = f"\\\\{alvo}\\Futura"
        try:
            if os.path.exists(share):
                n_arquivos = len(os.listdir(share))
                return True, f"{share} acessível — {n_arquivos} item(ns) encontrado(s)"
            return False, f"{share} não acessível — verifique permissões e compartilhamento"
        except PermissionError:
            return False, f"Acesso negado a {share} — credenciais necessárias"
        except Exception as e:
            return False, f"Erro ao acessar {share}: {e}"

    def _testar_porta(self, alvo: str, porta: int) -> tuple[bool, str]:
        try:
            with socket.create_connection((alvo, porta), timeout=self.TIMEOUT_TCP):
                return True, f"Porta {porta} aberta e respondendo"
        except socket.timeout:
            return False, f"Timeout — porta {porta} não respondeu em {self.TIMEOUT_TCP}s"
        except ConnectionRefusedError:
            return False, f"Porta {porta} recusou conexão — Firebird pode estar parado"
        except Exception as e:
            return False, f"Porta {porta} inacessível: {e}"

    def _ler_versao(self, alvo: str) -> str:
        ini = f"\\\\{alvo}\\Futura\\Futura.ini"
        try:
            with open(ini, encoding="latin-1", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if re.match(r"(?i)^(versao|version|versaosistema|ver)\s*=", line):
                        val = line.split("=", 1)[1].strip()
                        if val:
                            return val
        except Exception:
            pass
        return ""
