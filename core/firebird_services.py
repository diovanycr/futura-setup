# =============================================================================
# FUTURA SETUP — core/firebird_services.py
# Utilitários centralizados para controle de serviços do Firebird.
#
# Antes havia duas implementações independentes:
#   - core/atualizador.py  (com CREATE_NO_WINDOW e log)
#   - core/backup_gbak.py  (sem CREATE_NO_WINDOW, sem log, sem reversed)
#
# Esta versão unifica o melhor das duas:
#   - CREATE_NO_WINDOW em todos os subprocessos
#   - Log via core.logger em stop/start
#   - returncode == 0 antes de checar "RUNNING" (correção de bug)
#   - start reinicia na ordem inversa (Guardian antes do Server)
#   - Constantes de caminhos e serviços definidas aqui
# =============================================================================

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from core.logger import log

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

FIREBIRD_SERVICES: list[str] = [
    "FirebirdServerDefaultInstance",
    "FirebirdGuardianDefaultInstance",
    "Firebird Server - DefaultInstance",
    "Firebird Guardian - DefaultInstance",
]

FIREBIRD_CONF_PATHS: list[str] = [
    r"C:\Program Files (x86)\Firebird\Firebird_3_0\firebird.conf",
    r"C:\Program Files\Firebird\Firebird_3_0\firebird.conf",
    r"C:\Program Files (x86)\Firebird\Firebird_2_5\firebird.conf",
    r"C:\Program Files\Firebird\Firebird_2_5\firebird.conf",
]

FIREBIRD_PATHS: list[str] = [
    r"C:\Program Files (x86)\Firebird\Firebird_3_0",
    r"C:\Program Files\Firebird\Firebird_3_0",
    r"C:\Program Files (x86)\Firebird\Firebird_2_5",
    r"C:\Program Files\Firebird\Firebird_2_5",
]

_NO_WINDOW = subprocess.CREATE_NO_WINDOW

# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

def stop_firebird_services() -> list[str]:
    """
    Para todos os serviços do Firebird que estiverem rodando.
    Retorna lista dos nomes efetivamente parados.
    """
    parados: list[str] = []
    for svc in FIREBIRD_SERVICES:
        try:
            r = subprocess.run(
                ["sc", "query", svc],
                capture_output=True, text=True, timeout=5,
                creationflags=_NO_WINDOW,
            )
            if r.returncode == 0 and "RUNNING" in r.stdout:
                subprocess.run(
                    ["net", "stop", svc, "/y"],
                    capture_output=True, text=True, timeout=20,
                    creationflags=_NO_WINDOW,
                )
                parados.append(svc)
        except Exception as e:
            log.warn(f"[Firebird] Erro ao parar serviço '{svc}': {e}")
    return parados


def start_firebird_services(servicos: list[str]) -> None:
    """
    Reinicia os serviços listados na ordem inversa
    (garante que Guardian sobe antes do Server).
    """
    for svc in reversed(servicos):
        try:
            subprocess.run(
                ["net", "start", svc],
                capture_output=True, text=True, timeout=20,
                creationflags=_NO_WINDOW,
            )
        except Exception as e:
            log.warn(f"[Firebird] Erro ao reiniciar serviço '{svc}': {e}")


def find_firebird_dir() -> Optional[str]:
    """
    Retorna o diretório do Firebird instalado (onde gbak.exe está), ou None.
    Verifica primeiro pela presença do gbak.exe, depois só pelo diretório.
    """
    for path in FIREBIRD_PATHS:
        if Path(path, "gbak.exe").is_file():
            return path
    for conf in FIREBIRD_CONF_PATHS:
        parent = Path(conf).parent
        if parent.exists():
            return str(parent)
    return None
