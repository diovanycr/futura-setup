# =============================================================================
# FUTURA SETUP — UI: Backup & Restore Controller
# =============================================================================

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget, QTabWidget
from PyQt6.QtCore import Qt, pyqtSignal

from ui.theme import COLORS
from ui.theme_manager import theme_manager
from ui.widgets import PageHeader, SectionHeader, AlertBox, ResultBox, ConfirmDialog, make_secondary_btn
from ui.components.cards import PathSelectorCard
from ui.components.backup_widgets import BackupTab, RestoreTab
from core.backup_gbak import BackupGbakWorker, RestaureGbakWorker, gerar_nome_backup

class _StepConfig(QWidget):
    go_backup = pyqtSignal()
    go_restore = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        self.alert = AlertBox("Configuração do Engine", "info")
        lay.addWidget(self.alert)

        lay.addWidget(SectionHeader("Firebird Engine"))
        self.fld_fb = PathSelectorCard("Diretório do Firebird (contendo gbak.exe)", r"C:\Program Files\Firebird\Firebird_4_0", is_dir=True)
        lay.addWidget(self.fld_fb)

        # Abas
        self.tabs = QTabWidget()
        self.tab_backup = BackupTab()
        self.tab_restore = RestoreTab()
        self.tabs.addTab(self.tab_backup, "  Backup  ")
        self.tabs.addTab(self.tab_restore, "  Restaure  ")
        lay.addWidget(self.tabs)

        self.tab_backup.btn_start.clicked.connect(self.go_backup)
        self.tab_restore.btn_start.clicked.connect(self.go_restore)

        self._upd_style()
        theme_manager.theme_changed.connect(self._upd_style)

    def _upd_style(self, _mode=""):
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {COLORS['border']}; border-radius: 6px; background: transparent; }}
            QTabBar::tab {{ background: {COLORS['surface2']}; color: {COLORS['text_dim']}; padding: 8px 24px; border-radius: 4px; margin: 2px; }}
            QTabBar::tab:selected {{ background: {COLORS['accent']}; color: #ffffff; font-weight: bold; }}
        """)

class _StepResultado(QWidget):
    go_menu = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        self.alert = AlertBox("", "success")
        self.result_box = ResultBox("Resumo", [], "success")
        lay.addWidget(self.alert)
        lay.addWidget(self.result_box)
        lay.addStretch()
        self.btn_menu = make_secondary_btn("VOLTAR AO MENU", 180)
        self.btn_menu.clicked.connect(self.go_menu.emit)
        lay.addWidget(self.btn_menu)

    def set_resultado(self, op, ok, info):
        self.alert.set_text(f"{op} concluído com sucesso!" if ok else f"{op} falhou.")
        self.alert.set_kind("success" if ok else "danger")
        res_rows = [(k.replace("_"," ").title(), str(v)) for k, v in info.items() if k != "cancelado"]
        self.result_box.deleteLater()
        self.result_box = ResultBox(f"Resultado {op}", res_rows, "success" if ok else "error")
        self.layout().insertWidget(1, self.result_box)

class PageBackupGbak(QWidget):
    go_menu = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        
        self.header = PageHeader("BACKUP E RESTAURE", "Geração e restauração via GBAK")
        self.header.back_clicked.connect(self.go_menu.emit)
        lay.addWidget(self.header)

        self.stack = QStackedWidget()
        self.cfg = _StepConfig()
        self.res = _StepResultado()
        self.stack.addWidget(self.cfg)
        self.stack.addWidget(self.res)
        
        container = QWidget()
        c_lay = QVBoxLayout(container)
        c_lay.setContentsMargins(40, 20, 40, 20)
        c_lay.addWidget(self.stack)
        lay.addWidget(container, 1)

        self._worker = None
        self.cfg.go_backup.connect(self._on_backup)
        self.cfg.go_restore.connect(self._on_restore)
        self.res.go_menu.connect(self.go_menu.emit)

    def _on_backup(self):
        fb_dir = self.cfg.fld_fb.value
        fdb = self.cfg.tab_backup.fld_fdb.value
        dest_dir = self.cfg.tab_backup.fld_dest.value
        
        if not fdb or not dest_dir: return
        
        dest_file = gerar_nome_backup(dest_dir)
        self.cfg.tab_backup.set_running(True)
        self.cfg.tab_backup.console.clear_console()
        
        self._worker = BackupGbakWorker(fb_dir, fdb, dest_file)
        self._worker.log_line.connect(self.cfg.tab_backup.console.append_line)
        self._worker.progress.connect(lambda p, t, d: self.cfg.tab_backup.progress.set_progress(p, f"{t}: {d}"))
        self._worker.finished.connect(lambda s, i: self._finish("Backup", s, i))
        self._worker.start()

    def _on_restore(self):
        fb_dir = self.cfg.fld_fb.value
        bck = self.cfg.tab_restore.bck_selecionado
        fdb = self.cfg.tab_restore.fld_fdb.value
        
        if not bck or not fdb: return
        
        self.cfg.tab_restore.set_running(True)
        self.cfg.tab_restore.console.clear_console()
        
        self._worker = RestaureGbakWorker(fb_dir, bck, fdb)
        self._worker.log_line.connect(self.cfg.tab_restore.console.append_line)
        self._worker.progress.connect(lambda p, t, d: self.cfg.tab_restore.progress.set_progress(p, f"{t}: {d}"))
        self._worker.finished.connect(lambda s, i: self._finish("Restaure", s, i))
        self._worker.start()

    def _finish(self, op, ok, info):
        self.cfg.tab_backup.set_running(False)
        self.cfg.tab_restore.set_running(False)
        self.res.set_resultado(op, ok, info)
        self.stack.setCurrentIndex(1)

    def reset(self):
        self.stack.setCurrentIndex(0)