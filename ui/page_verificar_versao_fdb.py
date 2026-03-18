# =============================================================================
# FUTURA SETUP — Página: Verificar Versão do Firebird (.fdb)
# Salvar em: ui/page_verificar_versao_fdb.py
# =============================================================================

from __future__ import annotations

import os

from PyQt6.QtCore    import Qt, pyqtSignal, QThread
from PyQt6.QtGui     import QFont, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QFileDialog, QLabel, QFrame,
    QScrollArea, QPushButton, QApplication,
)

from ui.theme         import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets       import (
    PageTitle, SectionHeader, AlertBox,
    make_primary_btn, make_secondary_btn, make_folder_btn,
    btn_row, spacer, h_line, label, BusyOverlay,
)
from core.firebird_version_check import verificar_versao_fdb


# =============================================================================
# Worker — roda em thread para não travar a UI (gfix pode demorar)
# =============================================================================

class _VerificarWorker(QThread):
    concluido = pyqtSignal(dict)
    erro      = pyqtSignal(str)

    def __init__(self, path: str, user: str, password: str):
        super().__init__()
        self._path     = path
        self._user     = user
        self._password = password

    def run(self):
        try:
            result = verificar_versao_fdb(
                self._path,
                user=self._user,
                password=self._password,
                rodar_gfix=True,
            )
            self.concluido.emit(result)
        except Exception as e:
            self.erro.emit(str(e))


# =============================================================================
# Campo .fdb com botão explorer
# =============================================================================

class _PathFieldDB(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._lbl  = QLabel("Caminho do arquivo de banco de dados (.fdb)")
        self._edit = QLineEdit()
        self._edit.setPlaceholderText(r"Ex: C:\FuturaDados\GOURMET.fdb")

        self._btn = make_folder_btn(self)
        self._btn.setToolTip("Selecionar arquivo .fdb")
        self._btn.clicked.connect(self._browse)

        row = QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(self._edit, 1)
        row.addWidget(self._btn)

        lay.addWidget(self._lbl)
        lay.addLayout(row)

        theme_manager.theme_changed.connect(self._upd)
        self._upd()

    def _upd(self, _mode: str = ""):
        self._lbl.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 10px; font-weight: 600;"
            f" font-family: {FONT_SANS};"
        )
        self._edit.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1.5px solid {COLORS['border']};
                border-radius: 5px;
                padding: 4px 12px;
                font-size: 11px;
            }}
            QLineEdit:focus {{ border-color: {COLORS['accent']}; }}
        """)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar banco de dados Firebird", "C:\\",
            "Banco Firebird (*.fdb *.gdb *.db);;Todos os arquivos (*.*)",
        )
        if path:
            self._edit.setText(os.path.normpath(path))

    @property
    def value(self) -> str:
        return self._edit.text().strip()

    @value.setter
    def value(self, v: str):
        self._edit.setText(v)


# =============================================================================
# Página principal
# =============================================================================

_DEFAULT_USER     = "SYSDBA"
_DEFAULT_PASSWORD = "sbofutura"


class PageVerificarVersaoFdb(QWidget):
    go_menu = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._worker: QThread | None = None
        self._build_ui()
        theme_manager.theme_changed.connect(self._upd_drop_style)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(24, 28, 24, 20)
        lay.setSpacing(10)

        lay.addWidget(PageTitle(
            "VERIFICAR VERSAO DO FIREBIRD",
            "Detecta a versao e valida a integridade de um arquivo .fdb"
        ))

        lay.addWidget(SectionHeader("Arquivo do banco de dados"))

        desc = label(
            "Selecione ou arraste um arquivo .fdb. Sera verificada a versao do Firebird "
            "e rodado o gfix -validate para checar a integridade real do banco.",
            COLORS["text_mid"], 11,
        )
        desc.setWordWrap(True)
        lay.addWidget(desc)
        lay.addWidget(spacer(h=4))

        self._fld_db = _PathFieldDB()
        lay.addWidget(self._fld_db)

        self._drop_area = _DropArea()
        self._drop_area.arquivo_solto.connect(self._on_arquivo_solto)
        lay.addWidget(self._drop_area)
        self._upd_drop_style()

        lay.addWidget(h_line())

        self._btn_verificar = make_primary_btn("VERIFICAR", 150)
        self._btn_verificar.clicked.connect(self._on_verificar)
        btn_voltar = make_secondary_btn("VOLTAR", 80)
        btn_voltar.clicked.connect(self.go_menu.emit)
        lay.addWidget(btn_row(self._btn_verificar, btn_voltar))

        lay.addWidget(spacer(h=6))

        self._alert = AlertBox("", "info")
        self._alert.setVisible(False)
        lay.addWidget(self._alert)

        self._card_result = _ResultCard()
        self._card_result.setVisible(False)
        lay.addWidget(self._card_result)

        lay.addStretch()

        scroll.setWidget(inner)
        root.addWidget(scroll)

        self._overlay = BusyOverlay(self)

    def _on_arquivo_solto(self, path: str):
        self._fld_db.value = path

    def _on_verificar(self):
        path = self._fld_db.value
        if not path:
            self._mostrar_alerta("Informe o caminho de um arquivo .fdb.", "warn")
            self._card_result.setVisible(False)
            return

        self._btn_verificar.setEnabled(False)
        self._card_result.setVisible(False)
        self._alert.setVisible(False)
        self._overlay.show_with("Validando banco com gfix... aguarde.")

        worker = _VerificarWorker(path, _DEFAULT_USER, _DEFAULT_PASSWORD)
        worker.concluido.connect(self._on_concluido)
        worker.erro.connect(self._on_erro)
        worker.finished.connect(lambda: self._limpar_worker(worker))
        self._worker = worker
        worker.start()

    def _on_concluido(self, result: dict):
        self._overlay.hide_spinner()
        self._btn_verificar.setEnabled(True)

        if not result["ok"]:
            self._mostrar_alerta(f"Erro: {result['erro']}", "error")
            return

        self._alert.setVisible(False)
        self._card_result.atualizar(result, self._fld_db.value)
        self._card_result.setVisible(True)

    def _on_erro(self, msg: str):
        self._overlay.hide_spinner()
        self._btn_verificar.setEnabled(True)
        self._mostrar_alerta(f"Erro: {msg}", "error")

    def _limpar_worker(self, worker):
        if self._worker is worker:
            self._worker = None

    def _mostrar_alerta(self, txt: str, kind: str):
        self._alert.set_text(txt)
        self._alert.set_kind(kind)
        self._alert.setVisible(True)

    def _upd_drop_style(self, _mode: str = ""):
        self._drop_area.atualizar_estilo()

    def reset(self):
        self._fld_db.value = ""
        self._alert.setVisible(False)
        self._card_result.setVisible(False)
        self._btn_verificar.setEnabled(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            self._on_arquivo_solto(urls[0].toLocalFile())


# =============================================================================
# Widgets auxiliares
# =============================================================================

class _DropArea(QFrame):
    arquivo_solto = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl = QLabel("Arraste um arquivo .fdb aqui")
        self._lbl.setFont(QFont(FONT_SANS, 11))
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._lbl)
        self.atualizar_estilo()

    def atualizar_estilo(self):
        self._lbl.setStyleSheet(
            f"color: {COLORS.get('text_dim','#888')}; background: transparent; border: none;"
        )
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px dashed {COLORS.get('border','#444')};
                border-radius: 8px;
                background: {COLORS.get('surface','#1e1e1e')};
            }}
        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            self.setStyleSheet(f"""
                QFrame {{
                    border: 2px dashed {COLORS.get('accent','#0078d4')};
                    border-radius: 8px;
                    background: {COLORS.get('accent_dim','#1a3a5c')};
                }}
            """)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.atualizar_estilo()

    def dropEvent(self, event: QDropEvent):
        self.atualizar_estilo()
        urls = event.mimeData().urls()
        if urls:
            self.arquivo_solto.emit(urls[0].toLocalFile())


def _divider() -> QFrame:
    d = QFrame()
    d.setFrameShape(QFrame.Shape.HLine)
    d.setFixedHeight(1)
    d.setStyleSheet(f"background: {COLORS.get('border','#444')}; border: none;")
    return d


def _copy_field(value: str) -> QWidget:
    """
    Campo somente-leitura com botão copiar ao lado.
    Permite selecionar e copiar o valor facilmente.
    """
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)

    edit = QLineEdit(value)
    edit.setReadOnly(True)
    edit.setFont(QFont(FONT_MONO, 11, QFont.Weight.Bold))
    edit.setFixedHeight(30)
    edit.setStyleSheet(f"""
        QLineEdit {{
            background: {COLORS.get('bg', '#0a0e1a')};
            color: {COLORS.get('accent', '#00c2ff')};
            border: 1px solid {COLORS.get('border', '#1e2d45')};
            border-radius: 4px;
            padding: 0 8px;
            selection-background-color: {COLORS.get('accent', '#00c2ff')};
            selection-color: #000;
        }}
    """)

    btn = QPushButton("Copiar")
    btn.setFixedHeight(30)
    btn.setFixedWidth(60)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFont(QFont(FONT_SANS, 9))
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {COLORS.get('surface2', '#1a2235')};
            color: {COLORS.get('text_mid', '#aaa')};
            border: 1px solid {COLORS.get('border', '#1e2d45')};
            border-radius: 4px;
        }}
        QPushButton:hover {{
            background: {COLORS.get('accent_dim', '#1a3a5c')};
            color: {COLORS.get('accent', '#00c2ff')};
            border-color: {COLORS.get('accent', '#00c2ff')};
        }}
    """)

    def _copiar():
        QApplication.clipboard().setText(value)
        btn.setText("Copiado!")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: btn.setText("Copiar"))

    btn.clicked.connect(_copiar)

    row.addWidget(edit, 1)
    row.addWidget(btn)
    return container


class _ResultCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("result_card")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(6)

        # -- Versão Futura (Sistema) ----------------------------------------
        lay.addWidget(self._sec("Versao do Sistema Futura"))
        self._lbl_versao_futura = QLabel("")
        self._lbl_versao_futura.setFont(QFont(FONT_SANS, 18, QFont.Weight.Bold))
        lay.addWidget(self._lbl_versao_futura)

        # BUILD_BD — QLineEdit readonly (selecionável + copiável com teclado)
        row_build = QHBoxLayout()
        row_build.setSpacing(8)
        row_build.addWidget(self._mid("BUILD_BD:"))
        self._edit_build_bd = QLineEdit("")
        self._edit_build_bd.setReadOnly(True)
        self._edit_build_bd.setFixedHeight(28)
        self._edit_build_bd.setFixedWidth(100)
        self._edit_build_bd.setFont(QFont(FONT_MONO, 11, QFont.Weight.Bold))
        row_build.addWidget(self._edit_build_bd)
        row_build.addStretch()
        lay.addLayout(row_build)

        # Status estimado/confirmado
        self._lbl_futura_status = QLabel("")
        self._lbl_futura_status.setFont(QFont(FONT_SANS, 9))
        lay.addWidget(self._lbl_futura_status)

        # Erro de consulta (se houver)
        self._lbl_futura_erro = QLabel("")
        self._lbl_futura_erro.setFont(QFont(FONT_MONO, 9))
        self._lbl_futura_erro.setWordWrap(True)
        lay.addWidget(self._lbl_futura_erro)

        lay.addSpacing(6)
        lay.addWidget(_divider())
        lay.addSpacing(2)

        # -- Versão do arquivo Firebird -------------------------------------
        lay.addWidget(self._sec("Versao que criou o arquivo"))
        self._lbl_versao_arquivo = QLabel("")
        self._lbl_versao_arquivo.setFont(QFont(FONT_SANS, 15, QFont.Weight.Bold))
        lay.addWidget(self._lbl_versao_arquivo)

        row_info = QHBoxLayout()
        row_info.setSpacing(16)
        row_info.addWidget(self._mid("ODS:"))
        self._lbl_ods = QLabel("")
        self._lbl_ods.setFont(QFont(FONT_MONO, 10))
        row_info.addWidget(self._lbl_ods)
        row_info.addSpacing(12)
        row_info.addWidget(self._mid("Page size:"))
        self._lbl_page = QLabel("")
        self._lbl_page.setFont(QFont(FONT_MONO, 10))
        row_info.addWidget(self._lbl_page)
        row_info.addStretch()
        lay.addLayout(row_info)

        lay.addSpacing(6)
        lay.addWidget(_divider())
        lay.addSpacing(2)

        # -- Versão instalada -----------------------------------------------
        lay.addWidget(self._sec("Firebird instalado na maquina"))
        self._lbl_versao_instalada = QLabel("")
        self._lbl_versao_instalada.setFont(QFont(FONT_SANS, 15, QFont.Weight.Bold))
        lay.addWidget(self._lbl_versao_instalada)

        lay.addSpacing(6)
        lay.addWidget(_divider())
        lay.addSpacing(2)

        # -- Integridade (header) -------------------------------------------
        lay.addWidget(self._sec("Verificacao do cabecalho"))
        self._lbl_header = QLabel("")
        self._lbl_header.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
        lay.addWidget(self._lbl_header)
        self._header_det_lay = QVBoxLayout()
        self._header_det_lay.setSpacing(2)
        lay.addLayout(self._header_det_lay)

        lay.addSpacing(6)
        lay.addWidget(_divider())
        lay.addSpacing(2)

        # -- Integridade (gfix) ---------------------------------------------
        lay.addWidget(self._sec("Validacao gfix (integridade real do banco)"))
        self._lbl_gfix = QLabel("")
        self._lbl_gfix.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
        lay.addWidget(self._lbl_gfix)
        self._gfix_det_lay = QVBoxLayout()
        self._gfix_det_lay.setSpacing(2)
        lay.addLayout(self._gfix_det_lay)

        lay.addSpacing(6)
        lay.addWidget(_divider())
        lay.addSpacing(2)

        # -- Botões de cópia rápida ----------------------------------------
        lay.addSpacing(4)
        self._btn_copiar_build = self._make_copy_btn("Copiar BUILD")
        self._btn_copiar_tudo  = self._make_copy_btn("Copiar Tudo")
        self._btn_copiar_build.setFixedWidth(90)
        self._btn_copiar_tudo.setFixedWidth(90)
        self._btn_copiar_build.clicked.connect(self._copiar_build)
        self._btn_copiar_tudo.clicked.connect(self._copiar_tudo)

        row_copy = QHBoxLayout()
        row_copy.setSpacing(8)
        row_copy.addWidget(self._btn_copiar_build)
        row_copy.addWidget(self._btn_copiar_tudo)
        row_copy.addStretch()
        lay.addLayout(row_copy)

        # -- Caminho --------------------------------------------------------
        lay.addSpacing(4)
        self._lbl_arquivo = QLabel("")
        self._lbl_arquivo.setFont(QFont(FONT_MONO, 8))
        self._lbl_arquivo.setWordWrap(True)
        lay.addWidget(self._lbl_arquivo)

        self._result_cache: dict = {}
        self._atualizar_estilo()

    def _sec(self, txt: str) -> QLabel:
        lbl = QLabel(txt)
        lbl.setFont(QFont(FONT_SANS, 9))
        lbl.setStyleSheet(
            f"color: {COLORS.get('text_dim','#888')}; background: transparent; border: none;"
        )
        return lbl

    def _mid(self, txt: str) -> QLabel:
        lbl = QLabel(txt)
        lbl.setFont(QFont(FONT_SANS, 10))
        lbl.setStyleSheet(
            f"color: {COLORS.get('text_mid','#aaa')}; background: transparent; border: none;"
        )
        return lbl

    def _make_copy_btn(self, txt: str) -> QPushButton:
        btn = QPushButton(txt)
        btn.setFixedHeight(28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFont(QFont(FONT_SANS, 9))
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS.get('surface2','#1a2235')};
                color: {COLORS.get('text_mid','#aaa')};
                border: 1px solid {COLORS.get('border','#1e2d45')};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {COLORS.get('accent_dim','#1a3a5c')};
                color: {COLORS.get('accent','#00c2ff')};
                border-color: {COLORS.get('accent','#00c2ff')};
            }}
        """)
        return btn

    def _feedback_btn(self, btn: QPushButton, original: str):
        btn.setText("OK!")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: btn.setText(original))

    def _copiar_build(self):
        build = self._edit_build_bd.text().strip()
        if build:
            QApplication.clipboard().setText(build)
            self._feedback_btn(self._btn_copiar_build, "Copiar BUILD")

    def _copiar_tudo(self):
        r = self._result_cache
        if not r:
            return

        build_bd      = r.get("build_bd", 0)
        versao_futura = r.get("versao_futura", "N/A")
        est           = "estimado" if r.get("versao_futura_est") else "confirmado"
        versao_arq    = r.get("versao_arquivo", "N/A")
        ods           = f"{r.get('ods_major',0)}.{r.get('ods_minor',0)}"
        pg            = r.get("page_size", 0)
        versao_inst   = r.get("versao_instalada", "N/A")
        header_ok     = "OK" if r.get("header_ok") else "COM PROBLEMAS"
        gfix_ok       = "OK" if r.get("gfix_ok") else "COM ERROS" if r.get("gfix_executado") else "NAO EXECUTADO"
        arquivo       = self._lbl_arquivo.text()

        linhas = [
            "=== FUTURA SETUP — Verificacao de Versao ===",
            f"Arquivo        : {arquivo}",
            "",
            f"[Sistema Futura]",
            f"BUILD_BD       : {build_bd}",
            f"Versao Futura  : {versao_futura} ({est})",
            "",
            f"[Firebird]",
            f"Versao arquivo : {versao_arq}",
            f"ODS            : {ods}",
            f"Page size      : {pg} bytes",
            f"Instalado      : {versao_inst}",
            "",
            f"[Integridade]",
            f"Cabecalho      : {header_ok}",
            f"gfix validate  : {gfix_ok}",
        ]

        for e in r.get("header_erros", []):
            linhas.append(f"  ERRO header  : {e}")
        for e in r.get("gfix_erros", []):
            linhas.append(f"  ERRO gfix    : {e}")
        for a in r.get("gfix_avisos", []):
            linhas.append(f"  AVISO gfix   : {a}")

        QApplication.clipboard().setText("\n".join(linhas))
        self._feedback_btn(self._btn_copiar_tudo, "Copiar Tudo")

    def atualizar(self, result: dict, path: str):
        self._result_cache = result

        # -- Versão Futura ---------------------------------------------------
        build_bd      = result.get("build_bd", 0)
        versao_futura = result.get("versao_futura", "")
        est           = result.get("versao_futura_est", False)
        futura_erro   = result.get("versao_futura_erro", "")

        if versao_futura:
            self._lbl_versao_futura.setText(versao_futura)
            self._lbl_versao_futura.setStyleSheet(
                f"color: {COLORS.get('accent','#00c2ff')}; background: transparent; border: none;"
            )
            status_txt = "* Versao estimada por interpolacao" if est else "v Versao confirmada"
            status_cor = COLORS.get("warn", "#f39c12") if est else COLORS.get("accent2", "#2ecc71")
            self._lbl_futura_status.setText(status_txt)
            self._lbl_futura_status.setStyleSheet(
                f"color: {status_cor}; background: transparent; border: none;"
            )
        else:
            self._lbl_versao_futura.setText("Nao identificado")
            self._lbl_versao_futura.setStyleSheet(
                f"color: {COLORS.get('text_dim','#888')}; background: transparent; border: none;"
            )
            self._lbl_futura_status.setText("")

        # BUILD_BD
        self._edit_build_bd.setText(str(build_bd) if build_bd else "Nao disponivel")

        # Erro de consulta ao banco
        if futura_erro:
            self._lbl_futura_erro.setText(f"! {futura_erro}")
            self._lbl_futura_erro.setStyleSheet(
                f"color: {COLORS.get('warn','#f39c12')}; background: transparent; border: none;"
            )
        else:
            self._lbl_futura_erro.setText("")

        # -- Versão arquivo Firebird ----------------------------------------
        self._lbl_versao_arquivo.setText(result["versao_arquivo"])
        self._lbl_ods.setText(f"{result['ods_major']}.{result['ods_minor']}")
        pg = result["page_size"]
        self._lbl_page.setText(
            f"{pg} bytes  ({pg // 1024} KB)" if pg >= 1024 else f"{pg} bytes"
        )

        # -- Versão instalada -----------------------------------------------
        self._lbl_versao_instalada.setText(result["versao_instalada"])

        # -- Header ---------------------------------------------------------
        self._limpar(self._header_det_lay)
        if result["header_ok"]:
            self._lbl_header.setText("Cabecalho OK")
            self._lbl_header.setStyleSheet(
                f"color: {COLORS.get('accent2','#2ecc71')}; background: transparent; border: none;"
            )
        else:
            self._lbl_header.setText("Cabecalho com problemas")
            self._lbl_header.setStyleSheet(
                f"color: {COLORS.get('danger','#e74c3c')}; background: transparent; border: none;"
            )
        for e in result["header_erros"]:
            self._add(self._header_det_lay, f"  X  {e}", COLORS.get("danger", "#e74c3c"))
        for d in result["header_detalhes"]:
            self._add(self._header_det_lay, f"  v  {d}", COLORS.get("text_dim", "#888"))

        # -- gfix -----------------------------------------------------------
        self._limpar(self._gfix_det_lay)
        if not result["gfix_executado"]:
            msg = result["gfix_msg"] or "gfix nao executado."
            self._lbl_gfix.setText("Nao validado pelo gfix")
            self._lbl_gfix.setStyleSheet(
                f"color: {COLORS.get('warn','#f39c12')}; background: transparent; border: none;"
            )
            self._add(self._gfix_det_lay, f"  !  {msg}", COLORS.get("warn", "#f39c12"))
        elif result["gfix_ok"] and not result["gfix_avisos"]:
            self._lbl_gfix.setText("Banco integro (sem erros)")
            self._lbl_gfix.setStyleSheet(
                f"color: {COLORS.get('accent2','#2ecc71')}; background: transparent; border: none;"
            )
            self._add(self._gfix_det_lay, "  v  gfix -validate -full concluido sem erros",
                      COLORS.get("text_dim", "#888"))
        else:
            total = len(result["gfix_erros"])
            self._lbl_gfix.setText(
                f"Corrupcao detectada ({total} erro(s))" if total
                else "Validacao com avisos"
            )
            cor = COLORS.get("danger", "#e74c3c") if total else COLORS.get("warn", "#f39c12")
            self._lbl_gfix.setStyleSheet(
                f"color: {cor}; background: transparent; border: none;"
            )
            for e in result["gfix_erros"]:
                self._add(self._gfix_det_lay, f"  X  {e}", COLORS.get("danger", "#e74c3c"))
            for a in result["gfix_avisos"]:
                self._add(self._gfix_det_lay, f"  !  {a}", COLORS.get("warn", "#f39c12"))

        self._lbl_arquivo.setText(path)
        self._atualizar_estilo()

    def _limpar(self, layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add(self, layout: QVBoxLayout, txt: str, cor: str):
        lbl = QLabel(txt)
        lbl.setFont(QFont(FONT_MONO, 9))
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {cor}; background: transparent; border: none;")
        layout.addWidget(lbl)

    def _atualizar_estilo(self):
        accent2 = COLORS.get("accent2",  "#2ecc71")
        bg      = COLORS.get("surface",  "#1e1e1e")
        border  = COLORS.get("accent",   "#0078d4")
        mid     = COLORS.get("text_mid", "#aaa")
        dim     = COLORS.get("text_dim", "#888")

        self._edit_build_bd.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS.get('bg','#0a0e1a')};
                color: {COLORS.get('accent','#00c2ff')};
                border: 1px solid {COLORS.get('border','#1e2d45')};
                border-radius: 4px;
                padding: 0 8px;
                selection-background-color: {COLORS.get('accent','#00c2ff')};
                selection-color: #000;
            }}
        """)

        self._lbl_versao_arquivo.setStyleSheet(
            f"color: {COLORS.get('accent','#00c2ff')}; background: transparent; border: none;"
        )
        self._lbl_versao_instalada.setStyleSheet(
            f"color: {accent2}; background: transparent; border: none;"
        )
        self._lbl_ods.setStyleSheet(
            f"color: {mid}; background: transparent; border: none;"
        )
        self._lbl_page.setStyleSheet(
            f"color: {mid}; background: transparent; border: none;"
        )
        self._lbl_arquivo.setStyleSheet(
            f"color: {dim}; background: transparent; border: none;"
        )
        self.setStyleSheet(f"""
            QFrame#result_card {{
                background: {bg};
                border: 2px solid {border};
                border-radius: 10px;
            }}
            QLabel {{ background: transparent; border: none; }}
        """)