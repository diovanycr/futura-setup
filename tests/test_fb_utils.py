import unittest
import os
import sys
from pathlib import Path

# Adiciona o diretório raiz ao sys.path para permitir importações do core
sys.path.append(str(Path(__file__).parent.parent))

from core.fb_utils import (
    fb_portable_instalado,
    diagnosticar_instalacao,
    encontrar_servidor
)

class TestFbUtils(unittest.TestCase):

    def test_fb_portable_instalado_missing_dir(self):
        # Testa uma versão que não existe na config (ou dir inexistente)
        self.assertFalse(fb_portable_instalado("9.9"))

    def test_diagnosticar_instalacao_invalid(self):
        res = diagnosticar_instalacao("9.9")
        self.assertIsInstance(res, dict)
        self.assertFalse(res["ok"])
        self.assertEqual(len(res["arquivos"]), 0)

    def test_encontrar_servidor_none(self):
        self.assertIsNone(encontrar_servidor("9.9"))

if __name__ == '__main__':
    unittest.main()
