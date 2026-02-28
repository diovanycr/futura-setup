# =============================================================================
# FUTURA SETUP — Descoberta de Rede
# Melhorias v2:
#   - testar_conectividade: usa create_connection (sem alterar timeout global)
#   - ScanWorker: max_workers reduzido de 60 → 25 (mais seguro em redes corp.)
#   - MetodoScan: NamedTuple em vez de tupla anônima (mais legível)
#   - _emit_log: grava em disco para todos os kinds (ok, warn, err, info)
# =============================================================================

import re
import socket
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from dataclasses import dataclass
from typing import NamedTuple, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core.logger import log


# ── MODELO ───────────────────────────────────────────────────────────────────

@dataclass
class Servidor:
    ip:       str
    hostname: str = ""
    path:     str = ""
    path_ip:  str = ""
    version:  str = ""

    def __post_init__(self):
        if not self.path_ip:
            self.path_ip = f"\\\\{self.ip}\\Futura"
        if not self.hostname:
            self.hostname = self.ip
        if not self.path:
            self.path = f"\\\\{self.hostname}\\Futura"

    @property
    def display(self) -> str:
        if self.hostname != self.ip:
            return f"{self.hostname}  (IP: {self.ip})"
        return self.ip

    @property
    def version_display(self) -> str:
        return self.version if self.version else "versão desconhecida"


# ── METODO DE SCAN ────────────────────────────────────────────────────────────

class MetodoScan(NamedTuple):
    key:      str
    nome:     str
    descricao: str


# ── ARP ──────────────────────────────────────────────────────────────────────

def get_hosts_via_arp() -> list[str]:
    """Retorna lista de IPs do cache ARP, excluindo broadcast/multicast."""
    ips = []
    try:
        out = subprocess.check_output(
            ["arp", "-a"], text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        for line in out.splitlines():
            m = re.match(r'\s+(\d+\.\d+\.\d+\.\d+)\s+', line)
            if m:
                ip = m.group(1)
                if not re.match(r'^(224\.|239\.|255\.|0\.|127\.)', ip):
                    if ip not in ips:
                        ips.append(ip)
    except Exception as e:
        log.warn(f"Erro ao ler cache ARP: {e}")
    return ips


# ── CONECTIVIDADE ─────────────────────────────────────────────────────────────

def testar_conectividade(hosts: list[str] | None = None) -> bool:
    """
    Testa conectividade tentando conexão TCP na porta 80.
    Usa create_connection com timeout explícito — não altera socket.setdefaulttimeout()
    globalmente, o que poderia afetar outras threads.
    """
    from config import CONNECTIVITY_HOSTS
    hosts = hosts or CONNECTIVITY_HOSTS
    for h in hosts:
        try:
            with socket.create_connection((h, 80), timeout=5):
                return True
        except Exception:
            continue
    return False


# ── TESTA SHARE ──────────────────────────────────────────────────────────────

def _read_futura_version(share: str) -> str:
    """Tenta ler a versão do Futura a partir do Futura.ini no share."""
    ini_path = f"{share}\\Futura.ini"
    try:
        with open(ini_path, encoding="latin-1", errors="replace") as f:
            for line in f:
                line = line.strip()
                if re.match(r"(?i)^(versao|version|versaosistema|ver)\s*=", line):
                    val = line.split("=", 1)[1].strip()
                    if val:
                        return val
    except Exception:
        pass
    return ""


def _test_futura_share(ip: str) -> Optional[tuple[str, str]]:
    """
    Retorna (ip, version) se o share \\\\ip\\Futura existir com marcadores válidos.
    Retorna None se não encontrado.
    """
    try:
        share = f"\\\\{ip}\\Futura"
        if os.path.exists(share):
            has_ini = os.path.exists(f"{share}\\Futura.ini")
            has_exe = os.path.exists(f"{share}\\FuturaServer.exe")
            if has_ini or has_exe:
                version = _read_futura_version(share) if has_ini else ""
                return ip, version
    except Exception:
        pass
    return None


# ── RESOLVER HOSTNAME ─────────────────────────────────────────────────────────

def resolve_hostname(ip: str) -> str:
    """Tenta resolver nome NetBIOS/DNS. Retorna string vazia se falhar."""
    try:
        fqdn = socket.getfqdn(ip)
        if fqdn and fqdn != ip:
            return fqdn.split(".")[0].upper()
    except Exception:
        pass
    try:
        out = subprocess.check_output(
            ["nbtstat", "-A", ip], text=True, timeout=4,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        for line in out.splitlines():
            m = re.match(r'\s*(\S+)\s+<00>\s+UNIQUE', line)
            if m:
                return m.group(1).strip().upper()
    except Exception:
        pass
    return ""


# ── WORKER THREAD ─────────────────────────────────────────────────────────────

class ScanWorker(QThread):
    """
    Worker que executa o scan em background e emite sinais para a UI.
    Métodos suportados definidos em METODOS (lista de MetodoScan).
    """
    log_line    = pyqtSignal(str, str)
    progress    = pyqtSignal(int, int)
    finished    = pyqtSignal(list)
    status_text = pyqtSignal(str)

    # Usando MetodoScan (NamedTuple) — acesso por .key, .nome, .descricao
    METODOS: list[MetodoScan] = [
        MetodoScan("auto",              "Automático",
                   "Tenta os 4 métodos em sequência até encontrar"),
        MetodoScan("paralelo_rapido",   "Paralelo Rápido",
                   "Timeout 10s — todos os hosts ao mesmo tempo"),
        MetodoScan("paralelo_lento",    "Paralelo Rede Lenta",
                   "Timeout 30s — para redes com alta latência"),
        MetodoScan("sequencial_padrao", "Sequencial Padrão",
                   "3s por host, IP por IP"),
        MetodoScan("sequencial_lento",  "Sequencial Rede Lenta",
                   "8s por host, IP por IP"),
    ]

    _METODO_CFG = {
        "auto":              {"tipo": "auto"},
        "paralelo_rapido":   {"tipo": "paralelo",   "timeout_s": 10},
        "paralelo_lento":    {"tipo": "paralelo",   "timeout_s": 30},
        "sequencial_padrao": {"tipo": "sequencial", "timeout_s": 3},
        "sequencial_lento":  {"tipo": "sequencial", "timeout_s": 8},
    }

    def __init__(self, metodo: str = "auto", parent=None):
        super().__init__(parent)
        self.metodo = metodo
        self._stop  = False

    def stop(self):
        self._stop = True

    def run(self):
        self._emit_log("=== INICIANDO ESCANEAMENTO ===", "info")
        self.status_text.emit("Lendo cache ARP...")

        ips = get_hosts_via_arp()
        self._emit_log(f"{len(ips)} host(s) no cache ARP", "info")

        if not ips:
            self._emit_log("Nenhum host no cache ARP.", "warn")
            self.finished.emit([])
            return

        cfg = self._METODO_CFG.get(self.metodo, self._METODO_CFG["auto"])

        if cfg["tipo"] == "auto":
            result = self._run_auto(ips)
        elif cfg["tipo"] == "paralelo":
            result = self._run_paralelo(ips, cfg["timeout_s"])
        else:
            result = self._run_sequencial(ips, cfg["timeout_s"])

        self.finished.emit(result)

    # ── AUTO ──────────────────────────────────────────────────────────────────

    def _run_auto(self, ips: list[str]) -> list[Servidor]:
        configs = [
            ("Paralelo rápido (10s)",          "paralelo",   10),
            ("Paralelo rede lenta (30s)",       "paralelo",   30),
            ("Sequencial padrão (3s/host)",     "sequencial", 3),
            ("Sequencial rede lenta (8s/host)", "sequencial", 8),
        ]
        for nome, tipo, timeout in configs:
            if self._stop:
                break
            self._emit_log(f"Tentando: {nome}", "info")
            self.status_text.emit(f"Tentando: {nome}")
            r = (self._run_paralelo(ips, timeout) if tipo == "paralelo"
                 else self._run_sequencial(ips, timeout))
            if r:
                return r
            self._emit_log("Nenhum servidor encontrado com este método.", "warn")
        return []

    # ── PARALELO ──────────────────────────────────────────────────────────────

    def _run_paralelo(self, ips: list[str], timeout_s: int) -> list[Servidor]:
        self._emit_log(f"Disparando {len(ips)} testes em paralelo...", "info")
        self.status_text.emit(f"Escaneando {len(ips)} host(s)...")
        encontrados: list[tuple[str, str]] = []
        done = 0

        # max_workers=25: seguro em redes corporativas sem saturar SMB
        with ThreadPoolExecutor(max_workers=25) as ex:
            futures = {ex.submit(_test_futura_share, ip): ip for ip in ips}
            try:
                for f in as_completed(futures, timeout=timeout_s):
                    if self._stop:
                        break
                    done += 1
                    self.progress.emit(done, len(ips))
                    result = f.result()
                    if result:
                        ip, version = result
                        encontrados.append((ip, version))
                        self._emit_log(f"[ENCONTRADO] {ip}", "ok")
            except TimeoutError:
                self._emit_log(f"Timeout atingido ({timeout_s}s)", "warn")

        self._emit_log(f"{len(encontrados)} servidor(es) encontrado(s)", "info")
        return self._resolver_nomes(encontrados) if encontrados else []

    # ── SEQUENCIAL ────────────────────────────────────────────────────────────

    def _run_sequencial(self, ips: list[str], timeout_s: int) -> list[Servidor]:
        self._emit_log(f"Verificando {len(ips)} host(s) sequencialmente...", "info")
        encontrados: list[tuple[str, str]] = []
        for i, ip in enumerate(ips):
            if self._stop:
                break
            self.progress.emit(i + 1, len(ips))
            self.status_text.emit(f"Testando {ip}...")
            r = _test_futura_share(ip)
            if r:
                encontrados.append(r)
                self._emit_log(f"[ENCONTRADO] {ip}", "ok")
            else:
                self._emit_log(f"[não] {ip}", "dim")

        self._emit_log(f"{len(encontrados)} servidor(es) encontrado(s)", "info")
        return self._resolver_nomes(encontrados) if encontrados else []

    # ── RESOLVER NOMES ────────────────────────────────────────────────────────

    def _resolver_nomes(self, encontrados: list[tuple[str, str]]) -> list[Servidor]:
        servidores: list[Servidor] = []
        self._emit_log("Resolvendo nomes das máquinas...", "info")
        for ip, version in encontrados:
            self.status_text.emit(f"Resolvendo {ip}...")
            hostname = resolve_hostname(ip)
            ver_txt  = f" (v{version})" if version else ""
            if hostname:
                self._emit_log(f"{ip} → {hostname}{ver_txt}", "ok")
                servidores.append(Servidor(
                    ip=ip, hostname=hostname,
                    path=f"\\\\{hostname}\\Futura",
                    path_ip=f"\\\\{ip}\\Futura",
                    version=version,
                ))
            else:
                self._emit_log(f"{ip} → (usando IP){ver_txt}", "warn")
                servidores.append(Servidor(
                    ip=ip, hostname=ip,
                    path=f"\\\\{ip}\\Futura",
                    path_ip=f"\\\\{ip}\\Futura",
                    version=version,
                ))
        return servidores

    # ── LOG ───────────────────────────────────────────────────────────────────

    def _emit_log(self, msg: str, kind: str):
        """Grava no arquivo de log E emite sinal para a UI."""
        if kind == "ok":
            log.ok(msg)
        elif kind == "warn":
            log.warn(msg)
        elif kind == "err":
            log.error(msg)
        else:
            log.info(msg)
        self.log_line.emit(msg, kind)
