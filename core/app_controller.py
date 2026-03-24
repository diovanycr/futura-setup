# =============================================================================
# FUTURA SETUP — Core: App Controller
# =============================================================================

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from core.logger import log

class AppController(QObject):
    """
    Controlador central de lógica de negócio.
    Gerencia timers de polling, status de workers e orquestração entre páginas.
    """
    
    status_updated = pyqtSignal()
    busy_state_changed = pyqtSignal(bool)

    def __init__(self, navigation_manager, sidebar, parent=None):
        super().__init__(parent)
        self._nav = navigation_manager
        self._sidebar = sidebar
        
        self._busy_timer = QTimer(self)
        self._busy_timer.setInterval(200)
        self._busy_timer.timeout.connect(self._on_spin_tick)
        
        self._flow_mode = None # 'atalhos' | 'terminal' | None

    def start(self):
        """Inicia os loops de monitoramento."""
        self._busy_timer.start()

    def stop(self):
        """Para monitoramentos e workers."""
        self._busy_timer.stop()
        self.stop_all_workers()

    @property
    def flow_mode(self):
        return self._flow_mode

    @flow_mode.setter
    def flow_mode(self, val):
        self._flow_mode = val

    def _on_spin_tick(self):
        """
        Polling periódico para atualizar indicadores de 'Busy' na barra lateral.
        Migrado do MainWindow._spin_tick original.
        """
        active_pages = self._nav.active_pages()
        for idx in range(20): # Limite arbitrário de páginas
            nav_item = self._nav.get_nav_item(idx)
            if not nav_item: continue
            
            # Tenta encontrar a página correspondente se ela já existir
            page = None
            for p in active_pages:
                # Nota: Aqui dependemos da página estar no mapa do navigation_manager
                # O navigation_manager já nos dá as instâncias ativas.
                pass
            
            # Versão simplificada usando o mapa do nav_manager diretamente
            page = self._nav._pages_map.get(idx)
            if not page: continue
            
            worker = getattr(page, "_worker", None)
            is_running = bool(worker and hasattr(worker, "isRunning") and worker.isRunning())
            
            if nav_item._busy != is_running:
                nav_item.set_busy(is_running)
            elif is_running:
                nav_item._spin_tick()

    def get_active_workers(self) -> list:
        """Retorna lista de workers em execução em todas as páginas."""
        result = []
        for page in self._nav.active_pages():
            worker = getattr(page, "_worker", None)
            if worker and hasattr(worker, "isRunning") and worker.isRunning():
                result.append(worker)
        return result

    def is_worker_running(self) -> bool:
        return len(self.get_active_workers()) > 0

    def stop_all_workers(self):
        """Solicita a parada de todos os workers ativos."""
        for worker in self.get_active_workers():
            if hasattr(worker, "stop"):
                worker.stop()
            if hasattr(worker, "wait"):
                worker.wait(2000)

    def log_startup(self, app_version, is_admin):
        import platform, sys
        log.section(
            f"FUTURA SETUP v{app_version} INICIADO — "
            f"Windows {platform.version()} — "
            f"Python {sys.version.split()[0]} — "
            f"Admin: {is_admin}"
        )
