"""
Futura Setup — ponto de entrada alternativo.
Use este arquivo para iniciar o app diretamente:
    python launcher.py
Para projetos distribuídos como pacote, prefira:
    python -m futura_setup
"""
import sys
import os
import ctypes

# ── DEVE ser a PRIMEIRA coisa executada — antes de qualquer import Qt ────────
# Sem isso, a taskbar mostra o ícone do python.exe em vez do futura.ico
if sys.platform == "win32":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "FuturaSistemas.FuturaSetup.1.0"
        )
    except Exception:
        pass

# Garante que a raiz do projeto esteja no path ao rodar diretamente
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from main import main

if __name__ == "__main__":
    main()
