# =============================================================================
# FUTURA SETUP — Configurações Centralizadas
# Todas as constantes e URLs em um só lugar para fácil manutenção
# =============================================================================

# ── VERSÃO ────────────────────────────────────────────────────────────────────

APP_VERSION = "4.3.2"

# Súpressão de janelas CMD em subprocessos Windows
CREATE_NO_WINDOW = 0x08000000

# ── URLs DO REPOSITÓRIO ───────────────────────────────────────────────────────

# ATENÇÃO: _URL_BASE_FISICA é o caminho físico no servidor de repositório.
# Se esse caminho mudar, atualize aqui — as URLs abaixo são geradas a partir dele.
_REPO_BASE   = "https://repositorio.futurasistemas.com.br"
_REPO_FISICA = "D:/Backup//repositorio//"

URL_DLLS = (
    f"{_REPO_BASE}/download.php"
    f"?dirfisico={_REPO_FISICA}01%20-%20DLLs%20Sistema/atual/32/DLLx86.zip"
    f"&caminho={_REPO_BASE}/repositorio/01%20-%20DLLs%20Sistema/atual/32/DLLx86.zip"
    f"&filename=DLLx86.zip"
)

URL_ATUALIZADOR = (
    f"{_REPO_BASE}/download.php"
    f"?dirfisico={_REPO_FISICA}00%20-%20Atualizador/Atualizador.exe"
    f"&caminho={_REPO_BASE}/repositorio/00%20-%20Atualizador/Atualizador.exe"
    f"&filename=Atualizador.exe"
)

# Hosts usados para testar conectividade antes de downloads
CONNECTIVITY_HOSTS = [
    "repositorio.futurasistemas.com.br",
    "www.google.com",
    "8.8.8.8",
]

# ── INSTALAÇÃO ────────────────────────────────────────────────────────────────

# EXEs conhecidos do Futura, em ordem de prioridade
EXES_CONHECIDOS = [
    ("PDV.exe",          "Sistema PDV (Frente de Caixa)"),
    ("FuturaServer.exe", "Servidor Futura"),
    ("Cadastro.exe",     "Sistema de Cadastros"),
    ("Retaguarda.exe",   "Sistema Retaguarda"),
    ("Gerencial.exe",    "Sistema Gerencial"),
]

# Número máximo de backups mantidos por pasta
MAX_BACKUPS = 5

# Espaço mínimo em MB antes de emitir aviso
ESPACO_MIN_MB = 500

# Tentativas máximas de download (rede pode estar instável)
MAX_TENTATIVAS_DOWNLOAD = 3

# Tentativas máximas de cópia de arquivo (disco pode estar ocupado)
MAX_TENTATIVAS_COPIA = 3

# ── FIREBIRD ──────────────────────────────────────────────────────────────────

# Versões suportadas e bases de instalação — adicionar novas versões aqui
_FB_BASES    = [r"C:\Program Files", r"C:\Program Files (x86)"]
_FB_VERSOES  = ["Firebird_5_0", "Firebird_4_0", "Firebird_3_0"]

FIREBIRD_CONF_PATHS = [
    rf"{base}\Firebird\{ver}\databases.conf"
    for base in _FB_BASES
    for ver in _FB_VERSOES
]

FIREBIRD_SERVICES = [
    "FirebirdServerDefaultInstance",
    "FirebirdGuardianDefaultInstance",
    "Firebird Server - DefaultInstance",
    "Firebird Guardian - DefaultInstance",
    "FirebirdServerFirebird_4_0",
    "FirebirdGuardianFirebird_4_0",
    "FirebirdServerFirebird_5_0",
    "FirebirdGuardianFirebird_5_0",
]

# ── FIREBIRD PORTABLE (MENU 05) ───────────────────────────────────────────────

FB_PORTABLE_CONFIGS = {
    "3": {
        "dir":          r"C:\FuturaFirebird\FB3",
        "zip_url":      (
            "https://github.com/FirebirdSQL/firebird/releases/download/"
            "v3.0.13/Firebird-3.0.13.33818-0-x64.zip"
        ),
        "zip_size":     17 * 1024 * 1024,
        "porta":        3050,
        "label":        "Firebird 3 Portable",
        "security_db":  "security3.fdb",
        "servicos_win_oficiais": [
            "FirebirdServerDefaultInstance",
            "FirebirdGuardianDefaultInstance",
            "FirebirdServer",
            "Firebird",
        ],
        "servico_nome": "FuturaFirebirdFB3",
    },
    "4": {
        "dir":          r"C:\FuturaFirebird\FB4",
        "zip_url":      (
            "https://github.com/FirebirdSQL/firebird/releases/download/"
            "v4.0.6/Firebird-4.0.6.3221-0-x64.zip"
        ),
        "zip_size":     23 * 1024 * 1024,
        "porta":        3050,
        "label":        "Firebird 4 Portable",
        "security_db":  "security4.fdb",
        "servicos_win_oficiais": [],
        "servico_nome": "FuturaFirebirdFB4",
    },
}

FB3_INSTALLER_URL = (
    "https://github.com/FirebirdSQL/firebird/releases/download/"
    "v3.0.13/Firebird-3.0.13.33818-0-x64.exe"
)

FB4_REPO_ARQUIVOS = {
    "firebird.conf": (
        f"{_REPO_BASE}/download.php"
        f"?dirfisico={_REPO_FISICA}30%20-%20Firebird%204.0/Conf/firebird.conf"
        f"&caminho={_REPO_BASE}/repositorio/30%20-%20Firebird%204.0/Conf/firebird.conf"
        f"&filename=firebird.conf"
    ),
    "databases.conf": (
        f"{_REPO_BASE}/download.php"
        f"?dirfisico={_REPO_FISICA}30%20-%20Firebird%204.0/Conf/databases.conf"
        f"&caminho={_REPO_BASE}/repositorio/30%20-%20Firebird%204.0/Conf/databases.conf"
        f"&filename=databases.conf"
    ),
    "Usuarios.sql": (
        f"{_REPO_BASE}/download.php"
        f"?dirfisico={_REPO_FISICA}30%20-%20Firebird%204.0/Conf/Usuarios.sql"
        f"&caminho={_REPO_BASE}/repositorio/30%20-%20Firebird%204.0/Conf/Usuarios.sql"
        f"&filename=Usuarios.sql"
    ),
}

# ── REDE ──────────────────────────────────────────────────────────────────────

# Share que identifica um servidor Futura válido
FUTURA_SHARE_NAME = "Futura"

# Arquivos que confirmam que é um servidor Futura legítimo
FUTURA_MARKER_FILES = ["Futura.ini", "FuturaServer.exe"]

# ── PASTAS PADRÃO ─────────────────────────────────────────────────────────────

PASTAS_INSTALACAO_PADRAO = [
    "C:\\FUTURA",
    "C:\\FuturaTerminal",
]

# Subpasta de backups dentro da instalação
BACKUP_SUBDIR = "Backup_Atualizacao"
