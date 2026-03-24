# =============================================================================
# FUTURA SETUP — UI: Login Dialog
# =============================================================================

import hashlib
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from ui.theme import COLORS, FONT_SANS

_SENHA_HASH = "1cfafff6d51a03662b85b93dc3417f51687034ba9a46682f5328257eff7133ed"  # senha: 1313
_LOGIN_MAX_TENTATIVAS = 3
_LOGIN_BLOQUEIO_SEG   = 30

class LoginDialog(QDialog):
    def __init__(self, app_icon_fn, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Futura Setup — Acesso")
        if app_icon_fn:
            self.setWindowIcon(app_icon_fn())
        self.setFixedSize(360, 260)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.MSWindowsFixedSizeDialogHint
        )

        self._tentativas  = 0
        self._bloqueado   = False
        self._autenticado = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(12)

        titulo = QLabel("Futura Setup")
        titulo.setFont(QFont(FONT_SANS, 15, QFont.Weight.Bold))
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitulo = QLabel("Digite a senha para continuar")
        subtitulo.setFont(QFont(FONT_SANS, 11))
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._campo = QLineEdit()
        self._campo.setEchoMode(QLineEdit.EchoMode.Password)
        self._campo.setPlaceholderText("Senha")
        self._campo.setFixedHeight(38)
        self._campo.setFont(QFont(FONT_SANS, 12))
        self._campo.returnPressed.connect(self._verificar)

        self._msg = QLabel("")
        self._msg.setFont(QFont(FONT_SANS, 11))
        self._msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg.setWordWrap(True)

        self._btn = QPushButton("Entrar")
        self._btn.setFixedHeight(38)
        self._btn.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._verificar)

        lay.addWidget(titulo)
        lay.addWidget(subtitulo)
        lay.addSpacing(8)
        lay.addWidget(self._campo)
        lay.addWidget(self._msg)
        lay.addWidget(self._btn)

        self._upd_style()

    def _upd_style(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {COLORS['surface']};
            }}
            QLineEdit {{
                background: {COLORS['bg']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 0 12px;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {COLORS['accent']};
            }}
            QPushButton {{
                background: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {COLORS['accent']};
                opacity: 0.9;
            }}
            QPushButton:disabled {{
                background: {COLORS['text_disabled']};
                color: {COLORS['text_dim']};
            }}
        """)

    def _verificar(self):
        if self._bloqueado:
            return
        senha = self._campo.text()
        hash_digitado = hashlib.sha256(senha.encode()).hexdigest()
        if hash_digitado == _SENHA_HASH:
            self._autenticado = True
            self.accept()
        else:
            self._tentativas += 1
            restam = _LOGIN_MAX_TENTATIVAS - self._tentativas
            self._campo.clear()
            if self._tentativas >= _LOGIN_MAX_TENTATIVAS:
                self._bloquear()
            else:
                self._msg.setStyleSheet(f"color: {COLORS['danger']};")
                self._msg.setText(
                    f"Senha incorreta. {restam} tentativa{'s' if restam > 1 else ''} restante{'s' if restam > 1 else ''}."
                )

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
        self._msg.setStyleSheet(f"color: {COLORS['warn']};")
        self._msg.setText(
            f"Muitas tentativas. Aguarde {self._tempo_restante}s para tentar novamente."
        )
        self._tempo_restante -= 1
        if self._tempo_restante < 0:
            self._timer.stop()
            self._bloqueado   = False
            self._tentativas  = 0
            self._campo.setEnabled(True)
            self._btn.setEnabled(True)
            self._msg.setStyleSheet(f"color: {COLORS['text_mid']};")
            self._msg.setText("Voce pode tentar novamente.")
            self._campo.setFocus()

    def autenticado(self) -> bool:
        return self._autenticado
