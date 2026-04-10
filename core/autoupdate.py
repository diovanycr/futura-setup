# =============================================================================
# FUTURA SETUP — Core: Auto-Update Utility
# =============================================================================

import requests
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from config import APP_VERSION

class UpdateWorker(QThread):
    """
    Verifica se há uma nova versão disponível no repositório.
    """
    check_finished = pyqtSignal(bool, str, str) # (has_new, version, download_url)

    def __init__(self, parent=None):
        super().__init__(parent)
        # URL fictícia para exemplo, deve ser trocada pela real do repositório/API
        self.version_url = "https://raw.githubusercontent.com/user/repo/main/version.json"

    def run(self):
        try:
            # Simulando consulta a uma API de versão
            # response = requests.get(self.version_url, timeout=5)
            # data = response.json()
            # latest_version = data.get("version", APP_VERSION)
            # download_url = data.get("url", "")
            
            # Mock para demonstração (se a versão atual fosse 4.3.0 e a nova fosse 5.0.0)
            latest_version = "5.0.0"
            download_url = "https://example.com/FuturaSetup_v5.0.0.exe"
            
            has_new = self._is_newer(latest_version, APP_VERSION)
            self.check_finished.emit(has_new, latest_version, download_url)
        except Exception as e:
            print(f"Erro ao verificar atualização: {e}")
            self.check_finished.emit(False, APP_VERSION, "")

    def _is_newer(self, latest: str, current: str) -> bool:
        try:
            l_parts = [int(p) for p in latest.split(".")]
            c_parts = [int(p) for p in current.split(".")]
            return l_parts > c_parts
        except:
            return latest != current
