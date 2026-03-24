# =============================================================================
# FUTURA SETUP — UI: Crash Dialog
# =============================================================================

import sys
import os
import subprocess
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTextEdit, QFrame, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.widgets import spacer, h_line

class CrashDialog(QDialog):
    """
    Diálogo exibido quando ocorre uma exceção não tratada (Crash).
    Informa o usuário e fornece ferramentas de diagnóstico para suporte.
    """
    def __init__(self, error_msg: str, stacktrace: str, log_dir: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Futura Setup — Erro Critico")
        self.setFixedSize(560, 480)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        
        self._error_msg = error_msg
        self._stacktrace = stacktrace
        self._log_dir = log_dir

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        # -- Header --
        header = QHBoxLayout()
        icon_lbl = QLabel("⚠️")
        icon_lbl.setFont(QFont(FONT_SANS, 32))
        
        title_lay = QVBoxLayout()
        title = QLabel("Opa! Ocorreu um erro inesperado.")
        title.setFont(QFont(FONT_SANS, 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['danger']};")
        
        subtitle = QLabel("O sistema encontrou um problema e precisa ser fechado.")
        subtitle.setFont(QFont(FONT_SANS, 11))
        subtitle.setStyleSheet(f"color: {COLORS['text_mid']};")
        
        title_lay.addWidget(title)
        title_lay.addWidget(subtitle)
        
        header.addWidget(icon_lbl)
        header.addLayout(title_lay, 1)
        lay.addLayout(header)

        # -- Error Summary --
        summary_box = QFrame()
        summary_box.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['accent_dim']};
                border: 1px solid {COLORS['danger']};
                border-radius: 6px;
            }}
        """)
        sum_lay = QVBoxLayout(summary_box)
        msg_lbl = QLabel(error_msg)
        msg_lbl.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
        msg_lbl.setStyleSheet("border: none; background: transparent;")
        msg_lbl.setWordWrap(True)
        sum_lay.addWidget(msg_lbl)
        lay.addWidget(summary_box)

        # -- Technical Details --
        lay.addWidget(QLabel("Detalhes tecnicos (Stacktrace):"))
        self._console = QTextEdit()
        self._console.setReadOnly(True)
        self._console.setPlainText(stacktrace)
        self._console.setFont(QFont(FONT_MONO, 10))
        self._console.setStyleSheet(f"""
            background: #111111;
            color: #CCCCCC;
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
            padding: 8px;
        """)
        lay.addWidget(self._console)

        # -- Actions --
        btn_lay = QHBoxLayout()
        
        btn_copy = QPushButton("Copiar Detalhes")
        btn_copy.setFixedHeight(36)
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.clicked.connect(self._copy_to_clipboard)
        
        btn_logs = QPushButton("Abrir Pasta de Logs")
        btn_logs.setFixedHeight(36)
        btn_logs.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logs.clicked.connect(self._open_logs)
        
        btn_close = QPushButton("Fechar")
        btn_close.setFixedHeight(36)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 0 20px;
            }}
            QPushButton:hover {{ background: {COLORS['accent_hover']}; }}
        """)
        btn_close.clicked.connect(self.accept)

        btn_lay.addWidget(btn_copy)
        btn_lay.addWidget(btn_logs)
        btn_lay.addStretch()
        btn_lay.addWidget(btn_close)
        lay.addLayout(btn_lay)

        self.setStyleSheet(f"background: {COLORS['surface']}; color: {COLORS['text']};")

    def _copy_to_clipboard(self):
        text = f"ERRO: {self._error_msg}\n\nSTACKTRACE:\n{self._stacktrace}"
        QApplication.clipboard().setText(text)
        sender = self.sender()
        if isinstance(sender, QPushButton):
            sender.setText("Copiado!")
            QTimer.singleShot(2000, lambda: sender.setText("Copiar Detalhes"))

    def _open_logs(self):
        if self._log_dir and os.path.isdir(self._log_dir):
            os.startfile(self._log_dir)

def show_crash(msg: str, trace: str, log_dir: str = ""):
    """Funcao auxiliar para instanciar e executar o dialogo."""
    dlg = CrashDialog(msg, trace, log_dir)
    dlg.exec()
