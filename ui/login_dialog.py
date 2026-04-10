# =============================================================================
# FUTURA SETUP — UI: Login Dialog
# =============================================================================

import hashlib
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QWidget
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, pyqtProperty
from PyQt6.QtGui import QFont, QColor

from ui.theme import COLORS, FONT_SANS
from ui.theme_manager import theme_manager

_SENHA_HASH = "1cfafff6d51a03662b85b93dc3417f51687034ba9a46682f5328257eff7133ed"  # senha: 1313
_LOGIN_MAX_TENTATIVAS = 3
_LOGIN_BLOQUEIO_SEG   = 30

class LoginDialog(QDialog):
    def __init__(self, app_icon_fn, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Futura Setup — Acesso")
        if app_icon_fn:
            self.setWindowIcon(app_icon_fn())
        self.setFixedSize(380, 280)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.MSWindowsFixedSizeDialogHint
        )

        self._tentativas  = 0
        self._bloqueado   = False
        self._autenticado = False
        
        # Shake Animation
        self._shake_anim = QPropertyAnimation(self, b"pos")
        self._shake_anim.setDuration(400)
        self._shake_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(10)

        self._logo_lbl = QLabel("FUTURA SETUP")
        self._logo_lbl.setFont(QFont(FONT_SANS, 16, QFont.Weight.Bold))
        self._logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._subtitulo = QLabel("Acesso Restrito")
        self._subtitulo.setFont(QFont(FONT_SANS, 10))
        self._subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._campo = QLineEdit()
        self._campo.setEchoMode(QLineEdit.EchoMode.Password)
        self._campo.setPlaceholderText("Senha de acesso")
        self._campo.setFixedHeight(42)
        self._campo.setFont(QFont(FONT_SANS, 11))
        self._campo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._campo.returnPressed.connect(self._verificar)

        self._msg = QLabel("")
        self._msg.setFont(QFont(FONT_SANS, 9))
        self._msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg.setWordWrap(True)
        self._msg.setFixedHeight(20)

        self._btn = QPushButton("ENTRAR")
        self._btn.setFixedHeight(42)
        self._btn.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._verificar)

        lay.addWidget(self._logo_lbl)
        lay.addWidget(self._subtitulo)
        lay.addSpacing(10)
        lay.addWidget(self._campo)
        lay.addWidget(self._msg)
        lay.addWidget(self._btn)

        self._upd_style()
        theme_manager.theme_changed.connect(self._upd_style)

    def _upd_style(self, _mode=""):
        self.setStyleSheet(f"QDialog {{ background: {COLORS['surface']}; }}")
        
        self._logo_lbl.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        self._subtitulo.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
        
        self._campo.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['bg']};
                color: {COLORS['text']};
                border: 1.5px solid {COLORS['border']};
                border-radius: 8px;
                padding: 0 12px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """)
        
        txt_color = "#ffffff" if theme_manager.mode == "light" else "#001826"
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                color: {txt_color};
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{ background: {COLORS['accent']}; opacity: 0.9; }}
            QPushButton:pressed {{ background: {COLORS['accent']}; opacity: 0.8; }}
            QPushButton:disabled {{
                background: {COLORS['panel_hover']};
                color: {COLORS['text_disabled']};
            }}
        """)

    def _shake(self):
        """Efeito de balanço (shake) para erro."""
        orig_pos = self.pos()
        self._shake_anim.stop()
        self._shake_anim.setKeyValues([
            (0.0, orig_pos),
            (0.1, orig_pos + QPoint(-10, 0)),
            (0.2, orig_pos + QPoint(10, 0)),
            (0.3, orig_pos + QPoint(-10, 0)),
            (0.4, orig_pos + QPoint(10, 0)),
            (0.5, orig_pos + QPoint(-5, 0)),
            (0.6, orig_pos + QPoint(5, 0)),
            (1.0, orig_pos)
        ])
        self._shake_anim.start()

    def _verificar(self):
        if self._bloqueado: return
        
        senha = self._campo.text()
        hash_digitado = hashlib.sha256(senha.encode()).hexdigest()
        
        if hash_digitado == _SENHA_HASH:
            self._autenticado = True
            self.accept()
        else:
            self._shake()
            self._tentativas += 1
            restam = _LOGIN_MAX_TENTATIVAS - self._tentativas
            self._campo.clear()
            
            if self._tentativas >= _LOGIN_MAX_TENTATIVAS:
                self._bloquear()
            else:
                self._msg.setStyleSheet(f"color: {COLORS['danger']}; background: transparent;")
                self._msg.setText(f"Senha incorreta. {restam} tentativa{'s' if restam > 1 else ''} restantes.")

    def _bloquear(self):
        self._bloqueado    = True
        self._campo.setEnabled(False)
        self._btn.setEnabled(False)
        self._tempo_restante = _LOGIN_BLOQUEIO_SEG
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick_bloqueio)
        self._timer.start()
        self._tick_bloqueio()

    def _tick_bloqueio(self):
        self._msg.setStyleSheet(f"color: {COLORS['warn']}; background: transparent;")
        self._msg.setText(f"Bloqueado: {self._tempo_restante}s")
        self._tempo_restante -= 1
        if self._tempo_restante < 0:
            self._timer.stop()
            self._bloqueado   = False
            self._tentativas  = 0
            self._campo.setEnabled(True)
            self._btn.setEnabled(True)
            self._msg.setText("")
            self._campo.setFocus()

    def autenticado(self) -> bool:
        return self._autenticado
