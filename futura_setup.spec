# =============================================================================
# futura_setup.spec — PyInstaller spec file para FuturaSetup
# =============================================================================

import sys
import os
from datetime import date

# Lê a versão direto do config.py (usada para metadados futuros)
sys.path.insert(0, os.path.dirname(os.path.abspath(SPEC)))
import config as _cfg
_VERSION  = _cfg.APP_VERSION

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('futura.ico', '.'),
        ('config.py', '.'),
        ('ui', 'ui'),
        ('core', 'core'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.sip',
        'psutil',
        'win32api',
        'win32con',
        'win32service',
        'win32serviceutil',
        'pywintypes',
        'ctypes',
        'ctypes.wintypes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FuturaSetup',       # O bat renomeia para FuturaSetup_vX.X.X_DATE_HHMM.exe
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # Sem janela de console (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='futura.ico',       # Ícone do executável
    uac_uiaccess=False,
)
