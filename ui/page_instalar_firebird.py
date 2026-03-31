# =============================================================================
# FUTURA SETUP — Página: Instalar Firebird
# Layout baseado no padrão da Instalação Automática do Firebird Portable
# Salvar em: ui/page_instalar_firebird.py
# =============================================================================

from __future__ import annotations

import os

from PyQt6.QtCore    import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui     import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QButtonGroup,
    QRadioButton, QFrame, QLabel, QStackedWidget,
    QTabWidget, QListWidget, QListWidgetItem,
    QAbstractItemView, QFileDialog, QProgressBar,
    QPlainTextEdit, QPushButton, QGridLayout,
    QApplication,
)

from ui.theme         import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets       import (
    PageHeader, SectionHeader, AlertBox, LogConsole, ProgressBlock,
    make_primary_btn, make_secondary_btn, btn_row, spacer, h_line, label,
)
from core.firebird_installer import (
    InstaladorFirebirdWorker,
    check_installed_firebird,
    detect_arch,
    is_admin,
    elevar_como_admin,
    FB_URLS,
    FB_LABEL,
    fb_install_path,        # caminho real do Firebird instalado
)
from core.fb_portable import (
    varrer_fdb,
    fb_portable_instalado,
    FB_CONFIGS,
)

# Cores por versão — igual ao Portable
_COR = {
    "3": COLORS.get("accent2", "#2ecc71"),
    "4": COLORS.get("accent",  "#0078d4"),
}


# =============================================================================
# Helpers de serviço do Firebird INSTALADO (Program Files)
# Diferente do portable: usa fb_install_path() para localizar a pasta
# e gerencia o serviço "FirebirdServerDefaultInstance" ou "Firebird_<ver>"
# =============================================================================

# Cache de localização das pastas — evita varrer o disco a cada atualização
# { "3": ("C:\\...", timestamp), "4": ("", timestamp) }
_cache_pasta: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 60.0   # segundos — revalida no máximo 1x por minuto


def _encontrar_pasta_firebird(versao: str) -> str:
    """
    Localiza a pasta Firebird_3_0 ou Firebird_4_0 no disco.

    Usa cache com TTL de 60s para nao varrer o disco a cada chamada.
    Ordem de busca:
      1. Cache ainda valido  - retorna imediatamente
      2. Caminhos padrao     - retorna na primeira combinacao (< 1ms)
      3. Varredura C:        - so executada se os caminhos padrao falharem
    """
    import time

    # 1. Cache válido
    cached = _cache_pasta.get(versao)
    if cached is not None:
        pasta_c, ts = cached
        if time.monotonic() - ts < _CACHE_TTL:
            return pasta_c

    alvo = f"Firebird_{versao}_0"

    # 2. Caminhos padrão — verificação instantânea (< 1ms)
    candidatos_diretos = [
        f"C:\\Program Files\\Firebird\\{alvo}",
        f"C:\\Program Files (x86)\\Firebird\\{alvo}",
        f"C:\\Firebird\\{alvo}",
        f"C:\\{alvo}",
        f"C:\\Program Files\\{alvo}",
        f"C:\\Program Files (x86)\\{alvo}",
    ]
    for c in candidatos_diretos:
        if os.path.isdir(c):
            _cache_pasta[versao] = (c, time.monotonic())
            return c

    # 3. Varredura limitada — só chega aqui se instalação está em local incomum
    raiz = "C:\\"
    resultado = ""
    try:
        for nivel1 in os.listdir(raiz):
            p1 = os.path.join(raiz, nivel1)
            if not os.path.isdir(p1):
                continue
            if nivel1.lower() == alvo.lower():
                resultado = p1
                break
            try:
                for nivel2 in os.listdir(p1):
                    p2 = os.path.join(p1, nivel2)
                    if not os.path.isdir(p2):
                        continue
                    if nivel2.lower() == alvo.lower():
                        resultado = p2
                        break
                    try:
                        for nivel3 in os.listdir(p2):
                            p3 = os.path.join(p2, nivel3)
                            if os.path.isdir(p3) and nivel3.lower() == alvo.lower():
                                resultado = p3
                                break
                        if resultado:
                            break
                    except PermissionError:
                        pass
                if resultado:
                    break
            except PermissionError:
                pass
        if resultado:
            pass
    except Exception:
        pass

    _cache_pasta[versao] = (resultado, time.monotonic())
    return resultado


def _invalidar_cache_pasta(versao: str | None = None):
    """Invalida o cache para forçar nova detecção (chamar após instalar/remover)."""
    if versao:
        _cache_pasta.pop(versao, None)
    else:
        _cache_pasta.clear()


def _nome_servico_instalado(versao: str) -> str:
    """
    Descobre o nome do serviço Windows do Firebird instalado consultando
    o registro de serviços (sc qc) e cruzando com o caminho da pasta
    encontrada por _encontrar_pasta_firebird().

    Candidatos testados em ordem para cada versão.
    """
    import subprocess

    candidatos = {
        "3": [
            "FirebirdServerDefaultInstance",
            "FirebirdGuardianDefaultInstance",
            "Firebird_3",
            "FirebirdSS",
        ],
        "4": [
            "FirebirdServerDefaultInstance",
            "Firebird_4",
            "FirebirdSS4",
        ],
    }

    pasta = _encontrar_pasta_firebird(versao)

    # Prioridade: serviço cujo binário aponta para a pasta desta versão
    if pasta:
        pasta_lower = pasta.lower()
        for nome in candidatos.get(versao, []):
            try:
                r = subprocess.run(
                    ["sc", "qc", nome],
                    capture_output=True, text=True, timeout=5,
                )
                if r.returncode == 0 and pasta_lower in r.stdout.lower():
                    return nome
            except Exception:
                pass

    # Fallback: primeiro serviço que existir
    for nome in candidatos.get(versao, ["FirebirdServerDefaultInstance"]):
        try:
            r = subprocess.run(
                ["sc", "query", nome],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                return nome
        except Exception:
            pass

    return candidatos.get(versao, ["FirebirdServerDefaultInstance"])[0]


def _servico_instalado_rodando(versao: str) -> bool:
    """Verifica se o serviço do Firebird instalado está rodando."""
    import subprocess
    nome = _nome_servico_instalado(versao)
    try:
        r = subprocess.run(
            ["sc", "query", nome],
            capture_output=True, text=True, timeout=5,
        )
        return "RUNNING" in r.stdout
    except Exception:
        return False


def _servico_instalado_existe(versao: str) -> bool:
    """Verifica se o serviço do Firebird instalado está registrado."""
    import subprocess
    nome = _nome_servico_instalado(versao)
    try:
        r = subprocess.run(
            ["sc", "query", nome],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def _iniciar_servico_instalado(versao: str, log_fn=None) -> dict:
    """Inicia o serviço do Firebird instalado."""
    import subprocess
    def log(m):
        if log_fn:
            log_fn(m)

    nome = _nome_servico_instalado(versao)
    log(f"Iniciando serviço {nome} (Firebird {versao})...")
    try:
        r = subprocess.run(
            ["net", "start", nome],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0 or "já foi iniciado" in r.stdout.lower():
            log(f"Serviço {nome} iniciado com sucesso.")
            return {"ok": True, "erro": ""}
        else:
            msg = r.stderr.strip() or r.stdout.strip() or "Erro desconhecido"
            log(f"Erro ao iniciar serviço: {msg}")
            return {"ok": False, "erro": msg}
    except Exception as e:
        log(f"Exceção ao iniciar serviço: {e}")
        return {"ok": False, "erro": str(e)}


def _parar_servico_instalado(versao: str, log_fn=None) -> dict:
    """Para o serviço do Firebird instalado."""
    import subprocess
    def log(m):
        if log_fn:
            log_fn(m)

    nome = _nome_servico_instalado(versao)
    log(f"Parando serviço {nome} (Firebird {versao})...")
    try:
        r = subprocess.run(
            ["net", "stop", nome],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0 or "não foi iniciado" in r.stdout.lower():
            log(f"Serviço {nome} parado com sucesso.")
            return {"ok": True, "erro": ""}
        else:
            msg = r.stderr.strip() or r.stdout.strip() or "Erro desconhecido"
            log(f"Erro ao parar serviço: {msg}")
            return {"ok": False, "erro": msg}
    except Exception as e:
        log(f"Exceção ao parar serviço: {e}")
        return {"ok": False, "erro": str(e)}


def _reiniciar_servico_instalado(versao: str, log_fn=None) -> dict:
    """Reinicia o serviço do Firebird instalado."""
    r = _parar_servico_instalado(versao, log_fn)
    if not r["ok"]:
        return r
    import time
    time.sleep(1)
    return _iniciar_servico_instalado(versao, log_fn)


def _status_instalado(versao: str) -> dict:
    """
    Retorna dict com status do Firebird instalado para a versao informada.
    Usa _encontrar_pasta_firebird() para localizar Firebird_3_0 ou Firebird_4_0
    em qualquer lugar do C:, independente do fb_install_path().
    """
    pasta     = _encontrar_pasta_firebird(versao)
    instalado = bool(pasta)
    rodando   = _servico_instalado_rodando(versao) if instalado else False
    svc_reg   = _servico_instalado_existe(versao)  if instalado else False

    return {
        "instalado":   instalado,
        "rodando":     rodando,
        "servico_reg": svc_reg,
        "servico_rod": rodando,
        "pasta":       pasta,
    }


# =============================================================================
# Atualiza databases.conf do Firebird INSTALADO (Program Files)
# Diferente do portable: usa fb_install_path() para achar a pasta correta
# ex: C:\Program Files\Firebird\Firebird_3_0\databases.conf
# =============================================================================

def _atualizar_databases_conf_instalado(
    versao: str,
    caminho_dados: str,
    log_fn=None,
) -> dict:
    """
    Atualiza o databases.conf do Firebird instalado em Program Files.
    Localiza a pasta via _encontrar_pasta_firebird().

    Formato gerado:
        # Live Databases:
        #
        Dados = C:/caminho/dados.fdb
        Cep   = C:/caminho/cep.fdb
    """
    def log(m):
        if log_fn:
            log_fn(m)

    # Localiza a pasta de instalação via varredura real no C:\
    pasta = _encontrar_pasta_firebird(versao)

    if not pasta:
        msg = (
            f"Pasta do Firebird {versao} nao encontrada.\n"
            f"Verifique se o Firebird {versao} esta instalado corretamente."
        )
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg, "conf_path": ""}

    conf_path   = os.path.join(pasta, "databases.conf")
    pasta_dados = os.path.dirname(caminho_dados)
    caminho_cep = os.path.join(pasta_dados, "cep.fdb")

    log(f"Pasta Firebird {versao}: {pasta}")
    log(f"databases.conf: {conf_path}")
    log(f"Dados : {caminho_dados}")
    log(f"Cep   : {caminho_cep}")

    bloco_live = (
        "# Live Databases:\n"
        "#\n"
        f"Dados = {caminho_dados}\n"
        f"Cep   = {caminho_cep}\n"
    )

    try:
        if os.path.isfile(conf_path):
            with open(conf_path, "r", encoding="utf-8", errors="replace") as f:
                conteudo = f.read()
            log("databases.conf existente encontrado.")
        else:
            conteudo = ""
            log("databases.conf nao encontrado — sera criado.")

        marcador = "# Live Databases:"

        if marcador in conteudo:
            idx            = conteudo.index(marcador)
            cabecalho      = conteudo[:idx]
            conteudo_final = cabecalho + bloco_live
        else:
            # Remove entradas Dados/Cep antigas se existirem
            linhas_limpas = []
            for linha in conteudo.splitlines():
                l = linha.strip().lower()
                if l.startswith("dados =") or l.startswith("cep =") or l.startswith("cep   ="):
                    continue
                linhas_limpas.append(linha)
            conteudo_limpo = "\n".join(linhas_limpas)
            sep = "\n" if conteudo_limpo and not conteudo_limpo.endswith("\n") else ""
            conteudo_final = conteudo_limpo + sep + "\n" + bloco_live

        with open(conf_path, "w", encoding="utf-8") as f:
            f.write(conteudo_final)

        log(f"databases.conf atualizado com sucesso em: {conf_path}")
        return {"ok": True, "erro": "", "conf_path": conf_path}

    except PermissionError:
        msg = (
            f"Sem permissao para gravar em {conf_path}.\n"
            "Execute o Futura Setup como Administrador."
        )
        log(f"ERRO: {msg}")
        return {"ok": False, "erro": msg, "conf_path": conf_path}
    except Exception as e:
        log(f"Erro ao atualizar databases.conf: {e}")
        return {"ok": False, "erro": str(e), "conf_path": conf_path}


# =============================================================================
# Workers
# =============================================================================

class _VarreduraWorker(QThread):
    log       = pyqtSignal(str)
    concluido = pyqtSignal(list)

    def run(self):
        self.concluido.emit(varrer_fdb(log_fn=self.log.emit))


class _DatabasesConfWorker(QThread):
    log       = pyqtSignal(str)
    concluido = pyqtSignal(dict)

    def __init__(self, versao: str, caminho_dados: str, parent=None):
        super().__init__(parent)
        self.versao        = versao
        self.caminho_dados = caminho_dados

    def run(self):
        # Usa _atualizar_databases_conf_instalado — busca em Program Files,
        # nao em FB_CONFIGS["dir"] que e a pasta do portable
        self.concluido.emit(
            _atualizar_databases_conf_instalado(self.versao, self.caminho_dados, self.log.emit)
        )


class _ServicoWorker(QThread):
    """Worker para iniciar / parar / reiniciar o serviço do Firebird instalado."""
    log       = pyqtSignal(str)
    concluido = pyqtSignal(dict)

    def __init__(self, versao: str, acao: str, parent=None):
        super().__init__(parent)
        self.versao = versao
        self.acao   = acao   # 'iniciar' | 'parar' | 'reiniciar'

    def run(self):
        if self.acao == "iniciar":
            r = _iniciar_servico_instalado(self.versao, self.log.emit)
        elif self.acao == "parar":
            r = _parar_servico_instalado(self.versao, self.log.emit)
        else:
            r = _reiniciar_servico_instalado(self.versao, self.log.emit)
        r["versao"] = self.versao
        r["acao"]   = self.acao
        self.concluido.emit(r)


# =============================================================================
# Banner Admin — identico ao _BannerAdmin do Portable
# =============================================================================

class _BannerAdmin(QFrame):
    reiniciar_solicitado = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("banner_admin_inst")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        ico = QLabel("[!]")
        ico.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        ico.setStyleSheet("color:#e67e22; background:transparent; border:none;")
        ico.setFixedWidth(24)

        lbl = QLabel("Permissao de administrador necessaria para instalar o Firebird.")
        lbl.setFont(QFont(FONT_SANS, 9))
        lbl.setStyleSheet(
            f"color:{COLORS.get('text','#fff')}; background:transparent; border:none;"
        )

        btn = make_primary_btn("Reiniciar como Admin", 160)
        btn.setFixedHeight(30)
        btn.clicked.connect(self.reiniciar_solicitado.emit)

        lay.addWidget(ico, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(lbl, 1, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.setStyleSheet("""
            QFrame#banner_admin_inst {
                background: rgba(230,126,34,0.12);
                border: 1.2px solid #e67e22;
                border-radius: 6px;
            }
        """)


# =============================================================================
# Card de versao — identico ao _AutoInstallCard do Portable
# =============================================================================

class _VersionCard(QFrame):
    instalar_solicitado = pyqtSignal(str)   # (versao)

    def __init__(self, versao: str, arch: str, parent=None):
        super().__init__(parent)
        self._versao = versao
        self._arch   = arch
        self.setObjectName(f"vcard_inst_{versao}")
        self._build_ui()
        self._upd_style()
        theme_manager.theme_changed.connect(lambda _: self._upd_style())

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        # Header
        header = QHBoxLayout()
        titulo = QLabel(f"Firebird {self._versao}")
        titulo.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        titulo.setStyleSheet(
            f"color:{_COR[self._versao]}; background:transparent; border:none;"
        )

        self._lbl_badge = QLabel("NAO INSTALADO")
        self._lbl_badge.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self._lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_badge.setMinimumWidth(120)
        self._lbl_badge.setContentsMargins(6, 2, 6, 2)
        self._set_badge(False)

        header.addWidget(titulo, 1)
        header.addWidget(self._lbl_badge)
        lay.addLayout(header)

        # Separador
        hl = QFrame()
        hl.setFrameShape(QFrame.Shape.HLine)
        hl.setStyleSheet(
            f"background:{COLORS.get('border','#444')}; max-height:1px; border:none;"
        )
        lay.addWidget(hl)

        # Versao e arquitetura
        self._lbl_ver = QLabel(
            f"{FB_LABEL.get(self._versao, '')}   |   {self._arch}"
        )
        self._lbl_ver.setFont(QFont(FONT_MONO, 9))
        self._lbl_ver.setStyleSheet(
            f"color:{COLORS.get('text_mid','#aaa')}; background:transparent; border:none;"
        )
        lay.addWidget(self._lbl_ver)

        # Descricao
        if self._versao == "3":
            desc_txt = (
                "Compativel com sistemas legados.\n"
                "Estavel e amplamente utilizado."
            )
        else:
            desc_txt = (
                "Versao mais recente com melhor desempenho.\n"
                "Recomendado para novas instalacoes."
            )
        desc = QLabel(desc_txt)
        desc.setFont(QFont(FONT_SANS, 9))
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color:{COLORS.get('text_mid','#aaa')}; background:transparent; border:none;"
        )
        lay.addWidget(desc)

        # URL de download
        url = FB_URLS.get(self._versao, {}).get(self._arch, "")
        self._lbl_url = QLabel(url)
        self._lbl_url.setFont(QFont(FONT_MONO, 7))
        self._lbl_url.setWordWrap(True)
        self._lbl_url.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._lbl_url.setStyleSheet(
            f"color:{COLORS.get('text_dim','#555')}; background:transparent; border:none;"
        )
        lay.addWidget(self._lbl_url)

        lay.addStretch()

        # Status (oculto por padrao)
        self._status_box = QWidget()
        self._status_box.setVisible(False)
        st_lay = QVBoxLayout(self._status_box)
        st_lay.setContentsMargins(0, 4, 0, 4)
        st_lay.setSpacing(4)
        self._lbl_status = QLabel("Preparando...")
        self._lbl_status.setFont(QFont(FONT_SANS, 8))
        self._lbl_status.setStyleSheet(
            f"color:{COLORS.get('text_dim','#888')}; background:transparent; border:none;"
        )
        self._pbar = QProgressBar()
        self._pbar.setFixedHeight(4)
        self._pbar.setTextVisible(False)
        self._pbar.setRange(0, 100)
        st_lay.addWidget(self._lbl_status)
        st_lay.addWidget(self._pbar)
        lay.addWidget(self._status_box)

        # Botao
        self._btn = make_primary_btn("BAIXAR E INSTALAR", 220)
        self._btn.setFixedHeight(38)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(
            lambda: self.instalar_solicitado.emit(self._versao)
        )
        lay.addWidget(self._btn, 0, Qt.AlignmentFlag.AlignCenter)

    # API publica

    def set_loading(self, active: bool, msg: str = "", progress: int = 0):
        self._status_box.setVisible(active)
        self._btn.setEnabled(not active)
        if active:
            if msg:
                self._lbl_status.setText(msg)
            self._pbar.setValue(progress)

    def set_installed(self, installed: bool):
        self._set_badge(installed)
        self._btn.setText("REINSTALAR" if installed else "BAIXAR E INSTALAR")

    def _set_badge(self, instalado: bool):
        brd = COLORS.get("border", "#444")
        if instalado:
            self._lbl_badge.setText("INSTALADO")
            self._lbl_badge.setStyleSheet(f"""
                QLabel {{
                    background:{COLORS.get('accent2','#2ecc71')}; color:#fff;
                    border-radius:4px; padding:2px 8px; font-weight:bold;
                }}
            """)
        else:
            self._lbl_badge.setText("NAO INSTALADO")
            self._lbl_badge.setStyleSheet(f"""
                QLabel {{
                    background:{COLORS.get('surface','#2a2a2a')};
                    color:{COLORS.get('text_dim','#888')};
                    border:1px solid {brd};
                    border-radius:4px; padding:2px 8px; font-weight:bold;
                }}
            """)

    # Estilo

    def _upd_style(self, _=""):
        acc = _COR[self._versao]
        bg  = COLORS.get("surface", "#1e1e1e")
        brd = COLORS.get("border",  "#444")
        self.setStyleSheet(f"""
            QFrame#vcard_inst_{self._versao} {{
                background:{bg};
                border:1.5px solid {brd};
                border-radius:12px;
            }}
            QFrame#vcard_inst_{self._versao}:hover {{
                border:1.5px solid {acc};
                background:{COLORS.get('surface2','#2a2a2a')};
            }}
        """)
        self._pbar.setStyleSheet(f"""
            QProgressBar {{ background:{brd}; border:none; border-radius:2px; }}
            QProgressBar::chunk {{ background:{acc}; border-radius:2px; }}
        """)


# =============================================================================
# Card de Banco de Dados — identico ao do Portable
# =============================================================================

class _DatabasesConfCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("db_conf_card_inst")
        self._arquivos: list[str] = []
        self._worker: QThread | None = None
        self._build_ui()
        theme_manager.ui_theme_changed.connect(self._upd_style)
        theme_manager.theme_changed.connect(lambda _: self._upd_style())
        self._upd_style()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        header_inner = QHBoxLayout()
        icon = QLabel("[DB]")
        icon.setFont(QFont(FONT_SANS, 10, QFont.Weight.Bold))
        icon.setStyleSheet(
            f"color:{COLORS.get('accent','#0078d4')}; background:transparent; border:none;"
        )
        titulo_v = QVBoxLayout()
        titulo_lbl = QLabel("Configurar bases de dados")
        titulo_lbl.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
        subtitulo_lbl = QLabel("Selecione o arquivo .fdb para configurar o databases.conf")
        subtitulo_lbl.setFont(QFont(FONT_SANS, 9))
        titulo_v.addWidget(titulo_lbl)
        titulo_v.addWidget(subtitulo_lbl)
        info_lbl = QLabel("[i]")
        info_lbl.setToolTip(
            "O sistema buscara por arquivos .fdb. Ao selecionar o arquivo principal (Dados), "
            "o arquivo de CEP sera vinculado automaticamente se estiver na mesma pasta."
        )
        header_inner.addWidget(icon)
        header_inner.addLayout(titulo_v, 1)
        header_inner.addWidget(info_lbl)
        lay.addLayout(header_inner)

        self._ctrl_frame = QFrame()
        self._ctrl_frame.setObjectName("db_ctrl_box_inst")
        ctrl_lay = QHBoxLayout(self._ctrl_frame)
        ctrl_lay.setContentsMargins(12, 8, 12, 8)
        lbl_v = QLabel("Versao Firebird:")
        lbl_v.setFont(QFont(FONT_SANS, 9, QFont.Weight.Bold))
        self._radio_fb3 = QRadioButton("FB 3.0")
        self._radio_fb4 = QRadioButton("FB 4.0")
        self._radio_fb4.setChecked(True)
        v_group = QHBoxLayout()
        v_group.setSpacing(12)
        v_group.addWidget(self._radio_fb3)
        v_group.addWidget(self._radio_fb4)
        self._btn_varrer = make_primary_btn("VARRER HD", 130)
        self._btn_varrer.setFixedHeight(32)
        self._btn_varrer.clicked.connect(self._on_varrer)
        self._btn_explorer = make_secondary_btn("PROCURAR", 120)
        self._btn_explorer.setFixedHeight(32)
        self._btn_explorer.clicked.connect(self._on_selecionar_explorer)
        ctrl_lay.addWidget(lbl_v)
        ctrl_lay.addLayout(v_group)
        ctrl_lay.addSpacing(16)
        ctrl_lay.addWidget(self._btn_varrer)
        ctrl_lay.addWidget(self._btn_explorer)
        ctrl_lay.addStretch()
        lay.addWidget(self._ctrl_frame)

        self._lbl_count = QLabel("Aguardando inicio da varredura...")
        self._lbl_count.setFont(QFont(FONT_MONO, 8))
        lay.addWidget(self._lbl_count)

        self._lista = QListWidget()
        self._lista.setMinimumHeight(180)
        self._lista.setFont(QFont(FONT_MONO, 9))
        self._lista.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._lista.itemSelectionChanged.connect(self._on_selecao_changed)
        lay.addWidget(self._lista)

        self._preview_frame = QFrame()
        self._preview_frame.setObjectName("db_preview_inst")
        prev_lay = QGridLayout(self._preview_frame)
        prev_lay.setContentsMargins(10, 6, 10, 6)
        prev_lay.setSpacing(4)
        self._lbl_dados_tag = QLabel("Dados:")
        self._lbl_dados_tag.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self._lbl_dados = QLabel("—")
        self._lbl_dados.setWordWrap(True)
        self._lbl_dados.setFont(QFont(FONT_MONO, 8))
        self._lbl_cep_tag = QLabel("CEP:")
        self._lbl_cep_tag.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self._lbl_cep = QLabel("—")
        self._lbl_cep.setWordWrap(True)
        self._lbl_cep.setFont(QFont(FONT_MONO, 8))
        prev_lay.addWidget(self._lbl_dados_tag, 0, 0)
        prev_lay.addWidget(self._lbl_dados,     0, 1)
        prev_lay.addWidget(self._lbl_cep_tag,   1, 0)
        prev_lay.addWidget(self._lbl_cep,       1, 1)
        lay.addWidget(self._preview_frame)

        self._btn_aplicar = make_primary_btn("CONFIGURAR AGORA", 200)
        self._btn_aplicar.setFixedHeight(38)
        self._btn_aplicar.setEnabled(False)
        self._btn_aplicar.clicked.connect(self._on_aplicar)
        self._lbl_resultado = QLabel("")
        self._lbl_resultado.setFont(QFont(FONT_SANS, 9, QFont.Weight.Bold))
        self._lbl_resultado.setWordWrap(True)
        bt_row = QHBoxLayout()
        bt_row.addWidget(self._btn_aplicar)
        bt_row.addSpacing(12)
        bt_row.addWidget(self._lbl_resultado, 1)
        lay.addLayout(bt_row)
        lay.addStretch()

    def set_version(self, versao: str):
        if versao == "3":
            self._radio_fb3.setChecked(True)
        elif versao == "4":
            self._radio_fb4.setChecked(True)

    def _on_varrer(self):
        self._lista.clear()
        self._arquivos = []
        self._lbl_count.setText("Varrendo... aguarde.")
        self._btn_varrer.setEnabled(False)
        self._btn_explorer.setEnabled(False)
        self._btn_aplicar.setEnabled(False)
        self._lbl_dados.setText("—")
        self._lbl_cep.setText("—")
        self._lbl_resultado.setText("")
        worker = _VarreduraWorker()
        worker.log.connect(lambda m: self._lbl_count.setText(m))
        worker.concluido.connect(self._on_varredura_concluida)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _on_varredura_concluida(self, arquivos: list[str]):
        self._arquivos = arquivos
        self._btn_varrer.setEnabled(True)
        self._btn_explorer.setEnabled(True)
        self._lista.clear()
        if not arquivos:
            self._lbl_count.setText("Nenhum arquivo .fdb encontrado.")
            return
        self._lbl_count.setText(
            f"{len(arquivos)} arquivo(s) .fdb encontrado(s) — selecione o Dados:"
        )
        for caminho in arquivos:
            item = QListWidgetItem(caminho)
            item.setToolTip(caminho)
            self._lista.addItem(item)

    def _on_selecionar_explorer(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo Dados", "C:\\",
            "Firebird Database (*.fdb);;Todos os arquivos (*.*)",
        )
        if not caminho:
            return
        caminho = os.path.normpath(caminho)
        pasta   = os.path.dirname(caminho)
        cep     = os.path.join(pasta, "cep.fdb")
        existentes = [self._lista.item(i).text() for i in range(self._lista.count())]
        if caminho not in existentes:
            item = QListWidgetItem(caminho)
            item.setToolTip(caminho)
            self._lista.insertItem(0, item)
            self._lbl_count.setText(
                f"{len(existentes)+1} arquivo(s) listado(s) — selecione o Dados:"
            )
        for i in range(self._lista.count()):
            if self._lista.item(i).text() == caminho:
                self._lista.setCurrentRow(i)
                break
        self._lbl_dados.setText(caminho)
        self._lbl_cep.setText(cep)
        self._btn_aplicar.setEnabled(True)
        self._lbl_resultado.setText("")

    def _on_selecao_changed(self):
        items = self._lista.selectedItems()
        if not items:
            self._lbl_dados.setText("—")
            self._lbl_cep.setText("—")
            self._btn_aplicar.setEnabled(False)
            return
        caminho_dados = items[0].text()
        pasta         = os.path.dirname(caminho_dados)
        caminho_cep   = os.path.join(pasta, "cep.fdb")
        self._lbl_dados.setText(caminho_dados)
        self._lbl_cep.setText(caminho_cep)
        self._btn_aplicar.setEnabled(True)
        self._lbl_resultado.setText("")

    def _on_aplicar(self):
        items = self._lista.selectedItems()
        if not items:
            return
        versao        = "3" if self._radio_fb3.isChecked() else "4"
        caminho_dados = items[0].text()

        # Verifica se o Firebird INSTALADO existe (nao o portable)
        pasta_inst = _encontrar_pasta_firebird(versao)
        if not pasta_inst:
            self._lbl_resultado.setText(
                f"Firebird {versao} nao encontrado em Program Files.\n"
                f"Instale o Firebird {versao} antes de configurar."
            )
            self._lbl_resultado.setStyleSheet(
                "color:#e67e22; background:transparent; border:none;"
            )
            return

        self._btn_aplicar.setEnabled(False)
        self._btn_varrer.setEnabled(False)
        self._btn_explorer.setEnabled(False)
        self._lbl_resultado.setText("Aplicando...")
        self._lbl_resultado.setStyleSheet(
            f"color:{COLORS.get('text_mid','#aaa')}; background:transparent; border:none;"
        )
        worker = _DatabasesConfWorker(versao, caminho_dados)
        worker.log.connect(lambda m: None)   # log interno silencioso (sem console na aba)
        worker.concluido.connect(self._on_aplicar_concluido)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _on_aplicar_concluido(self, r: dict):
        self._btn_aplicar.setEnabled(True)
        self._btn_varrer.setEnabled(True)
        self._btn_explorer.setEnabled(True)
        if r["ok"]:
            versao     = "3" if self._radio_fb3.isChecked() else "4"
            conf_path  = r.get("conf_path", "databases.conf")
            self._lbl_resultado.setText(
                f"databases.conf do Firebird {versao} atualizado!\n{conf_path}"
            )
            self._lbl_resultado.setStyleSheet(
                "color:#2ecc71; background:transparent; border:none;"
            )
        else:
            self._lbl_resultado.setText(f"Erro: {r['erro']}")
            self._lbl_resultado.setStyleSheet(
                "color:#e74c3c; background:transparent; border:none;"
            )

    def _lista_style(self) -> str:
        bg   = COLORS.get("bg",      "#0f0f0f")
        surf = COLORS.get("surface", "#181818")
        brd  = COLORS.get("border",  "#2a2a2a")
        acc  = COLORS.get("accent",  "#0078d4")
        txt  = COLORS.get("text")
        return f"""
            QListWidget {{
                background:{bg}; color:{txt};
                border:1px solid {brd}; border-radius:8px;
                padding:6px; outline:none;
            }}
            QListWidget::item {{
                padding:8px 12px; border-radius:6px; margin-bottom:2px;
                color:{COLORS.get('text_mid','#aaa')};
                border-bottom:1px solid {surf};
            }}
            QListWidget::item:selected {{
                background:rgba(0,120,212,0.2); color:{acc};
                border:1px solid {acc}; font-weight:bold;
            }}
            QListWidget::item:hover:!selected {{
                background:{surf}; color:{COLORS.get('text','#fff')};
            }}
            QScrollBar:vertical {{
                background:transparent; width:10px; margin:4px; border-radius:5px;
            }}
            QScrollBar::handle:vertical {{
                background:{brd}; border-radius:5px; min-height:30px;
            }}
            QScrollBar::handle:vertical:hover {{ background:{acc}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0px; }}
        """

    def _upd_style(self, _=""):
        self._lista.setStyleSheet(self._lista_style())
        brd  = COLORS.get("border", "#444")
        tmid = COLORS.get("text_mid", "#aaa")
        for lbl in (self._lbl_dados_tag, self._lbl_cep_tag):
            lbl.setStyleSheet(
                f"color:{COLORS.get('text','#fff')}; background:transparent; border:none;"
            )
        for lbl in (self._lbl_dados, self._lbl_cep):
            lbl.setStyleSheet(
                f"color:{tmid}; background:transparent; border:none;"
            )
        self._lbl_count.setStyleSheet(
            f"color:{tmid}; background:transparent; border:none;"
        )
        acc = COLORS.get("accent", "#0078d4")
        self.setStyleSheet(f"""
            QFrame#db_conf_card_inst {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {COLORS.get('surface','#1a1a1a')},
                    stop:1 {COLORS.get('bg','#121212')});
                border:1.5px solid {brd};
                border-radius:12px;
            }}
        """)
        self._ctrl_frame.setStyleSheet(f"""
            QFrame#db_ctrl_box_inst {{
                background:rgba(255,255,255,0.03);
                border:1px solid {brd};
                border-radius:8px;
            }}
            QRadioButton {{
                color:{COLORS.get('text_mid','#aaa')}; spacing:8px;
            }}
            QRadioButton::indicator {{ width:14px; height:14px; }}
            QRadioButton:checked {{
                color:{acc}; font-weight:bold;
            }}
        """)


# =============================================================================
# Card de Serviço por versão — aba Serviço
# Mostra status, versao instalada e botões iniciar/parar/reiniciar
# =============================================================================

class _ServicoCard(QFrame):
    """
    Card individual de status e controle do serviço do Firebird instalado.
    Regra de exclusão mútua: ativar FB3 para FB4 e vice-versa.
    """
    acao_solicitada = pyqtSignal(str, str)  # (versao, 'iniciar'|'parar'|'reiniciar')

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self._versao = versao
        self.setObjectName(f"svc_card_inst_{versao}")
        self._build_ui()
        self._upd_style()
        theme_manager.theme_changed.connect(lambda _: self._upd_style())

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        # ── Header ────────────────────────────────────────────────────────
        header = QHBoxLayout()
        titulo = QLabel(f"Firebird {self._versao}")
        titulo.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
        titulo.setStyleSheet(
            f"color:{_COR[self._versao]}; background:transparent; border:none;"
        )

        self._badge_status = QLabel("VERIFICANDO")
        self._badge_status.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self._badge_status.setFixedWidth(100)
        self._badge_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header.addWidget(titulo, 1)
        header.addWidget(self._badge_status)
        lay.addLayout(header)

        # ── Separador ─────────────────────────────────────────────────────
        hl = QFrame()
        hl.setFrameShape(QFrame.Shape.HLine)
        hl.setStyleSheet(
            f"background:{COLORS.get('border','#444')}; max-height:1px; border:none;"
        )
        lay.addWidget(hl)

        # ── Indicador de instalação ────────────────────────────────────────
        inst_row = QHBoxLayout()
        self._dot = QWidget()
        self._dot.setFixedSize(10, 10)
        self._dot.setStyleSheet(
            f"background:{COLORS.get('text_dim','#888')}; border-radius:5px;"
        )
        self._lbl_inst = QLabel("Verificando instalacao...")
        self._lbl_inst.setFont(QFont(FONT_SANS, 9))
        self._lbl_inst.setStyleSheet(
            f"color:{COLORS.get('text_mid','#aaa')}; background:transparent; border:none;"
        )
        inst_row.addWidget(self._dot)
        inst_row.addWidget(self._lbl_inst, 1)
        lay.addLayout(inst_row)

        # ── Caminho de instalação ──────────────────────────────────────────
        self._lbl_path = QLabel("")
        self._lbl_path.setFont(QFont(FONT_MONO, 8))
        self._lbl_path.setWordWrap(True)
        self._lbl_path.setStyleSheet(
            f"color:{COLORS.get('text_dim','#666')}; background:transparent; border:none;"
        )
        lay.addWidget(self._lbl_path)

        # ── Aviso de exclusão mútua ────────────────────────────────────────
        self._lbl_exclusao = QLabel("")
        self._lbl_exclusao.setFont(QFont(FONT_SANS, 8))
        self._lbl_exclusao.setWordWrap(True)
        self._lbl_exclusao.setStyleSheet(
            "color:#e67e22; background:transparent; border:none;"
        )
        self._lbl_exclusao.setVisible(False)
        lay.addWidget(self._lbl_exclusao)

        lay.addStretch()

        # ── Botões de controle ─────────────────────────────────────────────
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(8)

        self._btn_iniciar   = make_primary_btn("INICIAR",   110)
        self._btn_parar     = make_secondary_btn("PARAR",   100)
        self._btn_reiniciar = make_secondary_btn("REINICIAR", 110)

        for btn in (self._btn_iniciar, self._btn_parar, self._btn_reiniciar):
            btn.setFixedHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._btn_iniciar.clicked.connect(
            lambda: self.acao_solicitada.emit(self._versao, "iniciar")
        )
        self._btn_parar.clicked.connect(
            lambda: self.acao_solicitada.emit(self._versao, "parar")
        )
        self._btn_reiniciar.clicked.connect(
            lambda: self.acao_solicitada.emit(self._versao, "reiniciar")
        )

        btn_lay.addWidget(self._btn_iniciar)
        btn_lay.addWidget(self._btn_parar)
        btn_lay.addWidget(self._btn_reiniciar)
        btn_lay.addStretch()
        lay.addLayout(btn_lay)

    # ── API pública ───────────────────────────────────────────────────────

    def atualizar(self, instalado: bool, rodando: bool, pasta: str = "",
                  outra_rodando: bool = False):
        """
        Atualiza o card com o estado atual do serviço.
        outra_rodando: indica se a outra versão está ativa (exclusão mútua).
        """
        acc = _COR[self._versao]

        # Dot e texto de status
        if rodando:
            self._dot.setStyleSheet(f"background:{acc}; border-radius:5px;")
            self._lbl_inst.setText(f"Firebird {self._versao} — servico ativo e rodando")
            self._lbl_inst.setStyleSheet(f"color:{acc}; background:transparent; border:none;")
            self._set_badge("RODANDO", acc)
        elif instalado:
            self._dot.setStyleSheet(
                f"background:{COLORS.get('text_dim','#888')}; border-radius:5px;"
            )
            self._lbl_inst.setText(f"Firebird {self._versao} — instalado, servico parado")
            self._lbl_inst.setStyleSheet(
                f"color:{COLORS.get('text_mid','#aaa')}; background:transparent; border:none;"
            )
            self._set_badge("PARADO", COLORS.get("text_dim", "#888"))
        else:
            self._dot.setStyleSheet(
                f"background:{COLORS.get('text_dim','#444')}; border-radius:5px;"
            )
            self._lbl_inst.setText(f"Firebird {self._versao} — nao instalado")
            self._lbl_inst.setStyleSheet(
                f"color:{COLORS.get('text_dim','#666')}; background:transparent; border:none;"
            )
            self._set_badge("NAO INSTALADO", COLORS.get("text_dim", "#555"))

        # Caminho
        self._lbl_path.setText(pasta if pasta else "")

        # Aviso de exclusão mútua
        outra = "4" if self._versao == "3" else "3"
        if outra_rodando and instalado and not rodando:
            self._lbl_exclusao.setText(
                f"[!] Firebird {outra} esta ativo. Ao iniciar o FB{self._versao}, "
                f"o FB{outra} sera parado automaticamente."
            )
            self._lbl_exclusao.setVisible(True)
        else:
            self._lbl_exclusao.setVisible(False)

        # Habilitar/desabilitar botões
        self._btn_iniciar.setEnabled(instalado and not rodando)
        self._btn_parar.setEnabled(rodando)
        self._btn_reiniciar.setEnabled(rodando)

    def set_ocupado(self, v: bool):
        for btn in (self._btn_iniciar, self._btn_parar, self._btn_reiniciar):
            btn.setEnabled(not v)

    # ── Internos ──────────────────────────────────────────────────────────

    def _set_badge(self, texto: str, cor: str):
        self._badge_status.setText(texto)
        brd = COLORS.get("border", "#444")
        if texto == "RODANDO":
            self._badge_status.setStyleSheet(f"""
                QLabel {{
                    background:{cor}; color:#fff;
                    border-radius:4px; padding:2px 6px; font-weight:bold;
                }}
            """)
        else:
            # PARADO, N/A ou NAO INSTALADO — fundo neutro
            self._badge_status.setStyleSheet(f"""
                QLabel {{
                    background:{COLORS.get('surface','#2a2a2a')};
                    color:{cor};
                    border:1px solid {brd};
                    border-radius:4px; padding:2px 6px; font-weight:bold;
                }}
            """)

    def _upd_style(self, _=""):
        acc = _COR[self._versao]
        bg  = COLORS.get("surface", "#1e1e1e")
        brd = COLORS.get("border",  "#444")
        self.setStyleSheet(f"""
            QFrame#svc_card_inst_{self._versao} {{
                background:{bg};
                border:1.5px solid {brd};
                border-radius:12px;
            }}
            QFrame#svc_card_inst_{self._versao}:hover {{
                border:1.5px solid {acc};
                background:{COLORS.get('surface2','#2a2a2a')};
            }}
        """)


# =============================================================================
# Página principal
# =============================================================================

class PageInstalarFirebird(QWidget):
    go_menu = pyqtSignal()

    _IDX_CONFIG    = 0
    _IDX_RUNNING   = 1
    _IDX_RESULTADO = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: InstaladorFirebirdWorker | None = None
        self._svc_worker: _ServicoWorker | None = None
        self._status_worker: QThread | None = None
        self._checker: QThread | None = None
        self._arch          = detect_arch()
        self._tabs_built = {0: True, 1: False, 2: False}
        self._versao_sel    = "4"
        self._version_cards : dict[str, _VersionCard] = {}
        self._svc_cards     : dict[str, _ServicoCard] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = PageHeader("FIREBIRD", "Instalação Oficial do Firebird")
        self._header.back_clicked.connect(self._on_back_clicked)
        root.addWidget(self._header)

        # Container para o conteúdo original
        content_w = QWidget()
        content_lay = QVBoxLayout(content_w)
        content_lay.setContentsMargins(40, 20, 40, 20)
        content_lay.setSpacing(8)

        # Banner admin FORA das abas — igual ao Portable
        if not is_admin():
            self._banner = _BannerAdmin()
            self._banner.reiniciar_solicitado.connect(self._on_reiniciar_admin)
            root.addWidget(self._banner)
        else:
            self._banner = None

        # QTabWidget com Lazy Loading
        self._tabs = QTabWidget()
        self._tabs.setFont(QFont(FONT_SANS, 10))
        self._tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tabs, 1)

        # Aba 0: Instalação (Construção inicial)
        self._tab_install = QWidget()
        ilay = QVBoxLayout(self._tab_install); ilay.setContentsMargins(0, 12, 0, 0); ilay.setSpacing(0)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_config())
        self._stack.addWidget(self._build_running())
        self._stack.addWidget(self._build_resultado())
        ilay.addWidget(self._stack, 1)
        self._tabs.addTab(self._tab_install, "Instalacao")

        # Placeholders
        self._tab_svc = QWidget()
        self._tab_db  = QWidget()
        self._tabs.addTab(self._tab_svc, "Servico")
        self._tabs.addTab(self._tab_db, "Banco de Dados")

        theme_manager.theme_changed.connect(self._upd_tabs_style)
        self._upd_tabs_style()

        self._go_step(self._IDX_CONFIG)
        self._timer_svc = QTimer(self)
        self._timer_svc.setInterval(5000)
        self._timer_svc.timeout.connect(self._atualizar_status_servicos)

        # NÃO iniciamos workers nem verificações aqui. Deixamos para o showEvent.

    def _on_tab_changed(self, index):
        if self._tabs_built.get(index): return
        if index == 1: self._build_tab_svc()
        elif index == 2: self._build_tab_db()
        self._tabs_built[index] = True
        self._upd_tabs_style()

    def _build_tab_svc(self):
        slay = QVBoxLayout(self._tab_svc); slay.setContentsMargins(16, 16, 16, 16); slay.setSpacing(10)
        nota_svc = label("Gerencie o servico do Firebird instalado. Iniciar uma versao para automaticamente a outra.", COLORS["text_mid"], 10); nota_svc.setWordWrap(True); slay.addWidget(nota_svc)
        self._svc_alert = AlertBox("", "info"); self._svc_alert.setVisible(False); slay.addWidget(self._svc_alert)
        svc_cards_lay = QHBoxLayout(); svc_cards_lay.setSpacing(16)
        for v in ("3", "4"):
            card = _ServicoCard(v); card.acao_solicitada.connect(self._on_svc_acao)
            self._svc_cards[v] = card; svc_cards_lay.addWidget(card, 1)
        slay.addLayout(svc_cards_lay)
        slay.addWidget(label("Log de operacoes:", COLORS["text_dim"], 8))
        self._svc_console = LogConsole(max_height=120); slay.addWidget(self._svc_console); slay.addStretch()

    def _build_tab_db(self):
        dlay = QVBoxLayout(self._tab_db); dlay.setContentsMargins(16, 16, 16, 16); dlay.setSpacing(8)
        nota_db = label("Configure quais bancos de dados o Firebird ira expor. Varre o HD, selecione o arquivo Dados e clique em Configurar.", COLORS["text_dim"], 9); nota_db.setWordWrap(True); dlay.addWidget(nota_db)
        self._db_conf_card = _DatabasesConfCard(); dlay.addWidget(self._db_conf_card); dlay.addStretch()

    # =========================================================================
    # Build das telas
    # =========================================================================

    def _build_config(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # Descricao
        desc = label(
            "Utilize este assistente para instalar o Firebird de forma automatizada. "
            "Escolha a versao desejada e clique em Baixar e Instalar.",
            COLORS["text_mid"], 10,
        )
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Cards lado a lado — identico ao _AutoInstallCard do Portable
        card_lay = QHBoxLayout()
        card_lay.setSpacing(16)

        for v in ("3", "4"):
            card = _VersionCard(v, self._arch)
            card.instalar_solicitado.connect(self._on_instalar)
            self._version_cards[v] = card
            card_lay.addWidget(card, 1)

        lay.addLayout(card_lay)
        lay.addStretch()

        return w

    def _build_running(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._progress = ProgressBlock("Instalando Firebird...")
        lay.addWidget(self._progress)

        self._console = LogConsole(max_height=0)
        lay.addWidget(self._console, 1)

        lay.addWidget(h_line())
        lay.addWidget(spacer(h=4))

        self._btn_cancelar = make_secondary_btn("CANCELAR", 140)
        self._btn_cancelar.clicked.connect(self._on_cancelar)

        foot = QHBoxLayout()
        foot.addStretch()
        foot.addWidget(self._btn_cancelar)
        lay.addLayout(foot)

        return w

    def _build_resultado(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._res_alert   = AlertBox("", "success")
        self._res_detalhe = label("", COLORS["text_mid"], 11)
        self._res_detalhe.setWordWrap(True)

        lay.addWidget(self._res_alert)
        lay.addWidget(self._res_detalhe)

        # ── Botões de navegação pós-instalação ────────────────────────────
        self._btn_ir_banco   = make_secondary_btn("IR PARA BANCO DE DADOS", 200)
        self._btn_ir_servico = make_secondary_btn("IR PARA SERVICO", 180)
        self._btn_novo       = make_secondary_btn("NOVA INSTALACAO", 180)

        self._btn_ir_banco.setVisible(False)
        self._btn_ir_servico.setVisible(False)

        self._btn_ir_banco.clicked.connect(self._ir_para_banco)
        self._btn_ir_servico.clicked.connect(self._ir_para_servico)
        self._btn_novo.clicked.connect(self._go_novo)

        foot = QHBoxLayout()
        foot.addWidget(self._btn_ir_banco)
        foot.addWidget(self._btn_ir_servico)
        foot.addStretch()
        foot.addWidget(self._btn_novo)
        lay.addLayout(foot)

        lay.addStretch()
        return w

    # =========================================================================
    # Verificacao de instalacao existente
    # =========================================================================

    def _run_install_check(self):
        class _Checker(QThread):
            done = pyqtSignal(object)
            def run(self_):
                try:
                    self_.done.emit(check_installed_firebird())
                except Exception:
                    self_.done.emit(None)

        self._checker = _Checker(self)
        self._checker.done.connect(self._on_check_done)
        self._checker.start()

    def _on_check_done(self, result):
        """Resultado do check inicial. Agora delegamos a atualização visual ao _atualizar_status_servicos."""
        self._atualizar_status_servicos()

    # =========================================================================
    # Controle de Serviço (aba Serviço)
    # =========================================================================

    def _atualizar_status_servicos(self):
        """Dispara coleta de status em background para não travar a UI."""
        if self._svc_worker and self._svc_worker.isRunning():
            return
        if hasattr(self, "_status_worker") and self._status_worker and self._status_worker.isRunning():
            return

        class _StatusWorker(QThread):
            concluido = pyqtSignal(dict)
            def run(self_):
                st = {v: _status_instalado(v) for v in ("3", "4")}
                self_.concluido.emit(st)

        w = _StatusWorker(self)
        w.concluido.connect(self._aplicar_status_servicos)
        w.finished.connect(lambda: setattr(self, "_status_worker", None))
        self._status_worker = w
        w.start()

    def _aplicar_status_servicos(self, st: dict):
        """Aplica o resultado do status (roda na thread principal — seguro para UI)."""
        for v in ("3", "4"):
            card = self._svc_cards.get(v)
            if card:
                outra = "4" if v == "3" else "3"
                card.atualizar(
                    instalado     = st[v]["instalado"],
                    rodando       = st[v]["rodando"],
                    pasta         = st[v]["pasta"],
                    outra_rodando = st[outra]["rodando"],
                )

        # Sincroniza badge INSTALADO/NÃO INSTALADO dos _VersionCard
        for v in ("3", "4"):
            vc = self._version_cards.get(v)
            if vc:
                vc.set_installed(st[v]["instalado"])

    def _on_svc_acao(self, versao: str, acao: str):
        """Trata clique nos botões Iniciar / Parar / Reiniciar."""
        if not is_admin():
            self._svc_alerta(
                "Permissao de administrador necessaria. Reinicie como Administrador.",
                "warn"
            )
            return

        # Exclusão mútua: ao iniciar, para a outra versão primeiro
        outra = "4" if versao == "3" else "3"
        if acao == "iniciar":
            st_outra = _status_instalado(outra)
            if st_outra["rodando"]:
                self._svc_console.append_line(
                    f"Exclusao mutua: parando Firebird {outra} antes de iniciar {versao}..."
                )
                r_stop = _parar_servico_instalado(outra, self._svc_console.append_line)
                if not r_stop["ok"]:
                    self._svc_alerta(
                        f"Nao foi possivel parar o Firebird {outra}: {r_stop['erro']}",
                        "error"
                    )
                    return

        # Desabilita os cards durante a operação
        for card in self._svc_cards.values():
            card.set_ocupado(True)

        self._svc_alert.setVisible(False)
        self._svc_console.append_line(
            f"Executando '{acao}' no Firebird {versao}..."
        )

        worker = _ServicoWorker(versao, acao)
        worker.log.connect(self._svc_console.append_line)
        worker.concluido.connect(self._on_svc_concluido)
        worker.finished.connect(lambda: setattr(self, "_svc_worker", None))
        self._svc_worker = worker
        worker.start()

    def _on_svc_concluido(self, r: dict):
        versao = r.get("versao", "")
        acao   = r.get("acao", "")

        # Reabilita cards e atualiza status
        for card in self._svc_cards.values():
            card.set_ocupado(False)
        self._atualizar_status_servicos()

        acoes_ptbr = {
            "iniciar":   "iniciado",
            "parar":     "parado",
            "reiniciar": "reiniciado",
        }
        acao_lbl = acoes_ptbr.get(acao, acao)

        if r["ok"]:
            self._svc_alerta(
                f"Firebird {versao} {acao_lbl} com sucesso!",
                "success"
            )
        else:
            self._svc_alerta(
                f"Erro ao executar '{acao}' no Firebird {versao}: {r['erro']}",
                "error"
            )

    def _svc_alerta(self, txt: str, kind: str):
        self._svc_alert.set_text(txt)
        self._svc_alert.set_kind(kind)
        self._svc_alert.setVisible(True)

    # =========================================================================
    # Admin
    # =========================================================================

    def _on_reiniciar_admin(self):
        ok = elevar_como_admin()
        if ok:
            QApplication.quit()
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self, "Erro de elevacao",
                "Nao foi possivel solicitar privilegios de Administrador.\n"
                "Execute o programa manualmente como Administrador.",
            )

    # =========================================================================
    # Instalacao
    # =========================================================================

    def reset(self):
        self._go_step(self._IDX_CONFIG)
        self._run_install_check()

    def _on_instalar(self, versao: str):
        if not is_admin():
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox(self)
            msg.setWindowTitle("Permissao necessaria")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText(
                "A instalacao do Firebird requer privilegios de Administrador.\n\n"
                "O Futura Setup sera reiniciado como Administrador.\n"
                "Confirme no prompt do Windows (UAC) para continuar."
            )
            msg.setStandardButtons(
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
            )
            msg.setDefaultButton(QMessageBox.StandardButton.Ok)
            if msg.exec() == QMessageBox.StandardButton.Ok:
                ok = elevar_como_admin()
                if ok:
                    QApplication.quit()
                else:
                    QMessageBox.critical(
                        self, "Erro de elevacao",
                        "Nao foi possivel solicitar privilegios de Administrador.\n"
                        "Execute o programa manualmente como Administrador.",
                    )
            return

        self._versao_sel = versao
        card = self._version_cards.get(versao)
        if card:
            card.set_loading(True, "Iniciando...", 0)

        self._console.clear_console()
        self._progress.set_progress(0, "Iniciando...")
        self._btn_cancelar.setEnabled(True)
        self._go_step(self._IDX_RUNNING)

        self._worker = InstaladorFirebirdWorker(versao, self._arch, parent=self)
        self._worker.log_line.connect(self._console.append_line)
        self._worker.progress.connect(
            lambda pct, t, d: self._progress.set_progress(pct, f"{t}  {d}".strip())
        )
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_cancelar(self):
        if self._worker and self._worker.isRunning():
            self._btn_cancelar.setEnabled(False)
            self._worker.stop()
            self._worker.wait(3000)

    def _on_finished(self, success: bool, info: dict):
        versao    = self._versao_sel
        card      = self._version_cards.get(versao)
        cancelado = info.get("cancelado", False)
        sem_admin = info.get("sem_admin", False)

        if card:
            card.set_loading(False)
            card.set_installed(success)

        self._worker = None
        # Invalida cache para forçar nova detecção da pasta recém-instalada
        _invalidar_cache_pasta(versao)

        if success:
            ver  = info.get("version", "Firebird")
            arch = info.get("arch", self._arch)
            self._res_alert.set_text(f"{ver} ({arch}) instalado com sucesso!")
            self._res_alert.set_kind("success")
            self._res_detalhe.setText(
                "O servico do Firebird foi iniciado automaticamente.\n"
                "Nenhuma reinicializacao e necessaria."
            )
            self._btn_ir_banco.setVisible(True)
            self._btn_ir_servico.setVisible(True)
            self._db_conf_card.set_version(versao)
            # Atualiza os cards de serviço após instalação
            self._atualizar_status_servicos()
        elif cancelado:
            self._res_alert.set_text("Instalacao cancelada pelo usuario.")
            self._res_alert.set_kind("warn")
            self._res_detalhe.setText("")
            self._btn_ir_banco.setVisible(False)
            self._btn_ir_servico.setVisible(False)
        elif sem_admin:
            self._res_alert.set_text("Permissao insuficiente — execute como Administrador.")
            self._res_alert.set_kind("error")
            self._res_detalhe.setText(
                "Feche o Futura Setup e abra novamente clicando com o botao direito\n"
                "no icone do programa -> Executar como administrador."
            )
            self._btn_ir_banco.setVisible(False)
            self._btn_ir_servico.setVisible(False)
        else:
            self._res_alert.set_text("Falha durante a instalacao. Verifique o log para detalhes.")
            self._res_alert.set_kind("error")
            self._res_detalhe.setText("")
            self._btn_ir_banco.setVisible(False)
            self._btn_ir_servico.setVisible(False)

        self._go_step(self._IDX_RESULTADO)

    def _go_novo(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(1000)
        self._worker = None
        self.reset()

    def _go_step(self, idx: int):
        self._stack.setCurrentIndex(idx)

    def _on_back_clicked(self):
        # Se estiver na aba de instalação e no passo de resultado ou execução, volta pro início da instalação
        if self._tabs.currentIndex() == 0:
            if self._stack.currentIndex() != self._IDX_CONFIG:
                self._go_step(self._IDX_CONFIG)
                return

        self.go_menu.emit()

    def _ir_para_banco(self):
        self._tabs.setCurrentIndex(2)   # aba Banco de Dados
        QTimer.singleShot(300, self._db_conf_card._on_varrer)

    def _ir_para_servico(self):
        self._tabs.setCurrentIndex(1)   # aba Servico
        self._atualizar_status_servicos()

    def showEvent(self, event):
        super().showEvent(event)
        # Delay para garantir fluidez na navegação
        QTimer.singleShot(150, self._run_install_check)
        QTimer.singleShot(300, self._timer_svc.start)

    def hideEvent(self, event):
        self._timer_svc.stop()
        # Encerramento seguro de todas as threads ativas
        for w in (self._worker, self._svc_worker, self._status_worker, self._checker):
            if w and w.isRunning():
                w.wait(200)
        super().hideEvent(event)

    # =========================================================================
    # Estilo das abas
    # =========================================================================

    def _upd_tabs_style(self, _=""):
        bg   = COLORS.get("surface",  "#1e1e1e")
        bg2  = COLORS.get("bg",       "#121212")
        brd  = COLORS.get("border",   "#444")
        txt  = COLORS.get("text",     "#fff")
        tmid = COLORS.get("text_mid", "#aaa")
        acc  = COLORS.get("accent",   "#0078d4")

        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background:{bg};
                border:1.5px solid {brd};
                border-radius:8px;
                padding:12px;
            }}
            QTabBar::tab {{
                background:{bg2};
                color:{tmid};
                border:1px solid {brd};
                border-bottom:none;
                border-top-left-radius:6px;
                border-top-right-radius:6px;
                padding:8px 18px;
                margin-right:3px;
                font-family:{FONT_SANS};
                font-size:10pt;
            }}
            QTabBar::tab:selected {{
                background:{bg};
                color:{txt};
                border-bottom:2px solid {acc};
                font-weight:bold;
            }}
            QTabBar::tab:hover:!selected {{
                background:{bg};
                color:{txt};
            }}
        """)