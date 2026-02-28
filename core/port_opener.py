"""
core/port_opener.py — Worker para abrir/remover portas no Firewall do Windows via netsh

Executa netsh advfirewall firewall como Administrador em tempo real,
emitindo cada linha para a UI via log_line.
"""

from __future__ import annotations

import subprocess
import ctypes
from typing import Literal

from PyQt6.QtCore import QThread, pyqtSignal

from core.logger import log
from core.installer import _BaseWorker

# ---------------------------------------------------------------------------
# Mapa de portas conhecidas (porta → nome)
# ---------------------------------------------------------------------------
KNOWN_PORTS: dict[int, str] = {
    20: "FTP Data", 21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
    53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS",
    445: "SMB", 465: "SMTPS", 587: "SMTP", 993: "IMAPS", 995: "POP3S",
    1433: "SQL Server", 1521: "Oracle", 3000: "Node.js", 3050: "Firebird",
    3306: "MySQL", 3389: "RDP", 4200: "Angular", 5000: "Flask",
    5173: "Vite", 5432: "PostgreSQL", 5601: "Kibana", 5672: "RabbitMQ",
    6379: "Redis", 6443: "Kubernetes", 8000: "Django", 8080: "HTTP Alt",
    8443: "HTTPS Alt", 8888: "Jupyter", 9000: "PHP-FPM",
    9090: "Prometheus", 9200: "Elasticsearch", 27017: "MongoDB",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def rule_name(port: int, proto: str, direction: str) -> str:
    """Gera nome único para a regra do firewall."""
    base  = KNOWN_PORTS.get(port, f"Porta_{port}").replace(" ", "_").replace("/", "_")
    d_tag = "IN" if direction == "in" else "OUT"
    return f"FuturaSetup_{base}_{port}_{proto.upper()}_{d_tag}"


def build_commands(
    ports: list[int],
    proto: Literal["TCP", "UDP", "BOTH"],
    direction: Literal["in", "out", "both"],
    action: Literal["add", "delete"],
) -> list[tuple[str, list[str]]]:
    """
    Retorna lista de (descrição, comando) para cada regra a executar.
    """
    protos = ["TCP", "UDP"] if proto == "BOTH" else [proto]
    dirs   = ["in", "out"]  if direction == "both" else [direction]
    cmds: list[tuple[str, list[str]]] = []

    for port in ports:
        for pr in protos:
            for dr in dirs:
                name = rule_name(port, pr, dr)
                if action == "add":
                    cmd = [
                        "netsh", "advfirewall", "firewall", "add", "rule",
                        f"name={name}",
                        f"dir={dr}",
                        "action=allow",
                        f"protocol={pr}",
                        f"localport={port}",
                        "enable=yes",
                        "profile=any",
                    ]
                    desc = f"[{port}] {pr} {dr.upper()} → {KNOWN_PORTS.get(port, 'porta ' + str(port))}"
                else:
                    cmd = [
                        "netsh", "advfirewall", "firewall", "delete", "rule",
                        f"name={name}",
                    ]
                    desc = f"[{port}] Removendo {pr} {dr.upper()}"
                cmds.append((desc, cmd))

    return cmds


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class PortOpenerWorker(_BaseWorker):
    finished = pyqtSignal(bool, dict)

    _LOG_PREFIX = "[PortOpener]"

    def __init__(
        self,
        ports: list[int],
        proto: Literal["TCP", "UDP", "BOTH"],
        direction: Literal["in", "out", "both"],
        action: Literal["add", "delete"],
    ):
        super().__init__()
        self._ports     = ports
        self._proto     = proto
        self._direction = direction
        self._action    = action

    def run(self):
        action_label = "abertura" if self._action == "add" else "remoção"
        log.section(f"PORT OPENER — {action_label.upper()} DE PORTAS")
        self._log(f"Iniciando {action_label} de portas: {self._ports}", "info")

        sucesso = False
        info: dict = {"ok": [], "fail": []}

        if not is_admin():
            self._log("ERRO: O programa não está rodando como Administrador.", "err")
            self._log("Reinicie o Futura Setup como Administrador para alterar o Firewall.", "warn")
            self.finished.emit(False, info)
            return

        cmds = build_commands(self._ports, self._proto, self._direction, self._action)
        total = len(cmds)

        if total == 0:
            self._log("Nenhuma regra a aplicar — lista de portas vazia.", "warn")
            self.finished.emit(True, {"ok": [], "fail": [], "total": 0,
                                      "action": self._action, "ports": self._ports})
            return

        for i, (desc, cmd) in enumerate(cmds):
            if self._stop:
                self._log("Cancelado pelo usuário.", "warn")
                break

            pct = int((i / total) * 100)
            self._pct(pct, desc)
            self._log(desc, "info")
            self._log(f"  → {' '.join(cmd)}", "dim")

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=15,
                )
                out = (result.stdout + result.stderr).strip()
                if result.returncode == 0:
                    self._log(f"  ✔ OK — {out or 'Regra aplicada.'}", "ok")
                    info["ok"].append(desc)
                else:
                    self._log(f"  ✕ Falhou — {out}", "err")
                    info["fail"].append(desc)
            except Exception as e:
                self._log(f"  ✕ Exceção: {e}", "err")
                info["fail"].append(desc)

        sucesso = len(info["fail"]) == 0 and not self._stop
        info["total"]  = total
        info["action"] = self._action
        info["ports"]  = self._ports

        if sucesso:
            self._pct(100, f"Concluído! {len(info['ok'])} regra(s) aplicada(s).")
            self._log(f"✔ {action_label.capitalize()} concluída com sucesso.", "ok")
        else:
            self._pct(100, f"Concluído com {len(info['fail'])} falha(s).")
            self._log(f"⚠ {len(info['fail'])} regra(s) falharam.", "warn")

        self.finished.emit(sucesso, info)
