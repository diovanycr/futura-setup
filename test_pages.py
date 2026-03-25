import sys
from PyQt6.QtWidgets import QApplication
from ui.page_menu import PageMenu
from ui.page_scan import PageScan
from ui.page_atalhos import PageAtalhos
from ui.page_terminal import PageTerminal
from ui.page_restaurar import PageRestaurar
from ui.page_atualizacao import PageAtualizacao
from ui.page_instalar_firebird import PageInstalarFirebird
from ui.page_fb_portable import PageFbPortable
from ui.page_log import PageLog
from ui.page_backup_gbak import PageBackupGbak
from ui.page_utilitarios import PageUtilitarios
from ui.page_port_opener import PagePortOpener
from ui.page_diagnostico import PageDiagnostico
from ui.page_verificar_versao_fdb import PageVerificarVersaoFdb

app = QApplication(sys.argv)
pages = [
    PageMenu, PageScan, PageAtalhos, PageTerminal,
    PageRestaurar, PageAtualizacao, PageInstalarFirebird,
    PageFbPortable, PageLog, PageBackupGbak, PageUtilitarios,
    PagePortOpener, PageDiagnostico, PageVerificarVersaoFdb
]
for p in pages:
    try:
        instance = p()
        print(f"{p.__name__}: OK")
    except Exception as e:
        import traceback
        print(f"ERROR in {p.__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)
print("ALL PAGES OK!")
