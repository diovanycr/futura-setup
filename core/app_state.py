# =============================================================================
# FUTURA SETUP — Core: Reactive App State
# =============================================================================

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, Any
from core.network import Servidor

class AppState(QObject):
    """
    Singleton que gerencia o estado global de forma reativa.
    Páginas e componentes podem se conectar a sinais de mudança de estado.
    """
    _instance = None
    
    # Sinais de mudança de estado
    servidor_changed = pyqtSignal(object)  # Optional[Servidor]
    pasta_changed    = pyqtSignal(str)     # Path de destino
    flow_mode_changed = pyqtSignal(str)     # "atalhos" | "terminal" | etc.
    worker_running_changed = pyqtSignal(bool)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppState, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        super().__init__()
        self._servidor: Optional[Servidor] = None
        self._pasta: str = ""
        self._flow_mode: str = "menu"
        self._worker_running: bool = False
        self._initialized = True

    # ── Getters / Setters ─────────────────────────────────────────────────────

    @property
    def servidor(self) -> Optional[Servidor]:
        return self._servidor

    @servidor.setter
    def servidor(self, val: Optional[Servidor]):
        if self._servidor != val:
            self._servidor = val
            self.servidor_changed.emit(val)

    @property
    def pasta(self) -> str:
        return self._pasta

    @pasta.setter
    def pasta(self, val: str):
        if self._pasta != val:
            self._pasta = val
            self.pasta_changed.emit(val)

    @property
    def flow_mode(self) -> str:
        return self._flow_mode

    @flow_mode.setter
    def flow_mode(self, val: str):
        if self._flow_mode != val:
            self._flow_mode = val
            self.flow_mode_changed.emit(val)

    @property
    def is_worker_running(self) -> bool:
        return self._worker_running

    def set_worker_running(self, val: bool):
        if self._worker_running != val:
            self._worker_running = val
            self.worker_running_changed.emit(val)

# Instância Global
state = AppState()
