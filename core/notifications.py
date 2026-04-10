# =============================================================================
# FUTURA SETUP — Core: System Notifications (Windows Toast)
# =============================================================================

import os
import sys
import threading
from typing import Optional

try:
    from win10toast import ToastNotifier
except ImportError:
    ToastNotifier = None

class NotificationManager:
    """
    Gerencia notificações nativas do Windows sem bloquear a thread principal.
    """
    def __init__(self):
        self._toaster: Optional[ToastNotifier] = ToastNotifier() if ToastNotifier else None
        self._icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "futura.ico")
        if not os.path.exists(self._icon_path):
            self._icon_path = None

    def notify(self, title: str, message: str, duration: int = 5):
        """Dispara uma notificação em uma thread separada."""
        if not self._toaster:
            print(f"Notification (Fallback): {title} - {message}")
            return

        def _run():
            try:
                self._toaster.show_toast(
                    title=title,
                    msg=message,
                    icon_path=self._icon_path,
                    duration=duration,
                    threaded=True
                )
            except Exception as e:
                print(f"Erro ao mostrar notificação: {e}")

        # O toaster.show_toast com threaded=True já faz isso, 
        # mas envolvemos em um try/except safe.
        threading.Thread(target=_run, daemon=True).start()

# Instância Global
notifier = NotificationManager()

def send_notification(title: str, message: str, duration: int = 5):
    notifier.notify(title, message, duration)
