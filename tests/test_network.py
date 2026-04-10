# =============================================================================
# FUTURA SETUP — Tests: Network Discovery
# =============================================================================

import pytest
from core.network import Servidor, MetodoScan

def test_servidor_dataclass():
    """Valida se as propriedades do Servidor funcionam conforme esperado."""
    srv = Servidor(ip="192.168.1.10", hostname="SERVER01", version="4.3.0")
    assert srv.ip == "192.168.1.10"
    assert srv.hostname == "SERVER01"
    assert srv.display == "SERVER01  (IP: 192.168.1.10)"
    assert srv.path == "\\\\SERVER01\\Futura"
    assert srv.path_ip == "\\\\192.168.1.10\\Futura"
    assert srv.version_display == "4.3.0"

def test_servidor_no_hostname():
    """Valida fallback quando hostname não é fornecido."""
    srv = Servidor(ip="10.0.0.5")
    assert srv.hostname == "10.0.0.5"
    assert srv.display == "10.0.0.5"
    assert srv.path == "\\\\10.0.0.5\\Futura"

def test_metodo_scan_namedtuple():
    """Valida a estrutura do MetodoScan."""
    m = MetodoScan("test", "Test Name", "Test Desc")
    assert m.key == "test"
    assert m.nome == "Test Name"
    assert m.descricao == "Test Desc"
