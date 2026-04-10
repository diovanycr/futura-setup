# =============================================================================
# FUTURA SETUP — UI: Navigation Manager
# =============================================================================

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QObject, pyqtSignal

# Importação das páginas (Lazy Loading será feito dentro do manager)
from ui.page_menu               import PageMenu
from ui.page_scan               import PageScan
from ui.page_atalhos            import PageAtalhos
from ui.page_terminal           import PageTerminal
from ui.page_restaurar          import PageRestaurar
from ui.page_log                import PageLog
from ui.page_atualizacao        import PageAtualizacao
from ui.page_backup_gbak        import PageBackupGbak
from ui.page_port_opener        import PagePortOpener
from ui.page_diagnostico        import PageDiagnostico
from ui.page_editar_funcionario import PageEditarFuncionario
from ui.page_implantar_mobile   import PageImplantarMobile
from ui.page_shutdown_online    import PageShutdownOnline
from ui.page_utilitarios        import PageUtilitarios
from ui.page_instalar_firebird  import PageInstalarFirebird
from ui.page_verificar_versao_fdb import PageVerificarVersaoFdb
from ui.page_fb_portable        import PageFbPortable

# Índices das páginas
IDX_MENU                 = 0
IDX_SCAN                 = 1
IDX_ATALHOS              = 2
IDX_TERMINAL             = 3
IDX_RESTAURAR            = 4
IDX_LOG                  = 5
IDX_ATUALIZACAO          = 6
IDX_BACKUP_GBAK          = 7
IDX_PORT_OPENER          = 8
IDX_DIAGNOSTICO          = 9
IDX_EDITAR_FUNC          = 10
IDX_IMPLANTAR_MOBILE     = 11
IDX_SHUTDOWN_ONLINE      = 12
IDX_UTILITARIOS          = 13
IDX_INSTALAR_FIREBIRD    = 14
IDX_VERIFICAR_VERSAO_FDB = 15
IDX_FB_PORTABLE          = 16

class NavigationManager(QObject):
    """Gerencia a criação lazy e a troca de páginas no StackedWidget."""
    
    page_changed = pyqtSignal(int, QWidget) # (index, page_instance)

    def __init__(self, stack_widget, sidebar, parent=None):
        super().__init__(parent)
        self._stack = stack_widget
        self._sidebar = sidebar
        self._pages_map: dict[int, QWidget] = {}
        
        # O Menu Principal é criado imediatamente para performance
        self._page_menu = PageMenu()
        self._register_page(IDX_MENU, self._page_menu)
        
        # Mapeamento do NavItem da Sidebar para cada página
        self._nav_map = {
            IDX_ATALHOS:              self._sidebar.nav_atalhos,
            IDX_TERMINAL:             self._sidebar.nav_terminal,
            IDX_ATUALIZACAO:          self._sidebar.nav_atualizacao,
            IDX_BACKUP_GBAK:          self._sidebar.nav_utilitarios,
            IDX_PORT_OPENER:          self._sidebar.nav_utilitarios,
            IDX_EDITAR_FUNC:          self._sidebar.nav_utilitarios,
            IDX_IMPLANTAR_MOBILE:     self._sidebar.nav_utilitarios,
            IDX_SHUTDOWN_ONLINE:      self._sidebar.nav_utilitarios,
            IDX_INSTALAR_FIREBIRD:    self._sidebar.nav_menu,
            IDX_VERIFICAR_VERSAO_FDB: self._sidebar.nav_utilitarios,
            IDX_FB_PORTABLE:          self._sidebar.nav_menu,
            IDX_MENU:                 self._sidebar.nav_menu,
            IDX_UTILITARIOS:          self._sidebar.nav_utilitarios,
        }

    def _register_page(self, idx: int, page: QWidget):
        """Adiciona a página ao stack e ao mapa interno."""
        while self._stack.count() <= idx:
            self._stack.addWidget(QWidget()) # Placeholder
        
        old = self._stack.widget(idx)
        self._stack.removeWidget(old)
        if old: old.deleteLater()
        
        self._stack.insertWidget(idx, page)
        self._pages_map[idx] = page

    def get_page(self, idx: int) -> QWidget:
        """Retorna a página (cria se necessário)."""
        if idx in self._pages_map:
            return self._pages_map[idx]
        
        page = self._create_page_instance(idx)
        if page:
            self._register_page(idx, page)
            return page
        return QWidget()

    def _create_page_instance(self, idx: int) -> QWidget | None:
        """Lógica de fábrica para criação das páginas."""
        if idx == IDX_SCAN:
            return PageScan()
        elif idx == IDX_ATALHOS:
            return PageAtalhos()
        elif idx == IDX_TERMINAL:
            return PageTerminal()
        elif idx == IDX_RESTAURAR:
            return PageRestaurar()
        elif idx == IDX_LOG:
            return PageLog()
        elif idx == IDX_ATUALIZACAO:
            return PageAtualizacao()
        elif idx == IDX_BACKUP_GBAK:
            return PageBackupGbak()
        elif idx == IDX_PORT_OPENER:
            return PagePortOpener()
        elif idx == IDX_DIAGNOSTICO:
            return PageDiagnostico()
        elif idx == IDX_EDITAR_FUNC:
            return PageEditarFuncionario()
        elif idx == IDX_IMPLANTAR_MOBILE:
            return PageImplantarMobile()
        elif idx == IDX_SHUTDOWN_ONLINE:
            return PageShutdownOnline()
        elif idx == IDX_UTILITARIOS:
            return PageUtilitarios()
        elif idx == IDX_INSTALAR_FIREBIRD:
            return PageInstalarFirebird()
        elif idx == IDX_VERIFICAR_VERSAO_FDB:
            return PageVerificarVersaoFdb()
        elif idx == IDX_FB_PORTABLE:
            return PageFbPortable()
        return None

    def show_page(self, idx: int):
        """Troca para a página informada, garantindo que ela exista."""
        page = self.get_page(idx)
        self._stack.setCurrentIndex(idx)
        
        # Atualiza a sidebar se houver um item correspondente
        nav_item = self._nav_map.get(idx)
        if nav_item:
            self._sidebar.set_active(nav_item)
        
        self.page_changed.emit(idx, page)

    def active_pages(self) -> list[QWidget]:
        """Retorna lista de páginas já instanciadas."""
        return list(self._pages_map.values())

    def get_nav_item(self, idx: int):
        """Retorna o NavItem da sidebar associado a um índice de página."""
        return self._nav_map.get(idx)

    def get_searchable_entries(self) -> list[dict]:
        """Retorna lista de entradas formatadas para o Global Search."""
        return [
            {"title": "Menu Principal", "idx": IDX_MENU, "tags": "home inicio dashboard"},
            {"title": "Puxar via Rede (Atalhos)", "idx": IDX_ATALHOS, "tags": "rede server servidor atalhos"},
            {"title": "Configurar Novo Terminal", "idx": IDX_TERMINAL, "tags": "copiar arquivos terminal terminal autonomo"},
            {"title": "Atualizar ERP Futura", "idx": IDX_ATUALIZACAO, "tags": "update baixar versao nova erp"},
            {"title": "Instalar Firebird (Instalador Oficial)", "idx": IDX_INSTALAR_FIREBIRD, "tags": "fb3 fb4 download instalar servico"},
            {"title": "Firebird Portable (Gerenciador)", "idx": IDX_FB_PORTABLE, "tags": "portable independente multi versao"},
            {"title": "Backup GBAK (Segurança)", "idx": IDX_BACKUP_GBAK, "tags": "backup gbak segurança dados dump"},
            {"title": "Restaurar Backup (Recuperação)", "idx": IDX_RESTAURAR, "tags": "restore restaurar recuperar dados"},
            {"title": "Liberar Portas (Firewall)", "idx": IDX_PORT_OPENER, "tags": "firewall portas 3050 network rede"},
            {"title": "Diagnóstico de Sistema", "idx": IDX_DIAGNOSTICO, "tags": "check saude erros sistema logs"},
            {"title": "Visualizar Logs do Setup", "idx": IDX_LOG, "tags": "log historico depuracao"},
            {"title": "Shutdown / Online (Firebird)", "idx": IDX_SHUTDOWN_ONLINE, "tags": "gfix fechar conexoes online derrubar"},
            {"title": "Verificar Versão de Banco (.fdb)", "idx": IDX_VERIFICAR_VERSAO_FDB, "tags": "fdb ods versao firebird"},
            {"title": "Editar Funcionário Admin", "idx": IDX_EDITAR_FUNC, "tags": "senha admin config usuario"},
            {"title": "Implantar Futura Mobile", "idx": IDX_IMPLANTAR_MOBILE, "tags": "mobile celular tablet android"},
            {"title": "Utilitários Extras", "idx": IDX_UTILITARIOS, "tags": "ferramentas ferramentas gfix gbak"},
        ]
