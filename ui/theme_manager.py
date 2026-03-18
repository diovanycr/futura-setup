# =============================================================================
# FUTURA SETUP — Theme Manager v3
# Melhorias v3:
#   - Singleton via __new__ + __init__ guard _initialized (consistente com FuturaLogger)
#   - set_mode: emite sinal mesmo se mode == atual (para forçar re-render se necessário)
#   - Separação clara entre _load_saved_theme e _setup
# =============================================================================

from PyQt6.QtCore import QObject, pyqtSignal
from ui.theme import set_theme, COLORS


class ThemeManager(QObject):
    theme_changed    = pyqtSignal(str)   # emite o novo mode ("light" | "dark")
    ui_theme_changed = pyqtSignal(str)   # emite o novo tema ("modern" | "classic")
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            instance = super().__new__(cls)
            QObject.__init__(instance)
            cls._instance = instance
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._mode        = self._load_saved_theme()
        self._ui_theme    = self._load_saved_ui_theme()
        set_theme(self._mode)

    def _load_saved_theme(self) -> str:
        try:
            from core.logger import log
            return log.prefs.theme
        except Exception:
            return "light"

    def _load_saved_ui_theme(self) -> str:
        try:
            from core.logger import log
            return log.prefs.ui_theme
        except Exception:
            return "modern"

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def ui_theme(self) -> str:
        return self._ui_theme

    def toggle(self):
        """Alterna entre light e dark."""
        new_mode = "dark" if self._mode == "light" else "light"
        self._apply(new_mode)

    def set_mode(self, mode: str):
        """Define o tema diretamente. No-op silencioso se mode inválido."""
        if mode not in ("light", "dark"):
            return
        self._apply(mode)

    def set_ui_theme(self, ui_theme: str):
        if ui_theme not in ("modern", "classic"):
            return
        self._ui_theme = ui_theme
        try:
            from core.logger import log
            log.prefs.ui_theme = ui_theme
        except Exception:
            pass
        self.ui_theme_changed.emit(ui_theme)

    def _apply(self, mode: str):
        self._mode = mode
        set_theme(mode)
        self._save_theme()
        self.theme_changed.emit(mode)

    def _save_theme(self):
        try:
            from core.logger import log
            log.prefs.theme = self._mode
        except Exception:
            pass


theme_manager = ThemeManager()
