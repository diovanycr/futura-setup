# =============================================================================
# FUTURA SETUP — Logger v3
# Melhorias v3:
#   - Prefs._load: valida tipo antes de atualizar (evita corrupção silenciosa)
#   - FuturaLogger: guard _initialized para evitar re-init acidental
#   - read_log_tail: lê apenas as últimas N linhas (evita 8MB em memória)
#   - LogSignals documentado — usado para streaming em tempo real na UI
# =============================================================================

import json
import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal


# ── PREFS ─────────────────────────────────────────────────────────────────────

class Prefs:
    """
    Persistência de preferências do usuário em APPDATA/Futura/prefs.json.
    Salva: tema, últimos servidores, últimas pastas de instalação.
    """
    _MAX_HIST = 5

    def __init__(self, prefs_path: Path):
        self._path = prefs_path
        self._data: dict = {
            "theme":           "light",
            "servidores_hist": [],
            "pastas_hist":     [],
            "portas_hist":     [],
        }
        self._load()

    def _load(self):
        try:
            if self._path.exists():
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
                # Só aceita se for dict — rejeita JSON corrompido ou de tipo errado
                if isinstance(loaded, dict):
                    # Valida campos individualmente para não aceitar tipos errados
                    if isinstance(loaded.get("theme"), str):
                        self._data["theme"] = loaded["theme"]
                    if isinstance(loaded.get("servidores_hist"), list):
                        self._data["servidores_hist"] = loaded["servidores_hist"]
                    if isinstance(loaded.get("pastas_hist"), list):
                        self._data["pastas_hist"] = loaded["pastas_hist"]
                    if isinstance(loaded.get("portas_hist"), list):
                        self._data["portas_hist"] = loaded["portas_hist"]
        except Exception:
            pass  # prefs corrompidas: usa defaults silenciosamente

    def save(self):
        try:
            self._path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass

    # ── Tema ──

    @property
    def theme(self) -> str:
        return self._data.get("theme", "light")

    @theme.setter
    def theme(self, value: str):
        if value in ("light", "dark"):
            self._data["theme"] = value
            self.save()

    # ── Histórico de servidores ──

    @property
    def servidores_hist(self) -> list[dict]:
        return self._data.get("servidores_hist", [])

    def add_servidor(self, ip: str, hostname: str, path: str):
        hist = self.servidores_hist
        hist = [s for s in hist if s.get("ip") != ip]
        hist.insert(0, {"ip": ip, "hostname": hostname, "path": path})
        self._data["servidores_hist"] = hist[:self._MAX_HIST]
        self.save()

    # ── Histórico de pastas de instalação ──

    @property
    def pastas_hist(self) -> list[str]:
        return self._data.get("pastas_hist", [])

    def add_pasta(self, pasta: str):
        hist = self.pastas_hist
        hist = [p for p in hist if p != pasta]
        hist.insert(0, pasta)
        self._data["pastas_hist"] = hist[:self._MAX_HIST]
        self.save()

    # ── Histórico de portas abertas ──

    @property
    def portas_hist(self) -> list[dict]:
        """Lista de dicts: {ports: [int], proto: str, direction: str, ts: str}"""
        return self._data.get("portas_hist", [])

    def add_portas(self, ports: list[int], proto: str, direction: str):
        from datetime import datetime
        entry = {
            "ports":     ports,
            "proto":     proto,
            "direction": direction,
            "ts":        datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        hist = self.portas_hist
        # Remove entrada idêntica se já existir
        hist = [h for h in hist if h.get("ports") != ports or h.get("proto") != proto]
        hist.insert(0, entry)
        self._data["portas_hist"] = hist[:self._MAX_HIST]
        self.save()


# ── LOGGER ────────────────────────────────────────────────────────────────────

class LogSignals(QObject):
    """
    Sinal para streaming de linhas de log em tempo real para a UI.
    Conecte a new_line para exibir logs ao vivo em qualquer widget.
    Assinatura: new_line(mensagem: str, kind: str)
      kind ∈ {"ok", "info", "warn", "err"}
    """
    new_line = pyqtSignal(str, str)


class FuturaLogger:
    """
    Singleton de logging. Use o objeto global `log` importado deste módulo.
    Não instancie diretamente.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Guard: evita re-inicialização se __init__ for chamado novamente
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._setup()

    def _setup(self):
        self.signals = LogSignals()

        app_dir = Path(os.environ.get("APPDATA", ".")) / "Futura"
        app_dir.mkdir(parents=True, exist_ok=True)

        self.log_path   = app_dir / "futura_setup.log"
        self.prefs_path = app_dir / "prefs.json"
        self.prefs      = Prefs(self.prefs_path)

        self._logger = logging.getLogger("futura_setup")
        self._logger.setLevel(logging.DEBUG)

        if not self._logger.handlers:
            # RotatingFileHandler: máx 2 MB, mantém 3 backups → nunca passa de 8 MB
            fh = logging.handlers.RotatingFileHandler(
                self.log_path,
                maxBytes    = 2 * 1024 * 1024,
                backupCount = 3,
                encoding    = "utf-8",
            )
            fh.setFormatter(logging.Formatter(
                "[%(asctime)s] [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            ))
            self._logger.addHandler(fh)

    # ── Emit interno ──

    def _emit(self, msg: str, kind: str):
        self.signals.new_line.emit(msg, kind)

    # ── API pública ──

    def info(self, msg: str):
        self._logger.info(msg)
        self._emit(msg, "info")

    def ok(self, msg: str):
        self._logger.info(f"[OK] {msg}")
        self._emit(f"[OK] {msg}", "ok")

    def warn(self, msg: str):
        self._logger.warning(msg)
        self._emit(f"[!] {msg}", "warn")

    def error(self, msg: str):
        self._logger.error(msg)
        self._emit(f"[X] {msg}", "err")

    def section(self, msg: str):
        line = f"=== {msg} ==="
        self._logger.info(line)
        self._emit(line, "info")

    # ── Leitura ──

    def read_log(self) -> str:
        """Lê apenas o arquivo de log atual."""
        try:
            return self.log_path.read_text(encoding="utf-8")
        except Exception:
            return "(Sem log disponível)"

    def read_log_all(self) -> str:
        """
        Lê todos os arquivos de log (rotacionados + atual) em ordem cronológica.
        Atenção: pode carregar até ~8 MB. Para exibição filtrada, prefira
        read_log_tail() que limita o volume lido.
        """
        parts = []
        for i in range(3, 0, -1):
            bk = Path(str(self.log_path) + f".{i}")
            if bk.exists():
                try:
                    parts.append(bk.read_text(encoding="utf-8"))
                except Exception:
                    pass
        try:
            parts.append(self.log_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return "\n".join(parts) if parts else "(Sem log disponível)"

    def read_log_tail(self, max_lines: int = 5000) -> str:
        """
        Lê as últimas `max_lines` linhas do log (todos os arquivos rotacionados).
        Mais eficiente que read_log_all() para exibição na UI.
        """
        all_lines: list[str] = []
        for i in range(3, 0, -1):
            bk = Path(str(self.log_path) + f".{i}")
            if bk.exists():
                try:
                    all_lines.extend(bk.read_text(encoding="utf-8").splitlines())
                except Exception:
                    pass
        try:
            all_lines.extend(self.log_path.read_text(encoding="utf-8").splitlines())
        except Exception:
            pass
        return "\n".join(all_lines[-max_lines:]) if all_lines else "(Sem log disponível)"


# Singleton global — importe e use diretamente: from core.logger import log
log = FuturaLogger()
