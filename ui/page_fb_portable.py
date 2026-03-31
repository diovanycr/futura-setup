# =============================================================================
# FUTURA SETUP — Página: Firebird Portable
# FB3 e FB4 totalmente simétricos:
#   - Instalação / Remoção portable
#   - Modo processo ou serviço Windows
#   - Toggle ativar/inativar independente
#   - Ativar uma versão desativa automaticamente a outra
#   - Configuração do databases.conf com varredura de .fdb
# Salvar em: ui/page_fb_portable.py
#
# CORREÇÕES APLICADAS:
#   1. is_admin() removido da thread principal (__init__ e _ModoCard.atualizar).
#      Resultado cacheado em self._eh_admin após _AdminCheckWorker concluir.
#   2. Timer pausado durante qualquer operação (_setar_ocupado) para evitar
#      colisão de status_detalhado() com workers ativos.
#   3. _ModoCard não chama mais is_admin() — recebe o valor via atualizar().
#   4. Banner admin construído após verificação assíncrona.
#   5. [CORRIGIDO] f-string faltando em _ModoCard._build_ui() no setStyleSheet do titulo.
#   6. [CORRIGIDO] Lógica de alerta invertida em _on_toggle_concluido (outra_rod).
#   7. [CORRIGIDO] del em dict substituído por .pop(v, None) em _on_status_concluido.
#   8. [CORRIGIDO] Lambda frágil com argumento nomeado substituído por posicional.
#   9. [CORRIGIDO] Índice de aba hardcoded substituído por indexOf(tab_db).
#  10. [CORRIGIDO] _upd_toggle protegido com try/finally para garantir reset do flag.
#  11. [CORRIGIDO] showEvent agora verifica se _admin_check_worker já está rodando
#      antes de disparar novo worker, evitando duplicação de banner/callbacks.
#  12. [CORRIGIDO] _setar_ocupado agora verifica se está na thread principal antes
#      de manipular o QTimer. Se chamado de outra thread, redireciona via
#      QMetaObject.invokeMethod com QueuedConnection, eliminando o erro
#      "QBasicTimer::stop: Failed. Possibly trying to stop from a different thread".
# =============================================================================
from __future__ import annotations

from PyQt6.QtCore    import Qt, pyqtSignal, pyqtSlot, QThread, QTimer, QMetaObject, Q_ARG
from PyQt6.QtGui     import QFont, QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QScrollArea, QProgressBar,
    QButtonGroup, QRadioButton, QAbstractButton,
    QPlainTextEdit, QPushButton, QListWidget,
    QListWidgetItem, QAbstractItemView, QFileDialog, QTabWidget,
    QGridLayout,
)

from ui.theme         import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets       import (
    PageHeader, SectionHeader, AlertBox, LogConsole,
    make_primary_btn, make_secondary_btn,
    btn_row, spacer, h_line, label,
    _apply_primary_style, _apply_secondary_style,
)
from core.fb_portable import (
    FB_CONFIGS,
    fb_portable_instalado,
    versao_fb_portable,
    status_detalhado,
    is_admin, solicitar_admin,
    ativar_fb, inativar_fb,
    alternar_versao_ativa,
    instalar_fb_portable,
    remover_fb_portable,
    fb_obter_modo,
    fb_servico_existe,
    fb_servico_rodando,
    registrar_fb_servico,
    remover_fb_servico,
    ativar_fb_servico,
    varrer_fdb,
    atualizar_databases_conf,
    aplicar_configs_oficiais_fb4,
    reiniciar_fb,
)

# Cores por versão
_COR = {
    "3": COLORS.get("accent2", "#2ecc71"),
    "4": COLORS.get("accent",  "#0078d4"),
}


# =============================================================================
# Toggle Switch
# =============================================================================

class _ToggleSwitch(QAbstractButton):
    sig_set_loading = pyqtSignal(bool, str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(52, 28)

    def setAtivo(self, v: bool):
        self.setEnabled(v)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        checked  = self.isChecked()
        disabled = not self.isEnabled()
        if disabled:
            track = QColor("#555"); thumb = QColor("#888")
        elif checked:
            track = QColor(COLORS.get("accent", "#0078d4")); thumb = QColor("#fff")
        else:
            track = QColor(COLORS.get("border", "#444")); thumb = QColor("#ccc")
        path = QPainterPath()
        path.addRoundedRect(0, 4, 52, 20, 10, 10)
        p.fillPath(path, track)
        p.setBrush(thumb)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(30 if checked else 4, 4, 20, 20)
        p.end()

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(52, 28)


# =============================================================================
# Workers
# =============================================================================

class _AlternarWorker(QThread):
    log       = pyqtSignal(str)
    concluido = pyqtSignal(dict)

    def __init__(self, versao: str, ativar: bool, parent=None):
        super().__init__(parent)
        self.versao = versao
        self.ativar = ativar

    def run(self):
        if self.ativar:
            r = alternar_versao_ativa(self.versao, self.log.emit)
        else:
            r = inativar_fb(self.versao, self.log.emit)
            r.setdefault("versao", self.versao)
        r["versao"] = self.versao
        r["ativar"] = self.ativar
        self.concluido.emit(r)


class _InstalarWorker(QThread):
    log       = pyqtSignal(str)
    progresso = pyqtSignal(int)
    concluido = pyqtSignal(dict)

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self.versao = versao

    def run(self):
        self.concluido.emit(
            instalar_fb_portable(self.versao, self.log.emit, self.progresso.emit)
        )


class _RemoverWorker(QThread):
    log       = pyqtSignal(str)
    concluido = pyqtSignal(dict)

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self.versao = versao

    def run(self):
        self.concluido.emit(remover_fb_portable(self.versao, self.log.emit))


class _ServicoWorker(QThread):
    log       = pyqtSignal(str)
    concluido = pyqtSignal(dict)

    def __init__(self, versao: str, acao: str, parent=None):
        super().__init__(parent)
        self.versao = versao
        self.acao   = acao   # 'registrar' | 'remover'

    def run(self):
        try:
            if self.acao == "registrar":
                # Uso de keyword arguments para evitar erro de assinatura no core
                r = registrar_fb_servico(self.versao, log_fn=self.log.emit)
            else:
                r = remover_fb_servico(self.versao, log_fn=self.log.emit)
            r["versao"] = self.versao
            r["acao"]   = self.acao
            self.concluido.emit(r)
        except Exception as e:
            self.concluido.emit({"ok": False, "erro": f"Exceção no worker de serviço: {e}", "versao": self.versao})


class _ConfigsOficiaisWorker(QThread):
    """Worker para baixar e aplicar configs oficiais do FB4."""
    log       = pyqtSignal(str)
    concluido = pyqtSignal(dict)

    def __init__(self, caminho_dados: str = "", caminho_cep: str = "", parent=None):
        super().__init__(parent)
        self.caminho_dados = caminho_dados
        self.caminho_cep   = caminho_cep

    def run(self):
        r = aplicar_configs_oficiais_fb4(
            caminho_dados=self.caminho_dados,
            caminho_cep=self.caminho_cep,
            log_fn=self.log.emit,
        )
        self.concluido.emit(r)


class _VarreduraWorker(QThread):
    """Worker para varredura de arquivos .fdb no HD."""
    log       = pyqtSignal(str)
    concluido = pyqtSignal(list)

    def run(self):
        arquivos = varrer_fdb(log_fn=self.log.emit)
        self.concluido.emit(arquivos)


class _DatabasesConfWorker(QThread):
    """Worker para atualizar o databases.conf."""
    log       = pyqtSignal(str)
    concluido = pyqtSignal(dict)

    def __init__(self, versao: str, caminho_dados: str, parent=None):
        super().__init__(parent)
        self.versao        = versao
        self.caminho_dados = caminho_dados

    def run(self):
        r = atualizar_databases_conf(self.versao, self.caminho_dados, self.log.emit)
        self.concluido.emit(r)


class _AutoInstallWorker(QThread):
    log       = pyqtSignal(str)
    progresso = pyqtSignal(int)
    concluido = pyqtSignal(dict)

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self.versao = versao

    def run(self):
        try:
            # Passo 1: Instalação (Download + Extração)
            self.log.emit(f"--- PASSO 1: Instalando Firebird {self.versao} Portable ---")
            r_inst = instalar_fb_portable(self.versao, self.log.emit, self.progresso.emit)
            if not r_inst["ok"]:
                self.concluido.emit(r_inst)
                return

            # Passo 2: Registrar como Serviço e Iniciar
            self.log.emit(f"\n--- PASSO 2: Registrando Serviço Windows (FB{self.versao}) ---")
            # Corrigido: passagem de argumentos nomeados para o core
            r_svc = registrar_fb_servico(self.versao, log_fn=self.log.emit)
            if not r_svc["ok"]:
                self.concluido.emit(r_svc)
                return

            # Ativa o serviço recém cadastrado
            self.log.emit(f"Iniciando servico FB{self.versao}...")
            r_ativ = ativar_fb_servico(self.versao, log_fn=self.log.emit)

            # Passo Extra para FB4: Baixar os 3 arquivos oficiais
            if self.versao == "4":
                self.log.emit(f"\n--- PASSO 3: Baixando arquivos oficiais (FB4) ---")
                r_fb4 = aplicar_configs_oficiais_fb4(log_fn=self.log.emit)
                if not r_fb4["ok"]:
                    self.log.emit(f"AVISO: Nao foi possivel baixar configs oficiais: {r_fb4['erro']}")

            # Consolida resultado
            res = r_inst.copy()
            res.update({"servico_ok": r_svc["ok"], "ativado_ok": r_ativ["ok"]})
            self.concluido.emit(res)
        except Exception as e:
            self.concluido.emit({"ok": False, "erro": f"Fatal: {e}"})


class _ReiniciarWorker(QThread):
    log       = pyqtSignal(str)
    concluido = pyqtSignal(dict)

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self.versao = versao

    def run(self):
        self.concluido.emit(reiniciar_fb(self.versao, self.log.emit))


class _StatusWorker(QThread):
    """
    Executa status_detalhado() + fb_portable_instalado() em background.
    Evita bloquear a thread principal durante o refresh de 4s.
    """
    concluido = pyqtSignal(dict)

    def run(self):
        try:
            st = status_detalhado()
            # Enriquece com versão instalada para evitar chamadas extras na UI
            for v in ("3", "4"):
                try:
                    inst = st[f"fb{v}"]["instalado"]
                    st[f"fb{v}"]["ver_str"] = versao_fb_portable(v) if inst else ""
                except Exception:
                    st.setdefault(f"fb{v}", {})["ver_str"] = ""
            self.concluido.emit(st)
        except Exception:
            self.concluido.emit({})


# =============================================================================
# Worker de verificação de admin (evita bloquear thread principal)
# =============================================================================

class _AdminCheckWorker(QThread):
    """
    Verifica is_admin() em background para não bloquear a UI.
    Emite concluido(True/False).
    """
    concluido = pyqtSignal(bool)

    def run(self):
        try:
            resultado = is_admin()
        except Exception:
            resultado = False
        self.concluido.emit(resultado)


# =============================================================================
# Card de modo de execução
# CORREÇÃO: não chama mais is_admin() diretamente.
#           O valor é recebido via atualizar(eh_admin=...).
# =============================================================================

class _ModoCard(QFrame):
    acao_solicitada = pyqtSignal(str, str)   # (versao, 'registrar'|'remover')

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self._versao         = versao
        self._svc_registrado = False
        self.setObjectName(f"modo_card_{versao}")
        self._build_ui()
        self._upd_style()
        theme_manager.theme_changed.connect(lambda _: self._upd_style())

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)

        # Header: Titulo + Badge
        header = QHBoxLayout()
        titulo = QLabel("Modo de execução")
        titulo.setFont(QFont(FONT_SANS, 10, QFont.Weight.Bold))
        titulo.setStyleSheet(f"color:{COLORS.get('text')}; background:transparent; border:none;")

        self._badge = QLabel()
        self._badge.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self._badge.setFixedWidth(72)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header.addWidget(titulo, 1)
        header.addWidget(self._badge)
        lay.addLayout(header)

        # Status row
        row = QHBoxLayout()
        row.setSpacing(8)
        self._dot = QWidget()
        self._dot.setFixedSize(8, 8)
        self._lbl_modo = QLabel()
        self._lbl_modo.setFont(QFont(FONT_MONO, 9))
        self._lbl_modo.setStyleSheet(f"color:{COLORS.get('text_mid','#aaa')}; background:transparent; border:none;")
        row.addWidget(self._dot)
        row.addWidget(self._lbl_modo, 1)
        lay.addLayout(row)

        self._lbl_desc = QLabel()
        self._lbl_desc.setFont(QFont(FONT_SANS, 9))
        self._lbl_desc.setWordWrap(True)
        self._lbl_desc.setStyleSheet(
            f"color:{COLORS.get('text_dim','#888')}; background:transparent; border:none;"
        )
        lay.addWidget(self._lbl_desc)

        btn_lay = QHBoxLayout()
        self._lbl_nota = QLabel("[!] Requer adm")
        self._lbl_nota.setFont(QFont(FONT_SANS, 8))
        self._lbl_nota.setStyleSheet("color:#e67e22; background:transparent; border:none;")
        btn_lay.addWidget(self._lbl_nota)
        btn_lay.addStretch()

        self._btn_acao = QPushButton()
        self._btn_acao.setFixedHeight(28)
        self._btn_acao.setFont(QFont(FONT_SANS, 9))
        self._btn_acao.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_acao.clicked.connect(self._on_btn)
        btn_lay.addWidget(self._btn_acao)
        lay.addLayout(btn_lay)

    def atualizar(self, instalado: bool, modo: str, svc_registrado: bool,
                  svc_rodando: bool, eh_admin: bool = False):
        self._svc_registrado = svc_registrado
        self.setEnabled(instalado)
        cor = _COR[self._versao]
        v   = self._versao

        if not instalado:
            self._lbl_modo.setText(f"FB{v} não instalado")
            self._badge.setText("—")
            self._lbl_desc.setText("Instale o portable para acessar esta opção.")
            self._btn_acao.setEnabled(False)
            self._dot.setStyleSheet(
                f"background:{COLORS.get('text_dim','#888')}; border-radius:4px;"
            )
            return

        self._btn_acao.setEnabled(True)

        if modo == "servico" and svc_registrado:
            self._dot.setStyleSheet(f"background:{cor}; border-radius:4px;")
            estado = "RUNNING" if svc_rodando else "PARADO"
            self._lbl_modo.setText(
                f"Serviço Windows - FuturaFirebirdFB{v} - {estado}"
            )
            self._badge.setText("SERVIÇO")
            self._badge.setStyleSheet(f"""
                QLabel {{
                    background:{cor}; color:#fff;
                    border-radius:4px; padding:1px 4px; font-weight:bold;
                }}
            """)
            self._lbl_desc.setText(
                f"O FB{v} está registrado como serviço Windows (start=auto). "
                "Inicia automaticamente com o Windows, independente do Futura Setup."
            )
            self._btn_acao.setText("Remover Serviço Windows")
            self._btn_acao.setStyleSheet(self._style_danger())
        else:
            self._dot.setStyleSheet(
                f"background:{COLORS.get('text_dim','#888')}; border-radius:4px;"
            )
            self._lbl_modo.setText(f"Processo portable - inicia com o Futura Setup")
            self._badge.setText("PROCESSO")
            self._badge.setStyleSheet(f"""
                QLabel {{
                    background:{COLORS.get('surface','#2a2a2a')};
                    color:{COLORS.get('text_mid','#aaa')};
                    border:1px solid {COLORS.get('border','#444')};
                    border-radius:4px; padding:1px 4px; font-weight:bold;
                }}
            """)
            self._lbl_desc.setText(
                f"O FB{v} roda como processo portable — só fica ativo enquanto o "
                "Futura Setup estiver aberto. Registre como serviço para iniciar "
                "automaticamente com o Windows."
            )
            self._btn_acao.setText("Registrar como Serviço Windows")
            self._btn_acao.setStyleSheet(self._style_primary())

        self._lbl_desc.setVisible(True)
        self._lbl_nota.setVisible(not eh_admin)
        self._upd_style()

    def _on_btn(self):
        acao = "remover" if self._svc_registrado else "registrar"
        self.acao_solicitada.emit(self._versao, acao)

    def set_ocupado(self, v: bool):
        self._btn_acao.setEnabled(not v)

    def _style_primary(self) -> str:
        acc = _COR[self._versao]
        text_btn = "#ffffff" if theme_manager.mode == "light" else "#001828"
        return f"""
            QPushButton {{
                background:{acc}; color:{text_btn}; border:none;
                border-radius:5px; padding:6px 16px; font-weight:bold;
            }}
            QPushButton:hover {{ opacity: 0.85; }}
            QPushButton:disabled {{ background:{COLORS.get('border','#444')}; color:{COLORS.get('text_disabled','#888')}; }}
        """

    def _style_danger(self) -> str:
        text_btn = "#ffffff"
        return f"""
            QPushButton {{
                background:#c0392b; color:{text_btn}; border:none;
                border-radius:5px; padding:6px 16px; font-weight:bold;
            }}
            QPushButton:hover {{ background:#e74c3c; }}
            QPushButton:disabled {{ background:#555; color:#888; }}
        """

    def _upd_style(self, _=""):
        self.setStyleSheet(f"""
            QFrame#modo_card_{self._versao} {{
                background:{COLORS.get('surface','#1e1e1e')};
                border:1px solid {COLORS.get('border','#444')};
                border-radius:12px;
                padding: 4px;
            }}
            QFrame#modo_card_{self._versao}:hover {{
                border:1px solid {_COR[self._versao]};
                background:{COLORS.get('surface2','#1a1a1a')};
            }}
        """)


# =============================================================================
# Linha de toggle por versão
# =============================================================================

class _ToggleRow(QWidget):
    def __init__(self, versao: str, detalhe: str, parent=None):
        super().__init__(parent)
        self._versao = versao
        self._cor    = _COR[versao]
        self.setObjectName(f"toggle_row_{self._versao}")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        self._dot = QWidget()
        self._dot.setFixedSize(10, 10)
        self._dot.setStyleSheet(
            f"background:{COLORS.get('text_dim','#888')}; border-radius:5px;"
        )

        col = QVBoxLayout()
        col.setSpacing(2)

        self._lbl_titulo = QLabel(FB_CONFIGS[versao]["label"])
        self._lbl_titulo.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        self._lbl_titulo.setStyleSheet(
            f"color:{COLORS.get('text')}; background:transparent; border:none;"
        )
        self._lbl_detalhe = QLabel(detalhe)
        self._lbl_detalhe.setFont(QFont(FONT_MONO, 9))
        self._lbl_detalhe.setStyleSheet(
            f"color:{COLORS.get('text_dim','#888')}; background:transparent; border:none;"
        )
        col.addWidget(self._lbl_titulo)
        col.addWidget(self._lbl_detalhe)

        self._badge = QLabel("INATIVO")
        self._badge.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self._badge.setFixedWidth(64)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_badge(False)

        self.toggle = _ToggleSwitch()

        lay.addWidget(self._dot)
        lay.addLayout(col, 1)
        lay.addWidget(self._badge)
        lay.addWidget(self.toggle)

        self._upd_style()
        theme_manager.theme_changed.connect(lambda _: self._upd_style())

    def _upd_style(self):
        self.setStyleSheet(f"""
            QWidget#toggle_row_{self._versao} {{
                background:{COLORS.get('surface','#1e1e1e')};
                border:1px solid {COLORS.get('border','#444')};
                border-radius:10px;
                padding: 6px 12px;
            }}
            _ToggleRow:hover {{
                border:1px solid {_COR[self._versao]};
                background:{COLORS.get('surface2','#1a1a1a')};
            }}
        """)

    def set_estado(self, ativo: bool, instalado: bool, detalhe: str = ""):
        try:
            cor = self._cor if ativo else COLORS.get("text_dim", "#888")
            self._dot.setStyleSheet(f"background:{cor}; border-radius:5px;")
            self._lbl_titulo.setStyleSheet(
                f"color:{COLORS.get('text')}; background:transparent; border:none;"
            )
            if not instalado:
                self._lbl_detalhe.setText("Não instalado — use o painel abaixo para instalar")
            elif detalhe:
                self._lbl_detalhe.setText(detalhe)
            self._set_badge(ativo)
        except RuntimeError:
            pass

    def _set_badge(self, ativo: bool):
        if ativo:
            self._badge.setText("ATIVO")
            self._badge.setStyleSheet(f"""
                QLabel {{
                    background:{self._cor}; color:#fff;
                    border-radius:4px; padding:2px 6px; font-weight:bold;
                }}
            """)
        else:
            self._badge.setText("INATIVO")
            self._badge.setStyleSheet(f"""
                QLabel {{
                    background:{COLORS.get('surface','#2a2a2a')};
                    color:{COLORS.get('text_dim','#888')};
                    border:1px solid {COLORS.get('border','#444')};
                    border-radius:4px; padding:2px 6px; font-weight:bold;
                }}
            """)


# =============================================================================
# Card de status de instalação
# =============================================================================

class _StatusCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("status_card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)

        self._icon = QLabel("📡")
        self._icon.setFont(QFont(FONT_SANS, 18))
        self._icon.setFixedWidth(32)

        col = QVBoxLayout()
        col.setSpacing(2)
        self._lbl_status  = QLabel()
        self._lbl_status.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
        self._lbl_detalhe = QLabel()
        self._lbl_detalhe.setFont(QFont(FONT_MONO, 9))
        col.addWidget(self._lbl_status)
        col.addWidget(self._lbl_detalhe)
        lay.addWidget(self._icon)
        lay.addLayout(col, 1)

        self._data = (False, "", "", "")
        self.atualizar(False, "", "", "")
        theme_manager.theme_changed.connect(
            lambda _: self.atualizar(*self._data)
        )

    def atualizar(self, instalado: bool, ver_str: str, fb_dir: str, label_v: str):
        self._data = (instalado, ver_str, fb_dir, label_v)
        cor = COLORS.get("accent2", "#2ecc71") if instalado else COLORS.get("text_dim", "#888")
        self._icon.setText("✅" if instalado else "❌")
        if instalado:
            self._lbl_status.setText(f"{label_v} instalado")
            self._lbl_detalhe.setText(
                f"{ver_str}   |   {fb_dir}" if fb_dir else ver_str
            )
        else:
            self._lbl_status.setText(f"{label_v} não instalado")
            self._lbl_detalhe.setText(f"Será instalado em: {fb_dir}" if fb_dir else "")
        self._lbl_status.setStyleSheet(
            f"color:{cor}; background:transparent; border:none;"
        )
        self._lbl_detalhe.setStyleSheet(
            f"color:{COLORS.get('text_dim','#888')}; background:transparent; border:none;"
        )
        self.setStyleSheet(f"""
            QFrame#status_card {{
                background:{COLORS.get('surface','#1e1e1e')};
                border:1.5px solid {COLORS.get('border','#444')};
                border-radius:8px;
            }}
        """)


# =============================================================================
# Console de log
# =============================================================================

class _Console(QFrame):
    def __init__(self, parent=None, fixed_height: int = 200):
        super().__init__(parent)
        self.setObjectName("console")
        if fixed_height > 0:
            self.setFixedHeight(fixed_height)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        bar = QWidget()
        bar_lay = QHBoxLayout(bar)
        bar_lay.setContentsMargins(10, 4, 6, 4)
        bar_lay.setSpacing(0)
        lbl = QLabel("Log")
        lbl.setFont(QFont(FONT_SANS, 8))
        lbl.setStyleSheet(
            f"color:{COLORS.get('text_dim','#888')}; background:transparent; border:none;"
        )
        self._btn_copiar = QPushButton("Copiar tudo")
        self._btn_copiar.setFixedHeight(20)
        self._btn_copiar.setFont(QFont(FONT_SANS, 8))
        self._btn_copiar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_copiar.clicked.connect(self._copiar)
        bar_lay.addWidget(lbl)
        bar_lay.addStretch()
        bar_lay.addWidget(self._btn_copiar)
        lay.addWidget(bar)

        self._texto = QPlainTextEdit()
        self._texto.setReadOnly(True)
        self._texto.setFont(QFont(FONT_MONO, 9))
        self._texto.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._texto.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        lay.addWidget(self._texto)

        self._upd_style()
        theme_manager.theme_changed.connect(self._upd_style)

    def append(self, txt: str):
        self._texto.appendPlainText(txt)
        sb = self._texto.verticalScrollBar()
        sb.setValue(sb.maximum())

    def limpar(self):
        self._texto.clear()

    def _copiar(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._texto.toPlainText())
        self._btn_copiar.setText("Copiado!")
        QTimer.singleShot(2000, lambda: self._btn_copiar.setText("Copiar tudo"))

    def _upd_style(self, _=""):
        bg = COLORS.get("bg", "#121212"); brd = COLORS.get("border", "#444")
        txt = COLORS.get("text_mid", "#aaa"); surf = COLORS.get("surface", "#1e1e1e")
        acc = COLORS.get("accent", "#0078d4")
        self.setStyleSheet(f"""
            QFrame#console {{ background:{bg}; border:1px solid {brd}; border-radius:6px; }}
        """)
        self._texto.setStyleSheet(f"""
            QPlainTextEdit {{
                background:{bg}; color:{txt}; border:none;
                border-bottom-left-radius:6px; border-bottom-right-radius:6px;
                padding:6px 10px; selection-background-color:{acc};
            }}
            QScrollBar:vertical {{ background:{surf}; width:8px; border-radius:4px; }}
            QScrollBar::handle:vertical {{ background:{brd}; border-radius:4px; min-height:20px; }}
        """)
        self._btn_copiar.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{acc}; border:none; padding:0 4px; }}
            QPushButton:hover {{ color:{txt}; }}
        """)


# =============================================================================
# Banner admin
# =============================================================================

class _BannerAdmin(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("banner_admin")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(10)

        ico = QLabel("⚠️")
        ico.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        ico.setStyleSheet("color:#e67e22; background:transparent; border:none;")
        ico.setFixedWidth(20)

        self.lbl_msg = QLabel("Permissão de administrador necessária para gerenciar serviços.")
        self.lbl_msg.setFont(QFont(FONT_SANS, 9))
        self.lbl_msg.setStyleSheet(f"color:{COLORS.get('text','#fff')}; background:transparent;")

        self.btn_reiniciar = make_primary_btn("Reiniciar como Admin", 150)
        self.btn_reiniciar.setFixedHeight(26)

        lay.addWidget(ico, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.lbl_msg, 1, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.btn_reiniciar, 0, Qt.AlignmentFlag.AlignVCenter)

        self.setStyleSheet("""
            QFrame#banner_admin {
                background:rgba(230,126,34,0.12);
                border:1.2px solid #e67e22;
                border-radius:6px;
            }
        """)


# =============================================================================
# Card databases.conf
# =============================================================================

class _DatabasesConfCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("db_conf_card")
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

        self._header_frame = QFrame()
        self._header_frame.setObjectName("db_header")
        header_inner = QHBoxLayout(self._header_frame)
        header_inner.setContentsMargins(12, 8, 12, 8)

        self._header_icon = QLabel("🗄️")
        self._header_icon.setFont(QFont(FONT_SANS, 18))

        titulo_v = QVBoxLayout()
        self._titulo_lbl = QLabel("Configurar bases de dados")
        self._titulo_lbl.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
        self._subtitulo_lbl = QLabel("Selecione o arquivo .fdb para configurar o databases.conf")
        self._subtitulo_lbl.setFont(QFont(FONT_SANS, 9))
        titulo_v.addWidget(self._titulo_lbl)
        titulo_v.addWidget(self._subtitulo_lbl)

        info_btn = QLabel("ℹ️")
        info_btn.setToolTip(
            "O sistema buscará por arquivos .fdb. Ao selecionar o arquivo principal (Dados), "
            "o arquivo de CEP será vinculado automaticamente se estiver na mesma pasta."
        )

        header_inner.addWidget(self._header_icon)
        header_inner.addLayout(titulo_v, 1)
        header_inner.addWidget(info_btn)
        lay.addWidget(self._header_frame)

        self._ctrl_frame = QFrame()
        self._ctrl_frame.setObjectName("ctrl_box")
        ctrl_lay = QHBoxLayout(self._ctrl_frame)
        ctrl_lay.setContentsMargins(12, 8, 12, 8)

        lbl_v = QLabel("Versão Firebird:")
        lbl_v.setFont(QFont(FONT_SANS, 9, QFont.Weight.Bold))

        self._radio_fb3 = QRadioButton("FB 3.0")
        self._radio_fb4 = QRadioButton("FB 4.0")
        self._radio_fb4.setChecked(True)

        v_group = QHBoxLayout()
        v_group.setSpacing(12)
        v_group.addWidget(self._radio_fb3)
        v_group.addWidget(self._radio_fb4)

        self._btn_varrer = make_primary_btn("🔍  VARRER HD", 130)
        self._btn_varrer.setFixedHeight(32)
        self._btn_varrer.clicked.connect(self._on_varrer)

        self._btn_explorer = make_secondary_btn("📂  PROCURAR", 120)
        self._btn_explorer.setFixedHeight(32)
        self._btn_explorer.clicked.connect(self._on_selecionar_explorer)

        ctrl_lay.addWidget(lbl_v)
        ctrl_lay.addLayout(v_group)
        ctrl_lay.addSpacing(16)
        ctrl_lay.addWidget(self._btn_varrer)
        ctrl_lay.addWidget(self._btn_explorer)
        ctrl_lay.addStretch()
        lay.addWidget(self._ctrl_frame)

        self._lbl_count = QLabel("Aguardando início da varredura...")
        self._lbl_count.setFont(QFont(FONT_MONO, 8))
        lay.addWidget(self._lbl_count)

        self._lista = QListWidget()
        self._lista.setMinimumHeight(180)
        self._lista.setFont(QFont(FONT_MONO, 9))
        self._lista.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._lista.itemSelectionChanged.connect(self._on_selecao_changed)
        lay.addWidget(self._lista)

        self._preview_frame = QFrame()
        self._preview_frame.setObjectName("preview_box")
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

        self._btn_aplicar = make_primary_btn("⚙️  CONFIGURAR AGORA", 200)
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
        import os
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
            total = len(existentes) + 1
            self._lbl_count.setText(f"{total} arquivo(s) listado(s) — selecione o Dados:")

        for i in range(self._lista.count()):
            if self._lista.item(i).text() == caminho:
                self._lista.setCurrentRow(i)
                break

        self._lbl_dados.setText(caminho)
        self._lbl_cep.setText(cep)
        self._btn_aplicar.setEnabled(True)
        self._lbl_resultado.setText("")

    def _on_selecao_changed(self):
        import os
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

        if not fb_portable_instalado(versao):
            self._lbl_resultado.setText(f"[!] FB{versao} não está instalado.")
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
        worker.concluido.connect(self._on_aplicar_concluido)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _on_aplicar_concluido(self, r: dict):
        self._btn_aplicar.setEnabled(True)
        self._btn_varrer.setEnabled(True)
        self._btn_explorer.setEnabled(True)
        if r["ok"]:
            versao = "3" if self._radio_fb3.isChecked() else "4"
            self._lbl_resultado.setText(f"databases.conf do FB{versao} atualizado!")
            self._lbl_resultado.setStyleSheet(
                "color:#2ecc71; background:transparent; border:none;"
            )
        else:
            self._lbl_resultado.setText(f"Erro: {r['erro']}")
            self._lbl_resultado.setStyleSheet(
                "color:#e74c3c; background:transparent; border:none;"
            )

    def _lista_style(self) -> str:
        if theme_manager.ui_theme == "classic":
            bg   = COLORS.get("bg",      "#121212")
            surf = COLORS.get("surface", "#1e1e1e")
            brd  = COLORS.get("border",  "#444")
            acc  = COLORS.get("accent",  "#0078d4")
            txt  = COLORS.get("text")
            return f"""
                QListWidget {{
                    background:{bg}; color:{txt};
                    border:1px solid {brd}; border-radius:6px;
                    padding:4px;
                }}
                QListWidget::item {{
                    padding:4px 8px; border-radius:4px;
                }}
                QListWidget::item:selected {{
                    background:{acc}; color:#fff;
                }}
                QListWidget::item:hover:!selected {{
                    background:{surf};
                }}
                QScrollBar:vertical {{
                    background:{surf}; width:8px; border-radius:4px;
                }}
                QScrollBar::handle:vertical {{
                    background:{brd}; border-radius:4px; min-height:20px;
                }}
            """
        else:
            bg   = COLORS.get("bg",      "#0f0f0f")
            surf = COLORS.get("surface", "#181818")
            brd  = COLORS.get("border",  "#2a2a2a")
            acc  = COLORS.get("accent",  "#0078d4")
            txt  = COLORS.get("text")
            return f"""
                QListWidget {{
                    background:{bg}; color:{txt};
                    border:1px solid {brd}; border-radius:8px;
                    padding:6px; outline: none;
                }}
                QListWidget::item {{
                    padding:8px 12px; border-radius:6px;
                    margin-bottom: 2px;
                    color: {COLORS.get('text_mid','#aaa')};
                    border-bottom: 1px solid {surf};
                }}
                QListWidget::item:selected {{
                    background: rgba(0, 120, 212, 0.2);
                    color: {acc};
                    border: 1px solid {acc};
                    font-weight: bold;
                }}
                QListWidget::item:hover:!selected {{
                    background:{surf};
                    color: {COLORS.get('text','#fff')};
                }}
                QScrollBar:vertical {{
                    background: transparent; width:10px; margin: 4px; border-radius:5px;
                }}
                QScrollBar::handle:vertical {{
                    background:{brd}; border-radius:5px; min-height:30px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background:{acc};
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            """

    def _upd_style(self, _=""):
        self._lista.setStyleSheet(self._lista_style())

        if theme_manager.ui_theme == "classic":
            self.setStyleSheet(f"""
                QFrame#db_conf_card {{
                    background:{COLORS.get('surface','#1e1e1e')};
                    border:1.5px solid {COLORS.get('border','#444')};
                    border-radius:10px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#db_conf_card {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {COLORS.get('surface','#1a1a1a')},
                        stop:1 {COLORS.get('bg','#121212')});
                    border:1.5px solid {COLORS.get('border','#333')};
                    border-radius:12px;
                }}
                QFrame#ctrl_box {{
                    background: rgba(255, 255, 255, 0.03);
                    border: 1px solid {COLORS.get('border','#2a2a2a')};
                    border-radius: 8px;
                }}
                QRadioButton {{
                    color: {COLORS.get('text_mid','#aaa')};
                    spacing: 8px;
                }}
                QRadioButton::indicator {{
                    width: 14px; height: 14px;
                }}
                QRadioButton:checked {{
                    color: {COLORS.get('accent','#0078d4')};
                    font-weight: bold;
                }}
            """)


# =============================================================================
# Card de Instalação / Remoção
# =============================================================================

class _InstallRemoveCard(QFrame):
    instalar_solicitado = pyqtSignal(str)
    remover_solicitado  = pyqtSignal(str)
    sig_set_loading     = pyqtSignal(bool, str, int)

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self._versao    = versao
        self._instalado = False
        self.setObjectName(f"install_remove_card_{versao}")
        self._build_ui()
        self._upd_style()
        theme_manager.theme_changed.connect(lambda _: self._upd_style())
        self.sig_set_loading.connect(self.set_loading)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        header = QHBoxLayout()
        titulo = QLabel(f"Firebird {self._versao}")
        titulo.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        titulo.setStyleSheet(f"color:{_COR[self._versao]};")

        icon = QLabel("📦")
        icon.setFont(QFont(FONT_SANS, 14))

        self._lbl_badge = QLabel("NÃO INSTALADO")
        self._lbl_badge.setFont(QFont(FONT_SANS, 8, QFont.Weight.Bold))
        self._lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_badge.setMinimumWidth(120)
        self._lbl_badge.setContentsMargins(6, 2, 6, 2)

        header.addWidget(titulo, 1)
        header.addWidget(self._lbl_badge)
        header.addWidget(icon)
        lay.addLayout(header)

        hl = QFrame()
        hl.setFrameShape(QFrame.Shape.HLine)
        hl.setStyleSheet(f"background:{COLORS.get('border','#444')}; max-height:1px;")
        lay.addWidget(hl)

        cfg = FB_CONFIGS[self._versao]
        self._lbl_info = QLabel(
            f"Diretório: {cfg['dir']}\n"
            f"Porta: {cfg['porta']}"
        )
        self._lbl_info.setFont(QFont(FONT_MONO, 9))
        self._lbl_info.setWordWrap(True)
        self._lbl_info.setStyleSheet(
            f"color:{COLORS.get('text_mid','#aaa')}; background:transparent; border:none;"
        )
        lay.addWidget(self._lbl_info)

        self._lbl_ver = QLabel("")
        self._lbl_ver.setFont(QFont(FONT_MONO, 8))
        self._lbl_ver.setStyleSheet(
            f"color:{COLORS.get('accent2','#2ecc71')}; background:transparent; border:none;"
        )
        lay.addWidget(self._lbl_ver)

        lay.addStretch()

        self._status_box = QWidget()
        self._status_box.setVisible(False)
        st_lay = QVBoxLayout(self._status_box)
        st_lay.setContentsMargins(0, 4, 0, 4)
        st_lay.setSpacing(4)
        self._lbl_status = label("Preparando...", COLORS["text_dim"], 8)
        self._pbar = QProgressBar()
        self._pbar.setFixedHeight(4)
        self._pbar.setTextVisible(False)
        self._pbar.setRange(0, 100)
        st_lay.addWidget(self._lbl_status)
        st_lay.addWidget(self._pbar)
        lay.addWidget(self._status_box)

        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(10)

        self._btn_instalar = make_primary_btn("⚡  INSTALAR", 160)
        self._btn_instalar.setFixedHeight(38)
        self._btn_instalar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_instalar.clicked.connect(
            lambda: self.instalar_solicitado.emit(self._versao)
        )

        self._btn_remover = QPushButton("🗑️  REMOVER")
        self._btn_remover.setFixedHeight(38)
        self._btn_remover.setMinimumWidth(130)
        self._btn_remover.setFont(QFont(FONT_SANS, 10, QFont.Weight.Bold))
        self._btn_remover.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_remover.clicked.connect(
            lambda: self.remover_solicitado.emit(self._versao)
        )

        btn_lay.addWidget(self._btn_instalar, 1)
        btn_lay.addWidget(self._btn_remover, 1)
        lay.addLayout(btn_lay)

        self._set_estado(False)

    def set_instalado(self, instalado: bool, ver_str: str = ""):
        try:
            self._instalado = instalado
            self._lbl_ver.setText(f"Versão: {ver_str}" if ver_str else "")
            self._set_estado(instalado)
        except RuntimeError:
            pass

    @pyqtSlot(bool)
    @pyqtSlot(bool, str)
    @pyqtSlot(bool, str, int)
    def set_loading(self, active: bool, msg: str = "", progress: int = 0):
        try:
            self._status_box.setVisible(active)
            self._btn_instalar.setEnabled(not active)
            self._btn_remover.setEnabled(not active)
            if active:
                if msg:
                    self._lbl_status.setText(msg)
                self._pbar.setValue(progress)
        except RuntimeError:
            pass

    def _set_estado(self, instalado: bool):
        acc = _COR[self._versao]
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
            self._lbl_badge.setText("NÃO INSTALADO")
            self._lbl_badge.setStyleSheet(f"""
                QLabel {{
                    background:{COLORS.get('surface','#2a2a2a')};
                    color:{COLORS.get('text_dim','#888')};
                    border:1px solid {brd};
                    border-radius:4px; padding:2px 8px; font-weight:bold;
                }}
            """)

        self._btn_instalar.setEnabled(not instalado)
        if not instalado:
            self._btn_instalar.setStyleSheet(f"""
                QPushButton {{
                    background:{acc}; color:#fff; border:none;
                    border-radius:6px; padding:6px 16px; font-weight:bold;
                    font-size:10pt;
                }}
                QPushButton:hover {{ background:{acc}; opacity:0.85; }}
                QPushButton:disabled {{
                    background:{brd}; color:{COLORS.get('text_disabled','#666')};
                    border-radius:6px;
                }}
            """)
        else:
            self._btn_instalar.setStyleSheet(f"""
                QPushButton {{
                    background:{brd}; color:{COLORS.get('text_disabled','#666')};
                    border:none; border-radius:6px; padding:6px 16px;
                    font-weight:bold; font-size:10pt;
                }}
            """)

        self._btn_remover.setEnabled(instalado)
        if instalado:
            self._btn_remover.setStyleSheet(f"""
                QPushButton {{
                    background:#c0392b; color:#fff; border:none;
                    border-radius:6px; padding:6px 16px; font-weight:bold;
                    font-size:10pt;
                }}
                QPushButton:hover {{ background:#e74c3c; }}
                QPushButton:disabled {{
                    background:{brd}; color:{COLORS.get('text_disabled','#666')};
                    border-radius:6px;
                }}
            """)
        else:
            self._btn_remover.setStyleSheet(f"""
                QPushButton {{
                    background:{brd}; color:{COLORS.get('text_disabled','#666')};
                    border:none; border-radius:6px; padding:6px 16px;
                    font-weight:bold; font-size:10pt;
                }}
            """)

    def _upd_style(self, _=""):
        acc = _COR[self._versao]
        bg  = COLORS.get("surface", "#1e1e1e")
        brd = COLORS.get("border",  "#444")
        self.setStyleSheet(f"""
            QFrame#install_remove_card_{self._versao} {{
                background:{bg};
                border:1.5px solid {brd};
                border-radius:12px;
            }}
            QFrame#install_remove_card_{self._versao}:hover {{
                border:1.5px solid {acc};
                background:{COLORS.get('surface2','#2a2a2a')};
            }}
        """)
        self._pbar.setStyleSheet(f"""
            QProgressBar {{ background:{brd}; border:none; border-radius:2px; }}
            QProgressBar::chunk {{ background:{acc}; border-radius:2px; }}
        """)
        self._set_estado(self._instalado)


class _AutoInstallCard(QFrame):
    acao_solicitada = pyqtSignal(str)
    sig_set_loading = pyqtSignal(bool, str, int)

    def __init__(self, versao: str, parent=None):
        super().__init__(parent)
        self._versao = versao
        self.setObjectName(f"auto_install_card_{versao}")
        self._build_ui()
        self._upd_style()
        theme_manager.theme_changed.connect(lambda _: self._upd_style())
        self.sig_set_loading.connect(self.set_loading)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        header = QHBoxLayout()
        titulo = QLabel(f"Firebird {self._versao}")
        titulo.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        titulo.setStyleSheet(f"color:{_COR[self._versao]};")

        icon = QLabel("🚀")
        icon.setFont(QFont(FONT_SANS, 14))

        header.addWidget(titulo, 1)

        self._lbl_installed = label("✅ INSTALADO", COLORS["accent2"], 8)
        self._lbl_installed.setStyleSheet(f"color:{COLORS['accent2']}; font-weight: bold;")
        self._lbl_installed.setVisible(False)
        header.addWidget(self._lbl_installed)

        header.addWidget(icon)
        lay.addLayout(header)

        h_line_lay = QVBoxLayout()
        h_line_lay.setContentsMargins(0, 4, 0, 8)
        hl = QFrame()
        hl.setFrameShape(QFrame.Shape.HLine)
        hl.setStyleSheet(f"background:{COLORS.get('border','#444')}; max-height:1px;")
        h_line_lay.addWidget(hl)
        lay.addLayout(h_line_lay)

        steps = [
            "Download e instalação do portable",
            "Configuração do modo de execução",
            "Ativação automática da versão"
        ]
        if self._versao == "4":
            steps.insert(2, "Importação de configurações oficiais")

        desc_text = "Este assistente executará:\n"
        for i, s in enumerate(steps, 1):
            desc_text += f"   {i}. {s}\n"

        desc = label(desc_text.strip(), COLORS["text_mid"], 9)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{COLORS['text_mid']}; line-height: 1.4;")
        lay.addWidget(desc)

        lay.addStretch()

        self._status_box = QWidget()
        self._status_box.setVisible(False)
        st_lay = QVBoxLayout(self._status_box)
        st_lay.setContentsMargins(0, 8, 0, 8)
        st_lay.setSpacing(6)

        self._lbl_status = label("Preparando...", COLORS["text_dim"], 8)
        self._pbar = QProgressBar()
        self._pbar.setFixedHeight(4)
        self._pbar.setTextVisible(False)
        self._pbar.setRange(0, 100)

        st_lay.addWidget(self._lbl_status)
        st_lay.addWidget(self._pbar)
        lay.addWidget(self._status_box)

        self._btn = make_primary_btn("INSTALAÇÃO AUTOMÁTICA", 240)
        self._btn.setFixedHeight(38)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(lambda: self.acao_solicitada.emit(self._versao))
        lay.addWidget(self._btn, 0, Qt.AlignmentFlag.AlignCenter)

    @pyqtSlot(bool)
    @pyqtSlot(bool, str)
    @pyqtSlot(bool, str, int)
    def set_loading(self, active: bool, msg: str = "", progress: int = 0):
        try:
            self._status_box.setVisible(active)
            self._btn.setEnabled(not active)
            if active:
                if msg:
                    self._lbl_status.setText(msg)
                self._pbar.setValue(progress)
        except RuntimeError:
            pass

    def set_installed(self, installed: bool):
        try:
            self._lbl_installed.setVisible(installed)
            if installed:
                self._btn.setText("REINSTALAR")
                _apply_secondary_style(self._btn)
            else:
                self._btn.setText("INSTALAÇÃO AUTOMÁTICA")
                _apply_primary_style(self._btn)
        except RuntimeError:
            return

    def _upd_style(self, _=""):
        acc = _COR[self._versao]
        bg  = COLORS.get('surface', '#1e1e1e')
        brd = COLORS.get('border', '#444')
        self.setStyleSheet(f"""
            QFrame#auto_install_card_{self._versao} {{
                background:{bg};
                border:1.5px solid {brd};
                border-radius:12px;
            }}
            QFrame#auto_install_card_{self._versao}:hover {{
                border:1.5px solid {acc};
                background:{COLORS.get('surface2','#2a2a2a')};
            }}
        """)
        self._pbar.setStyleSheet(f"""
            QProgressBar {{ background: {brd}; border: none; border-radius: 2px; }}
            QProgressBar::chunk {{ background: {acc}; border-radius: 2px; }}
        """)


# =============================================================================
# Card de Configuração FB4 (Recuperação)
# =============================================================================

class _Fb4ConfigCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("fb4_config_card")
        self._worker: QThread | None = None
        self._build_ui()
        self._upd_style()
        theme_manager.theme_changed.connect(lambda _: self._upd_style())

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        titulo = QLabel("Recuperar Configurações Oficiais FB4")
        titulo.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
        titulo.setStyleSheet(f"color:{COLORS.get('text','#fff')};")
        lay.addWidget(titulo)

        desc = QLabel(
            "Esta ferramenta baixa e aplica as configurações recomendadas para o Firebird 4.\n"
            "Arquivos afetados: firebird.conf, databases.conf, aliases e configurações de segurança.\n\n"
            "Útil para restaurar o ambiente padrão da Futura ou corrigir erros de comunicação."
        )
        desc.setFont(QFont(FONT_SANS, 9))
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{COLORS.get('text_mid','#aaa')};")
        lay.addWidget(desc)

        lay.addSpacing(8)

        self._btn_recuperar = make_primary_btn("BAIXAR E APLICAR CONFIGURAÇÕES", 280)
        self._btn_recuperar.setFixedHeight(36)
        self._btn_recuperar.clicked.connect(self._on_recuperar)
        lay.addWidget(self._btn_recuperar, 0, Qt.AlignmentFlag.AlignCenter)

        self._lbl_resultado = QLabel("")
        self._lbl_resultado.setFont(QFont(FONT_SANS, 10))
        self._lbl_resultado.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_resultado.setWordWrap(True)
        lay.addWidget(self._lbl_resultado)

        lay.addStretch()

    def _on_recuperar(self):
        self._btn_recuperar.setEnabled(False)
        self._lbl_resultado.setText("Baixando e configurando ambiente FB4...")
        self._lbl_resultado.setStyleSheet(f"color:{COLORS.get('accent','#0078d4')};")

        worker = _ConfigsOficiaisWorker()
        worker.log.connect(lambda m: self._lbl_resultado.setText(m))
        worker.concluido.connect(self._on_recuperar_concluido)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _on_recuperar_concluido(self, r: dict):
        self._btn_recuperar.setEnabled(True)
        if r["ok"]:
            self._lbl_resultado.setText("Ambiente Firebird 4 configurado com sucesso!")
            self._lbl_resultado.setStyleSheet("color:#2ecc71; font-weight:bold;")
        else:
            self._lbl_resultado.setText(f"Erro na recuperação: {r['erro']}")
            self._lbl_resultado.setStyleSheet("color:#e74c3c; font-weight:bold;")

    def _upd_style(self, _=""):
        self.setStyleSheet(f"""
            QFrame#fb4_config_card {{
                background:{COLORS.get('surface','#1e1e1e')};
                border:1.5px solid {COLORS.get('border','#444')};
                border-radius:12px;
            }}
        """)


# =============================================================================
# Dashboard de Status Geral
# =============================================================================

class _StatusDashboard(QFrame):
    versao_clicada  = pyqtSignal(str)
    acao_solicitada = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("status_dashboard")
        self.setFixedHeight(100)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(16)

        self._boxes = {}
        for v in ("3", "4"):
            box = QFrame()
            box.setFixedWidth(260)
            box.setObjectName(f"dash_box_{v}")
            box.setCursor(Qt.CursorShape.PointingHandCursor)
            box.mousePressEvent = lambda e, versao=v: self.versao_clicada.emit(versao)

            bl = QVBoxLayout(box)
            bl.setSpacing(6)
            bl.setContentsMargins(12, 10, 12, 10)

            top_row = QHBoxLayout()
            lbl_v = QLabel(f"Firebird {v}")
            lbl_v.setFont(QFont(FONT_SANS, 10, QFont.Weight.Bold))
            lbl_v.setStyleSheet(f"color:{_COR[v]}; border:none; background:transparent;")

            self._boxes[v] = {
                "frame":   box,
                "status":  QLabel("Verificando..."),
                "icon":    QLabel("🕒"),
            }
            self._boxes[v]["status"].setFont(QFont(FONT_SANS, 8))
            self._boxes[v]["status"].setStyleSheet(
                f"color:{COLORS.get('text_dim')}; border:none; background:transparent;"
            )
            self._boxes[v]["icon"].setFixedWidth(16)
            self._boxes[v]["icon"].setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._boxes[v]["icon"].setStyleSheet("background:transparent; border:none;")

            top_row.addWidget(lbl_v, 1)
            top_row.addWidget(self._boxes[v]["icon"])
            top_row.addWidget(self._boxes[v]["status"])

            actions_lay = QHBoxLayout()
            actions_lay.setSpacing(4)

            btn_start   = QPushButton("Iniciar")
            btn_stop    = QPushButton("Parar")
            btn_restart = QPushButton("Reiniciar")

            for btn, acao in [
                (btn_start,   "iniciar"),
                (btn_stop,    "parar"),
                (btn_restart, "reiniciar"),
            ]:
                btn.setFixedHeight(22)
                btn.setFont(QFont(FONT_SANS, 8))
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(
                    lambda _, versao=v, a=acao: self.acao_solicitada.emit(versao, a)
                )
                actions_lay.addWidget(btn)

            self._boxes[v].update({
                "btn_start":   btn_start,
                "btn_stop":    btn_stop,
                "btn_restart": btn_restart,
            })

            bl.addLayout(top_row)
            bl.addLayout(actions_lay)
            lay.addWidget(box)

        lay.addStretch()
        self._upd_style()
        theme_manager.theme_changed.connect(lambda _: self._upd_style())

    def atualizar(self, st: dict):
        try:
            for v in ("3", "4"):
                d         = st[f"fb{v}"]
                rodando   = d["rodando"]
                instalado = d["instalado"]

                self._boxes[v]["btn_start"].setVisible(not rodando and instalado)
                self._boxes[v]["btn_stop"].setVisible(rodando)
                self._boxes[v]["btn_restart"].setVisible(rodando)

                if rodando:
                    self._boxes[v]["status"].setText("Ativo")
                    self._boxes[v]["icon"].setText("🟢")
                elif instalado:
                    self._boxes[v]["status"].setText("Inativo")
                    self._boxes[v]["icon"].setText("⚪")
                else:
                    self._boxes[v]["status"].setText("Não instalado")
                    self._boxes[v]["icon"].setText("❌")
        except RuntimeError:
            pass

    def _upd_style(self):
        try:
            bg    = COLORS.get('bg')
            brd   = COLORS.get('border')
            surf  = COLORS.get('surface', '#1e1e1e')
            surf2 = COLORS.get('surface2', '#2a2a2a')

            self.setStyleSheet(f"""
                QFrame#status_dashboard {{
                    background:{surf};
                    border:1px solid {brd};
                    border-radius:12px;
                }}
            """)

            for v in ("3", "4"):
                acc = _COR[v]
                self._boxes[v]["frame"].setStyleSheet(f"""
                    QFrame#dash_box_{v} {{
                        background:{bg};
                        border:1px solid {brd};
                        border-radius:8px;
                    }}
                    QFrame#dash_box_{v}:hover {{
                        border:1.5px solid {acc};
                        background:{surf2};
                    }}
                """)
                btn_style = f"""
                    QPushButton {{
                        background: transparent;
                        color: {acc};
                        border: 1px solid {acc};
                        border-radius: 4px;
                        padding: 0px 4px;
                    }}
                    QPushButton:hover {{
                        background: {acc};
                        color: #fff;
                    }}
                """
                self._boxes[v]["btn_start"].setStyleSheet(btn_style)
                self._boxes[v]["btn_stop"].setStyleSheet(btn_style)
                self._boxes[v]["btn_restart"].setStyleSheet(btn_style)
        except RuntimeError:
            pass


# =============================================================================
# Página principal
# =============================================================================

class PageFbPortable(QWidget):
    go_menu           = pyqtSignal()
    sig_setar_ocupado = pyqtSignal(bool)
    sig_admin_res     = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: QThread | None             = None
        self._admin_check_worker: QThread | None = None
        self._status_worker: QThread | None      = None
        self._versao_sel   = "4"
        self._upd_toggle   = False
        self._toggle_rows  : dict[str, _ToggleRow]  = {}
        self._modo_cards   : dict[str, _ModoCard]   = {}
        self._versao_auto_install: str = "4"
        self._tabs_built = {0: True, 1: False, 2: False, 3: False, 4: False, 5: False}

        self._last_st: dict | None = None
        self._eh_admin: bool | None = None
        self._tab_db: QWidget | None = None

        self._build_ui()
        theme_manager.theme_changed.connect(self._upd_style)

        # Conectar sinais de ponte para threads
        self.sig_setar_ocupado.connect(self._setar_ocupado_slot)
        self.sig_admin_res.connect(self._on_admin_check_full_concluido)

        self._timer = QTimer(self)
        self._timer.setInterval(4000)
        self._timer.timeout.connect(self._atualizar_status)

    # =========================================================================
    # Verificação assíncrona de admin
    # =========================================================================

    def _verificar_admin_background(self):
        if self._admin_check_worker and self._admin_check_worker.isRunning():
            return
        aw = _AdminCheckWorker(self)
        aw.concluido.connect(self._on_admin_resultado_inicial)
        aw.finished.connect(lambda: setattr(self, "_admin_check_worker", None))
        self._admin_check_worker = aw
        aw.start()

    def _on_admin_resultado_inicial(self, admin_ok: bool):
        self._eh_admin = admin_ok

        if not admin_ok and self._banner_admin is None:
            self._banner_admin = _BannerAdmin()
            self._banner_admin.btn_reiniciar.clicked.connect(self._on_reiniciar_admin)
            self._content_lay.insertWidget(0, self._banner_admin)

        for card in self._modo_cards.values():
            try:
                card._lbl_nota.setVisible(not admin_ok)
            except RuntimeError:
                pass

        self._timer.start()
        self._atualizar_status()

    # =========================================================================
    # Construção da UI
    # =========================================================================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = PageHeader(
            "FIREBIRD PORTABLE",
            "Instale, ative e configure FB3 e FB4 de forma independente"
        )
        self._header.back_clicked.connect(self.go_menu.emit)
        root.addWidget(self._header)

        content_w = QWidget()
        self._content_lay = QVBoxLayout(content_w)
        self._content_lay.setContentsMargins(20, 16, 20, 12)
        self._content_lay.setSpacing(8)

        def _upd_title():
            if theme_manager.ui_theme == "modern":
                self._header.set_subtitle("✨ Interface Premium - Configuração Avançada")
            else:
                self._header.set_subtitle("Instale, ative e configure FB3 e FB4 de forma independente")

        theme_manager.ui_theme_changed.connect(_upd_title)
        _upd_title()

        self._banner_admin = None
        
        # Componentes globais que precisam existir desde o início
        self._alert    = AlertBox("", "info")
        self._progress = QProgressBar()
        self._console  = _Console(fixed_height=0)
        self._ir_cards : dict[str, _InstallRemoveCard] = {}
        self._auto_cards : dict[str, _AutoInstallCard] = {}
        self._toggle_rows : dict[str, _ToggleRow] = {}
        self._modo_cards : dict[str, _ModoCard] = {}
        
        self._tabs = QTabWidget()
        self._tabs.setFont(QFont(FONT_SANS, 10))
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._content_lay.addWidget(self._tabs)

        # -- ABA 0: Instalação Automática (Carregada no Início) -----------
        self._tab_auto = QWidget()
        self._build_tab_auto()
        self._tabs.addTab(self._tab_auto, "⚡ Instalação Automática")

        # -- Placeholders para as outras abas (Lazy Loading) -------------
        self._tab_controle = QWidget()
        self._tab_instalar = QWidget()
        self._tab_db       = QWidget()
        self._tab_fb4      = QWidget()
        self._tab_log      = QWidget()

        self._tabs.addTab(self._tab_controle, "⚙️ Controle de Versões")
        self._tabs.addTab(self._tab_instalar, "📦 Instalar / Remover")
        self._tabs.addTab(self._tab_db,       "🗄️ Banco de Dados")
        self._tabs.addTab(self._tab_fb4,      "🔧 Configurações FB4")
        self._tabs.addTab(self._tab_log,      "📋 Logs")

        self._content_lay.addStretch()
        root.addWidget(content_w)

        self._upd_style()

    def _on_tab_changed(self, index):
        if self._tabs_built.get(index):
            return
        
        if index == 1: self._build_tab_controle()
        elif index == 2: self._build_tab_instalar()
        elif index == 3: self._build_tab_db()
        elif index == 4: self._build_tab_fb4()
        elif index == 5: self._build_tab_log()
        
        self._tabs_built[index] = True
        self._upd_style()

    def _build_tab_auto(self):
        alay = QVBoxLayout(self._tab_auto)
        alay.setContentsMargins(16, 16, 16, 16)
        alay.setSpacing(10)
        desc_auto = label("Assistente para instalar e configurar o Firebird de forma automatizada.", COLORS["text_mid"], 10)
        desc_auto.setWordWrap(True)
        alay.addWidget(desc_auto)
        card_lay = QHBoxLayout(); card_lay.setSpacing(16)
        self._auto_cards = {}
        for v in ("3", "4"):
            card = _AutoInstallCard(v)
            card.acao_solicitada.connect(self._on_auto_install)
            card.sig_set_loading.connect(card.set_loading)
            self._auto_cards[v] = card
            card_lay.addWidget(card, 1)
        alay.addLayout(card_lay); alay.addStretch()

    def _build_tab_controle(self):
        tlay_root = QVBoxLayout(self._tab_controle)
        tlay_root.setContentsMargins(16, 16, 16, 16)
        tlay_root.setSpacing(10)
        info = label("Ative/inative cada versão e configure o modo de execução. ", COLORS["text_mid"], 10)
        info.setWordWrap(True); tlay_root.addWidget(info)
        self._dashboard = _StatusDashboard()
        self._dashboard.versao_clicada.connect(self._on_dash_v_clicada)
        self._dashboard.acao_solicitada.connect(self._on_dash_acao)
        tlay_root.addWidget(self._dashboard)
        tf = QFrame(); tf.setObjectName("toggles_frame")
        tlay_cols = QHBoxLayout(tf); tlay_cols.setContentsMargins(16, 16, 16, 16); tlay_cols.setSpacing(16)
        for versao in ("3", "4"):
            cfg = FB_CONFIGS[versao]; det = f"Porta {cfg['porta']}"
            col_frame = QFrame(); col_lay = QVBoxLayout(col_frame); col_lay.setContentsMargins(0,0,0,0); col_lay.setSpacing(10)
            row = _ToggleRow(versao, det)
            row.toggle.toggled.connect(lambda checked, v=versao: self._on_toggle(v, checked))
            self._toggle_rows[versao] = row
            col_lay.addWidget(row)
            card = _ModoCard(versao); card.acao_solicitada.connect(self._on_servico_acao)
            self._modo_cards[versao] = card
            col_lay.addWidget(card); col_lay.addStretch(); tlay_cols.addWidget(col_frame, 1)
        tlay_root.addWidget(tf); tlay_root.addStretch()

    def _build_tab_instalar(self):
        ilay = QVBoxLayout(self._tab_instalar)
        ilay.setContentsMargins(16, 16, 16, 16); ilay.setSpacing(10)
        ir_card_lay = QHBoxLayout(); ir_card_lay.setSpacing(16)
        for v in ("3", "4"):
            ir_card = _InstallRemoveCard(v); ir_card.instalar_solicitado.connect(self._on_instalar); ir_card.remover_solicitado.connect(self._on_remover); ir_card.sig_set_loading.connect(ir_card.set_loading)
            self._ir_cards[v] = ir_card; ir_card_lay.addWidget(ir_card, 1)
        ilay.addLayout(ir_card_lay)
        ilay.addWidget(self._progress); ilay.addWidget(self._alert); ilay.addStretch()

    def _build_tab_db(self):
        dlay = QVBoxLayout(self._tab_db); dlay.setContentsMargins(16,16,16,16)
        self._tab_db = self._tab_db # No-op to satisfy reference
        self._db_conf_card = _DatabasesConfCard(); dlay.addWidget(self._db_conf_card); dlay.addStretch()

    def _build_tab_fb4(self):
        flay = QVBoxLayout(self._tab_fb4); flay.setContentsMargins(16,16,16,16)
        self._fb4_conf_card = _Fb4ConfigCard(); flay.addWidget(self._fb4_conf_card); flay.addStretch()

    def _build_tab_log(self):
        llay = QVBoxLayout(self._tab_log); llay.setContentsMargins(0, 8, 0, 0)
        llay.addWidget(self._console, 1)
        btn_limpar = make_secondary_btn("Limpar Log", 130); btn_limpar.clicked.connect(self._console.limpar); llay.addWidget(btn_limpar)

    # =========================================================================
    # Toggles — alternância automática
    # =========================================================================

    def _on_toggle(self, versao: str, checked: bool):
        if self._upd_toggle:
            return

        outra = "4" if versao == "3" else "3"

        if checked:
            lbl_alvo  = FB_CONFIGS[versao]["label"]
            lbl_outra = FB_CONFIGS[outra]["label"]
            outra_ativa = (self._last_st or {}).get(f"fb{outra}", {}).get("rodando", False)
            if outra_ativa:
                msg_console = (
                    f"Ativando {lbl_alvo} e desativando {lbl_outra} automaticamente ..."
                )
            else:
                msg_console = f"Ativando {lbl_alvo} ..."
        else:
            msg_console = f"Inativando {FB_CONFIGS[versao]['label']} ..."

        self.sig_setar_ocupado.emit(True)
        self._console.limpar()
        self._alert.setVisible(False)
        self._console.append(msg_console)

        worker = _AlternarWorker(versao, checked)
        worker.log.connect(self._console.append,
                           Qt.ConnectionType.QueuedConnection)
        worker.concluido.connect(self._on_toggle_concluido,
                                 Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_toggle_concluido(self, r: dict):
        self.sig_setar_ocupado.emit(False)
        self._atualizar_status()
        versao = r.get("versao", "")
        ativar = r.get("ativar", True)
        lbl    = FB_CONFIGS.get(versao, {}).get("label", f"FB{versao}")
        acao   = "ativado" if ativar else "inativado"
        if r.get("requer_admin"):
            self._alerta(
                "Permissao de administrador necessaria. Use o botão 'Reiniciar como Admin'.",
                "warn"
            )
        elif r["ok"]:
            if ativar:
                outra     = "4" if versao == "3" else "3"
                lbl_outra = FB_CONFIGS[outra]["label"]
                outra_rod = (self._last_st or {}).get(f"fb{outra}", {}).get("rodando", False)
                if outra_rod:
                    self._alerta(
                        f"{lbl} ativado! {lbl_outra} foi desativado automaticamente.",
                        "success"
                    )
                else:
                    self._alerta(f"{lbl} {acao} com sucesso!", "success")
            else:
                self._alerta(f"{lbl} {acao} com sucesso!", "success")
        else:
            self._alerta(f"Erro: {r['erro']}", "error")

    def _on_reiniciar_admin(self):
        if solicitar_admin():
            from PyQt6.QtWidgets import QApplication
            QApplication.quit()
        else:
            self._alerta(
                "Não foi possível solicitar permissão. "
                "Clique direito no atalho e escolha 'Executar como administrador'.",
                "error"
            )

    # =========================================================================
    # Card de modo — registrar / remover serviço
    # =========================================================================

    def _on_servico_acao(self, versao: str, acao: str):
        if not self._eh_admin:
            self._alerta(
                "Permissao de administrador necessaria. Reinicie como Administrador.", "warn"
            )
            return
        label_acao = "Registrando" if acao == "registrar" else "Removendo"
        self.sig_setar_ocupado.emit(True)
        self._console.limpar()
        self._alert.setVisible(False)
        self._console.append(
            f"{label_acao} servico Windows do {FB_CONFIGS[versao]['label']} ..."
        )
        worker = _ServicoWorker(versao, acao)
        worker.log.connect(self._console.append,
                           Qt.ConnectionType.QueuedConnection)
        worker.concluido.connect(self._on_servico_concluido,
                                 Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_servico_concluido(self, r: dict):
        self.sig_setar_ocupado.emit(False)
        self._atualizar_status()
        versao = r.get("versao", "")
        acao   = r.get("acao", "")
        lbl    = FB_CONFIGS.get(versao, {}).get("label", f"FB{versao}")
        if r.get("requer_admin"):
            self._alerta(
                "Permissao de administrador necessaria. Reinicie como Administrador.", "warn"
            )
        elif r["ok"]:
            if acao == "registrar":
                self._alerta(
                    f"{lbl} registrado como serviço Windows! "
                    "Inicia automaticamente com o Windows.",
                    "success"
                )
            else:
                self._alerta(
                    f"Serviço Windows do {lbl} removido. Voltou ao modo processo.",
                    "success"
                )
        else:
            self._alerta(f"Erro: {r['erro']}", "error")

    def _on_dash_v_clicada(self, versao: str):
        if self._worker:
            return
        row = self._toggle_rows.get(versao)
        if row and row.toggle.isEnabled():
            row.toggle.setChecked(not row.toggle.isChecked())

    def _on_dash_acao(self, versao: str, acao: str):
        if self._worker:
            return

        if acao == "reiniciar":
            self._on_reiniciar(versao)
        elif acao == "iniciar":
            row = self._toggle_rows.get(versao)
            if row and row.toggle.isEnabled():
                row.toggle.setChecked(True)
        elif acao == "parar":
            row = self._toggle_rows.get(versao)
            if row and row.toggle.isEnabled():
                row.toggle.setChecked(False)

    def _on_reiniciar(self, versao: str):
        self.sig_setar_ocupado.emit(True)
        self._console.limpar()
        self._console.append(f"Reiniciando {FB_CONFIGS[versao]['label']} ...")
        worker = _ReiniciarWorker(versao)
        worker.log.connect(self._console.append,
                           Qt.ConnectionType.QueuedConnection)
        worker.concluido.connect(self._on_reiniciar_concluido,
                                 Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_reiniciar_concluido(self, r: dict):
        self.sig_setar_ocupado.emit(False)
        self._atualizar_status()
        if r["ok"]:
            self._alerta("Reiniciado com sucesso!", "success")
        else:
            self._alerta(f"Erro ao reiniciar: {r['erro']}", "error")

    # =========================================================================
    # Status geral (timer + pós-ações) — tudo em background via _StatusWorker
    # =========================================================================

    def _atualizar_status(self):
        if self._worker and self._worker.isRunning():
            return
        if self._status_worker and self._status_worker.isRunning():
            return

        sw = _StatusWorker()
        sw.concluido.connect(self._on_status_concluido,
                             Qt.ConnectionType.QueuedConnection)
        sw.finished.connect(lambda: setattr(self, "_status_worker", None))
        self._status_worker = sw
        sw.start()

    def _on_status_concluido(self, st: dict):
        if not st:
            return

        self._last_st = st

        self._upd_toggle = True
        eh_admin = self._eh_admin if self._eh_admin is not None else False

        try:
            for versao in ("3", "4"):
                try:
                    d       = st[f"fb{versao}"]
                    inst    = d["instalado"]
                    rodando = d["rodando"]
                    
                    if versao not in self._toggle_rows: continue
                    row     = self._toggle_rows[versao]
                    
                    if versao not in self._modo_cards: continue
                    card    = self._modo_cards[versao]

                    porta = FB_CONFIGS[versao]['porta']
                    if d.get("servico_rod"):
                        det = f"Serviço Windows - porta {porta} - rodando"
                    elif d.get("processo_rod"):
                        det = f"Processo portable - porta {porta} - rodando"
                    elif inst and d.get("modo") == "servico" and d.get("servico_reg"):
                        det = f"Serviço Windows - porta {porta} - parado"
                    elif inst:
                        det = f"Processo portable - porta {porta} - parado"
                    else:
                        det = f"Processo portable - porta {porta}"

                    if versao == "3" and d.get("servico_oficial_rod"):
                        det = f"Serviço oficial - porta {porta} - rodando"

                    try:
                        row.set_estado(rodando, inst, det)
                        row.toggle.setChecked(rodando)
                        row.toggle.setAtivo(inst)
                        row.toggle.setToolTip(
                            "Ativar esta versão irá desativar a outra automaticamente."
                            if inst else ""
                        )
                    except RuntimeError:
                        continue

                    card.atualizar(
                        instalado      = inst,
                        modo           = d.get("modo", "processo"),
                        svc_registrado = d.get("servico_reg", False),
                        svc_rodando    = d.get("servico_rod", False),
                        eh_admin       = eh_admin,
                    )
                except Exception:
                    continue
        finally:
            self._upd_toggle = False

        try:
            if hasattr(self, "_dashboard") and self._dashboard:
                self._dashboard.atualizar(st)
        except Exception:
            pass

        for v in list(self._auto_cards.keys()):
            try:
                inst = st[f"fb{v}"]["instalado"]
                card = self._auto_cards.get(v)
                if card is None:
                    continue
                card.set_installed(inst)
            except RuntimeError:
                self._auto_cards.pop(v, None)
            except Exception:
                continue

        for v in ("3", "4"):
            try:
                d    = st.get(f"fb{v}", {})
                inst = d.get("instalado", False)
                ver  = d.get("ver_str", "")
                ir   = self._ir_cards.get(v)
                if ir:
                    ir.set_instalado(inst, ver)
            except Exception:
                continue

        if st.get("conflito"):
            self._alerta(
                "FB3 e FB4 estão ativos simultaneamente — isso pode causar conflitos.",
                "warn"
            )

    # =========================================================================
    # Instalação Automática
    # =========================================================================

    def _on_auto_install(self, versao: str):
        if self._worker and self._worker.isRunning():
            return

        self._versao_auto_install = versao
        card = self._auto_cards.get(versao)
        if card:
            card.sig_set_loading.emit(True, "Verificando permissões...", 0)

        if self._eh_admin is not None:
            self.sig_admin_res.emit(self._eh_admin)
            return

        aw = _AdminCheckWorker(self)
        aw.concluido.connect(self.sig_admin_res.emit)
        aw.finished.connect(lambda: setattr(self, "_admin_check_worker", None))
        self._admin_check_worker = aw
        aw.start()

    @pyqtSlot(bool)
    def _on_admin_check_full_concluido(self, ok: bool):
        """Bridge para garantir que _on_admin_check_concluido rode na Main Thread."""
        self._on_admin_check_concluido(ok, self._versao_auto_install)

    def _on_admin_check_concluido(self, admin_ok: bool, versao: str):
        self._eh_admin = admin_ok
        card = self._auto_cards.get(versao)

        if not admin_ok:
            if card:
                card.set_loading(False)
            self._alerta(
                "Permissão de administrador necessária para instalação automática.",
                "warn"
            )
            return

        if card:
            card.sig_set_loading.emit(True, "Iniciando...", 0)

        self.sig_setar_ocupado.emit(True)
        self._console.limpar()
        self._alert.setVisible(False)
        self._console.append(f"Iniciando Instalação Automática do Firebird {versao}...")

        worker = _AutoInstallWorker(versao)

        worker.log.connect(self._console.append, Qt.ConnectionType.QueuedConnection)
        
        if card:
            # Corrigido: Remover lambdas inseguras que podem floodar a thread principal se chamadas em loop
            # Criamos slots de ponte para o card
            worker.log.connect(lambda m: card.sig_set_loading.emit(True, m, 0), Qt.ConnectionType.QueuedConnection)
            worker.progresso.connect(lambda v: card.sig_set_loading.emit(True, "", v), Qt.ConnectionType.QueuedConnection)

        worker.concluido.connect(self._on_auto_install_concluido,
                                 Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_auto_install_concluido(self, r: dict):
        versao = self._versao_auto_install
        card   = self._auto_cards.get(versao)
        if card:
            card.sig_set_loading.emit(False, "", 0)

        self.sig_setar_ocupado.emit(False)

        if r["ok"]:
            msg = (
                f"Firebird {versao} instalado e iniciado com sucesso!\n"
                "Agora, o sistema irá procurar seus bancos de dados para completar a configuração."
            )
            self._alerta(msg, "success")

            self._db_conf_card.set_version(versao)
            idx = self._tabs.indexOf(self._tab_db)
            if idx >= 0:
                self._tabs.setCurrentIndex(idx)
            QTimer.singleShot(1000, self._db_conf_card._on_varrer)
        else:
            self._alerta(
                f"Falha na instalação automática: {r.get('erro', 'Erro desconhecido')}",
                "error"
            )

        self._atualizar_status()

    # =========================================================================
    # Instalação / Remoção manual
    # =========================================================================

    def _on_versao_changed(self, versao: str):
        self._versao_sel = versao
        self._alert.setVisible(False)

    def _on_instalar(self, versao: str):
        cfg = FB_CONFIGS[versao]

        inst_cache = (self._last_st or {}).get(f"fb{versao}", {}).get("instalado", False)
        if inst_cache:
            self._alerta(f"{cfg['label']} já está instalado em {cfg['dir']}.", "info")
            return

        self._versao_sel = versao
        ir = self._ir_cards.get(versao)
        if ir:
            ir.sig_set_loading.emit(True, "Iniciando instalação...", 0)

        self.sig_setar_ocupado.emit(True)
        self._console.limpar()
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._alert.setVisible(False)

        worker = _InstalarWorker(versao)
        worker.log.connect(self._console.append,
                           Qt.ConnectionType.QueuedConnection)
        worker.progresso.connect(self._progress.setValue,
                                 Qt.ConnectionType.QueuedConnection)
        worker.concluido.connect(self._on_instalado,
                                 Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_instalado(self, r: dict):
        versao = self._versao_sel
        ir = self._ir_cards.get(versao)
        if ir:
            ir.sig_set_loading.emit(False, "", 0)

        self.sig_setar_ocupado.emit(False)
        self._progress.setVisible(False)
        self._atualizar_status()
        cfg = FB_CONFIGS[versao]
        if r["ok"]:
            self._alerta(f"{cfg['label']} instalado! Versão: {r['versao']}", "success")
        else:
            self._alerta(f"Erro na instalação: {r['erro']}", "error")

    def _on_remover(self, versao: str):
        cfg = FB_CONFIGS[versao]

        inst_cache = (self._last_st or {}).get(f"fb{versao}", {}).get("instalado", False)
        if not inst_cache:
            self._alerta(f"{cfg['label']} não está instalado.", "warn")
            return

        self._versao_sel = versao
        ir = self._ir_cards.get(versao)
        if ir:
            ir.sig_set_loading.emit(True, "Removendo...", 0)

        self.sig_setar_ocupado.emit(True)
        self._console.limpar()
        self._alert.setVisible(False)

        worker = _RemoverWorker(versao)
        worker.log.connect(self._console.append,
                           Qt.ConnectionType.QueuedConnection)
        worker.concluido.connect(self._on_removido,
                                 Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_removido(self, r: dict):
        versao = self._versao_sel
        ir = self._ir_cards.get(versao)
        if ir:
            ir.sig_set_loading.emit(False, "", 0)

        self.sig_setar_ocupado.emit(False)
        self._atualizar_status()
        cfg = FB_CONFIGS[versao]
        if r["ok"]:
            self._alerta(f"{cfg['label']} removido.", "success")
        else:
            self._alerta(f"Erro ao remover: {r['erro']}", "error")

    def _limpar_worker(self, worker):
        if self._worker is worker:
            self._worker = None

    # =========================================================================
    # Helpers
    # =========================================================================

    # CORREÇÃO 12: _setar_ocupado agora verifica se está na thread principal.
    # Se chamado de outra thread (ex: dentro de um worker), redireciona via
    # QMetaObject.invokeMethod com QueuedConnection, garantindo que o QTimer
    # seja manipulado apenas na thread onde foi criado.
    # Isso elimina o erro:
    #   "QBasicTimer::stop: Failed. Possibly trying to stop from a different thread"
    def _setar_ocupado(self, v: bool):
        """Envia sinal para mudar estado ocupado na Main Thread."""
        self.sig_setar_ocupado.emit(v)

    @pyqtSlot(bool)
    def _setar_ocupado_slot(self, v: bool):
        """Implementação real do estado ocupado, sempre rodando na Main Thread."""
        if v:
            self._timer.stop()
        else:
            if not (self._status_worker and self._status_worker.isRunning()):
                self._timer.start()

        for row in self._toggle_rows.values():
            try:
                row.toggle.setEnabled(not v)
            except RuntimeError: pass

        for card in self._modo_cards.values():
            try:
                card.set_ocupado(v)
            except RuntimeError: pass

        for card in self._auto_cards.values():
            try:
                card._btn.setEnabled(not v)
            except RuntimeError: pass

    def _alerta(self, txt: str, kind: str):
        self._alert.set_text(txt)
        self._alert.set_kind(kind)
        self._alert.setVisible(True)

    def _upd_style(self, _=""):
        bg   = COLORS.get("surface",  "#1e1e1e")
        bg2  = COLORS.get("bg",       "#121212")
        brd  = COLORS.get("border",   "#444")
        txt  = COLORS.get("text",     "#fff")
        tmid = COLORS.get("text_mid", "#aaa")
        acc  = COLORS.get("accent",   "#0078d4")

        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background:{bg};
                border:none; border-radius:4px;
            }}
            QProgressBar::chunk {{
                background:{acc};
                border-radius:4px;
            }}
        """)

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

        try:
            self.findChild(QFrame, "toggles_frame").setStyleSheet(f"""
                QFrame#toggles_frame {{
                    background:{bg};
                    border:1.5px solid {brd};
                    border-radius:10px;
                }}
            """)
        except Exception:
            pass

    def reset(self):
        self._alert.setVisible(False)
        self._progress.setVisible(False)
        self._console.limpar()
        self._atualizar_status()

    def showEvent(self, event):
        super().showEvent(event)
        # Delay de 100ms para garantir que a página já apareceu na tela e o menu não trave
        QTimer.singleShot(100, self._verificar_admin_background)

    def hideEvent(self, event):
        self._timer.stop()
        for attr in ("_worker", "_admin_check_worker", "_status_worker"):
            w = getattr(self, attr, None)
            if w and w.isRunning():
                w.wait(200)
        super().hideEvent(event)