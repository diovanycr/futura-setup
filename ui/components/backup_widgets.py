# =============================================================================
# FUTURA SETUP — UI Components: Backup & Restoration
# =============================================================================

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.components.base import h_line, spacer, label
from ui.components.buttons import make_primary_btn, make_secondary_btn
from ui.components.cards import PathSelectorCard
from ui.components.feedback import SectionHeader, ProgressBlock, AlertBox
from ui.components.containers import LogConsole

class BackupTab(QWidget):
    go_backup = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(10)

        lay.addWidget(SectionHeader("Banco de Dados"))
        self.fld_fdb = PathSelectorCard("Arquivo do Banco de Dados (.fdb)", "Ex: C:\\Futura\\Dados\\DADOS.fdb", is_dir=False)
        lay.addWidget(self.fld_fdb)

        self.alert_ver = AlertBox("", "info")
        self.alert_ver.setVisible(False)
        lay.addWidget(self.alert_ver)

        lay.addWidget(SectionHeader("Destino do Backup"))
        self.fld_dest = PathSelectorCard("Pasta de Destino (.bck)", "Ex: C:\\Futura\\Backup", is_dir=True)
        lay.addWidget(self.fld_dest)

        self.progress = ProgressBlock("Backup em Andamento")
        self.progress.setVisible(False)
        lay.addWidget(self.progress)

        self.console = LogConsole(max_height=200)
        self.console.setVisible(False)
        lay.addWidget(self.console)

        lay.addWidget(h_line())
        
        row = QHBoxLayout()
        self.btn_start = make_primary_btn("INICIAR BACKUP", 180)
        self.btn_cancel = make_secondary_btn("CANCELAR", 120)
        self.btn_cancel.setVisible(False)
        
        row.addWidget(self.btn_start)
        row.addWidget(self.btn_cancel)
        row.addStretch()
        lay.addLayout(row)

    def set_running(self, running: bool):
        self.btn_start.setEnabled(not running)
        self.btn_cancel.setVisible(running)
        self.progress.setVisible(running)
        self.console.setVisible(running)

class RestoreTab(QWidget):
    go_restore = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bck_selecionado = ""
        self._btn_itens = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(10)

        lay.addWidget(SectionHeader("Pasta de Backups"))
        self.fld_dir = PathSelectorCard("Localização dos arquivos .bck", "Ex: C:\\Futura\\Backup", is_dir=True)
        lay.addWidget(self.fld_dir)

        # Lista de backups
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFixedHeight(120)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_w = QWidget()
        self.list_lay = QVBoxLayout(self.list_w)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(4)
        self.scroll.setWidget(self.list_w)
        lay.addWidget(self.scroll)

        lay.addWidget(SectionHeader("Destino da Restauração"))
        self.fld_fdb = PathSelectorCard("Novo Arquivo (.fdb)", "Ex: C:\\Futura\\Dados\\DADOS_NOVO.fdb", is_dir=False)
        lay.addWidget(self.fld_fdb)

        self.progress = ProgressBlock("Restauração em Andamento")
        self.progress.setVisible(False)
        lay.addWidget(self.progress)

        self.console = LogConsole(max_height=200)
        self.console.setVisible(False)
        lay.addWidget(self.console)

        lay.addWidget(h_line())
        
        row = QHBoxLayout()
        self.btn_start = make_primary_btn("INICIAR RESTAURAÇÃO", 180)
        self.btn_cancel = make_secondary_btn("CANCELAR", 120)
        self.btn_cancel.setVisible(False)
        
        row.addWidget(self.btn_start)
        row.addWidget(self.btn_cancel)
        row.addStretch()
        lay.addLayout(row)

        self.fld_dir.edit.textChanged.connect(self.carregar_lista)

    def carregar_lista(self):
        while self.list_lay.count():
            item = self.list_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        
        path = self.fld_dir.value
        if not os.path.isdir(path): return

        files = [f for f in os.listdir(path) if f.lower().endswith(".bck")]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(path, x)), reverse=True)

        self._btn_itens = []
        for f in files:
            full = os.path.join(path, f)
            btn = QPushButton(f"  {f}")
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, p=full, b=btn: self._selecionar(p, b))
            self.list_lay.addWidget(btn)
            self._btn_itens.append(btn)
            
            # Auto-selecionar o primeiro (mais recente)
            if not self._bck_selecionado:
                self._selecionar(full, btn)

        self.list_lay.addStretch()
        self._upd_btns()

    def _selecionar(self, path, btn):
        self._bck_selecionado = path
        for b in self._btn_itens: b.setChecked(b is btn)
        self._upd_btns()

    def _upd_btns(self):
        for b in self._btn_itens:
            sel = b.isChecked()
            bg = COLORS["accent"] if sel else COLORS["surface2"]
            fg = "#ffffff" if sel else COLORS["text_mid"]
            b.setStyleSheet(f"QPushButton {{ background: {bg}; color: {fg}; text-align: left; border-radius: 4px; padding-left: 10px; border: 1px solid {COLORS['border']}; }}")

    def set_running(self, running: bool):
        self.btn_start.setEnabled(not running)
        self.btn_cancel.setVisible(running)
        self.progress.setVisible(running)
        self.console.setVisible(running)

    @property
    def bck_selecionado(self): return self._bck_selecionado
