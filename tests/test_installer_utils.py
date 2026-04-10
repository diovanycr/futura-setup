# =============================================================================
# FUTURA SETUP — Tests: Installer Utilities
# =============================================================================

import pytest
from core.installer import formatar_tamanho

def test_formatar_tamanho():
    """Valida a formatação de bytes para strings legíveis."""
    assert formatar_tamanho(512 * 1024) == "512 KB" # 512 KB
    # De acordo com o código: mb = bytes_ / (1024 * 1024)
    # Se mb >= 1: return f"{mb:.1f} MB" 
    # else: return f"{bytes_ / 1024:.0f} KB"
    
    assert formatar_tamanho(1024 * 512) == "512 KB"
    assert formatar_tamanho(1024 * 1024) == "1.0 MB"
    assert formatar_tamanho(1024 * 1024 * 1.5) == "1.5 MB"
    assert formatar_tamanho(1024 * 1024 * 1024) == "1024.0 MB"
