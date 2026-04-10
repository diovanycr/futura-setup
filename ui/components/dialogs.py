# =============================================================================
# FUTURA SETUP — UI Components: Dialogs
# =============================================================================

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ui.theme import COLORS, FONT_SANS
from ui.theme_manager import theme_manager
from ui.components.buttons import make_secondary_btn, make_primary_btn

class ConfirmDialog(QDialog):
    def __init__(self, title: str, lines: list[str], parent=None,
                 btn_ok: str = "Confirmar", btn_cancel: str = "Cancelar",
                 width: int = 460):
        super().__init__(parent)
        self.setWindowTitle("Confirmar")
        self.setFixedWidth(width)
        self._confirmed = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(8)

        t = QLabel(title)
        t.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
        t.setWordWrap(True)
        lay.addWidget(t)

        for line in lines:
            lbl = QLabel(line)
            lbl.setFont(QFont(FONT_SANS, 11))
            lbl.setWordWrap(True)
            lay.addWidget(lbl)

        lay.addSpacing(8)
        row = QHBoxLayout()
        b_cancel = make_secondary_btn(btn_cancel, 110)
        b_ok = make_primary_btn(btn_ok, 110)
        b_cancel.clicked.connect(self.reject)
        b_ok.clicked.connect(self._accept)
        row.addStretch(); row.addWidget(b_cancel); row.addWidget(b_ok)
        lay.addLayout(row)
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _accept(self):
        self._confirmed = True
        self.accept()

    def confirmed(self) -> bool: return self._confirmed

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(f"QDialog {{ background: {COLORS['surface']}; }} "
                           f"QLabel {{ color: {COLORS['text']}; background: transparent; }}")

class WorkerGuardDialog(QWidget):
    confirmed = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(420, 200)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lay = QVBoxLayout(self)
        box = QWidget()
        box.setObjectName("box")
        box_lay = QVBoxLayout(box)
        box_lay.setContentsMargins(28, 24, 28, 24)
        
        title = QLabel("Operação em andamento")
        title.setFont(QFont(FONT_SANS, 14, QFont.Weight.Bold))
        msg = QLabel("Deseja interromper a operação atual?")
        msg.setWordWrap(True)
        
        btn_row = QHBoxLayout()
        btn_cancel = make_secondary_btn("Continuar", 120)
        btn_confirm = make_primary_btn("Sair", 120)
        btn_cancel.clicked.connect(self.close)
        btn_confirm.clicked.connect(self.confirmed.emit)
        btn_confirm.clicked.connect(self.close)
        btn_row.addStretch(); btn_row.addWidget(btn_cancel); btn_row.addWidget(btn_confirm)
        
        box_lay.addWidget(title); box_lay.addWidget(msg); box_lay.addLayout(btn_row)
        lay.addWidget(box)
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(f"QWidget#box {{ background: {COLORS['surface']}; border: 1.5px solid {COLORS['warn']}; border-radius: 10px; }} "
                           f"QLabel {{ color: {COLORS['text']}; background: transparent; }}")
