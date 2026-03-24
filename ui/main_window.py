# =============================================================================
# FUTURA SETUP — UI: Main Window
# =============================================================================

from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt

from ui.theme import COLORS, get_stylesheet
from ui.theme_manager import theme_manager
from ui.widgets import FadeStackedWidget, WorkerGuardDialog
from ui.components.sidebar import Sidebar
from ui.navigation_manager import (
    NavigationManager, IDX_MENU, IDX_SCAN, IDX_ATALHOS, IDX_TERMINAL, 
    IDX_UTILITARIOS, IDX_LOG, IDX_RESTAURAR, IDX_ATUALIZACAO,
    IDX_BACKUP_GBAK, IDX_PORT_OPENER, IDX_DIAGNOSTICO, IDX_EDITAR_FUNC,
    IDX_IMPLANTAR_MOBILE, IDX_SHUTDOWN_ONLINE, IDX_INSTALAR_FIREBIRD,
    IDX_VERIFICAR_VERSAO_FDB, IDX_FB_PORTABLE
)
from core.app_controller import AppController
from config import APP_VERSION

class MainWindow(QMainWindow):
    def __init__(self, app_icon_fn):
        super().__init__()
        self.setWindowTitle(f"Futura Setup v{APP_VERSION}")
        if app_icon_fn:
            self.setWindowIcon(app_icon_fn())
        self.setMinimumSize(960, 620)
        self.resize(1100, 680)

        # ── Layout Base ──────────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = Sidebar()
        root.addWidget(self._sidebar)

        self._stack = FadeStackedWidget()
        root.addWidget(self._stack)

        # ── Gestão de Navegação e Orquestração ───────────────────────────────
        self._nav = NavigationManager(self._stack, self._sidebar)
        self._controller = AppController(self._nav, self._sidebar)

        # ── Conexão de Eventos ──────────────────────────────────────────────
        self._setup_connections()
        
        # ── Estado Inicial ───────────────────────────────────────────────────
        self._close_guard = False
        self._controller.start()
        self._go_menu()

    def _setup_connections(self):
        """Conecta eventos das páginas e da sidebar ao controlador/navegador."""
        
        # Conexões da Sidebar
        self._sidebar.nav_menu.on_click(lambda: self._navigate(self._go_menu))
        self._sidebar.nav_utilitarios.on_click(lambda: self._navigate(self._go_utilitarios))
        self._sidebar.nav_atualizacao.on_click(lambda: self._navigate(self._go_atualizacao))
        
        self._sidebar.nav_atalhos.on_click(
            lambda: self._navigate(lambda: self._nav.show_page(IDX_ATALHOS))
        )
        self._sidebar.nav_terminal.on_click(
            lambda: self._navigate(lambda: self._nav.show_page(IDX_TERMINAL))
        )

        # Conexões Dinâmicas (Signals das páginas)
        # O NavigationManager emite um sinal toda vez que uma página muda/é criada
        self._nav.page_changed.connect(self._on_page_ready)

    def _on_page_ready(self, idx, page):
        """Conecta sinais específicos de cada página quando elas são instanciadas."""
        if idx == IDX_MENU:
            page.go_atalhos.connect(self._start_atalhos)
            page.go_terminal.connect(self._start_terminal)
            page.go_atualizacao.connect(self._go_atualizacao)
            page.go_restaurar.connect(self._go_restaurar)
            page.go_log.connect(self._go_log)
            # Esses nomes de sinais devem coincidir com os definidos nas páginas
            try:
                page.go_instalar_firebird.connect(self._go_instalar_firebird)
                page.go_fb_portable.connect(self._go_fb_portable)
            except AttributeError: pass

        elif idx == IDX_UTILITARIOS:
            page.go_log.connect(self._go_log)
            page.go_backup_gbak.connect(self._go_backup_gbak)
            page.go_port_opener.connect(self._go_port_opener)
            page.go_diagnostico.connect(self._go_diagnostico)
            page.go_editar_func.connect(self._go_editar_func)
            page.go_implantar_mobile.connect(self._go_implantar_mobile)
            page.go_shutdown_online.connect(self._go_shutdown_online)
            page.go_verificar_versao_fdb.connect(self._go_verificar_versao_fdb)
            page.go_menu.connect(self._go_menu)

        elif idx == IDX_SCAN:
            page.servidor_selecionado.connect(self._on_servidor_detectado)
            page.cancelado.connect(self._go_menu)

    def _navigate(self, fn):
        """Helper para navegação com guarda de workers ativos."""
        if self._controller.is_worker_running():
            self._show_guard(fn)
        else:
            fn()

    def _show_guard(self, on_confirm):
        """Exibe diálogo de confirmação se houver processos ativos."""
        dlg = WorkerGuardDialog(self)
        dlg.move(
            self.x() + (self.width()  - dlg.width())  // 2,
            self.y() + (self.height() - dlg.height()) // 2,
        )
        dlg.confirmed.connect(on_confirm)
        dlg.show()

    # -- Métodos de Navegação (Wrappers para o NavigationManager) --

    def _go_menu(self):
        self._nav.show_page(IDX_MENU)

    def _go_utilitarios(self):
        self._nav.show_page(IDX_UTILITARIOS)

    def _go_log(self):
        p = self._nav.get_page(IDX_LOG)
        if hasattr(p, "load_log"): p.load_log()
        self._nav.show_page(IDX_LOG)

    def _go_restaurar(self):
        p = self._nav.get_page(IDX_RESTAURAR)
        if hasattr(p, "load_backups"): p.load_backups()
        self._nav.show_page(IDX_RESTAURAR)

    def _go_atualizacao(self):
        self._nav.show_page(IDX_ATUALIZACAO)

    def _go_backup_gbak(self):
        self._nav.show_page(IDX_BACKUP_GBAK)

    def _go_port_opener(self):
        self._nav.show_page(IDX_PORT_OPENER)

    def _go_diagnostico(self):
        self._nav.show_page(IDX_DIAGNOSTICO)

    def _go_editar_func(self):
        self._nav.show_page(IDX_EDITAR_FUNC)

    def _go_implantar_mobile(self):
        self._nav.show_page(IDX_IMPLANTAR_MOBILE)

    def _go_shutdown_online(self):
        self._nav.show_page(IDX_SHUTDOWN_ONLINE)

    def _go_verificar_versao_fdb(self):
        self._nav.show_page(IDX_VERIFICAR_VERSAO_FDB)

    def _go_instalar_firebird(self):
        self._nav.show_page(IDX_INSTALAR_FIREBIRD)

    def _go_fb_portable(self):
        self._nav.show_page(IDX_FB_PORTABLE)

    def _start_atalhos(self):
        self._controller.flow_mode = "atalhos"
        self._nav.show_page(IDX_SCAN)

    def _start_terminal(self):
        self._controller.flow_mode = "terminal"
        self._nav.show_page(IDX_SCAN)

    def _on_servidor_detectado(self, servidor):
        """Orquestra a transição após a varredura de servidores."""
        from core.logger import log
        log.prefs.add_servidor(servidor.ip, servidor.hostname, servidor.path)
        self._sidebar.unlock_modes()
        
        target_idx = IDX_ATALHOS if self._controller.flow_mode == "atalhos" else IDX_TERMINAL
        page = self._nav.get_page(target_idx)
        if hasattr(page, "set_servidor"):
            page.set_servidor(servidor)
        self._nav.show_page(target_idx)

    # -- Eventos de Sistema --

    def closeEvent(self, event):
        if self._close_guard:
            self._controller.stop()
            event.accept()
            return
            
        if self._controller.is_worker_running():
            event.ignore()
            def _confirmar():
                self._close_guard = True
                self._controller.stop_all_workers()
                self.close()
            self._show_guard(_confirmar)
        else:
            self._controller.stop()
            event.accept()
