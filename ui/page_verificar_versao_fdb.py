# =============================================================================
# FUTURA SETUP — Página: Verificar Versão do Firebird (.fdb)
# Apenas UI — lógica em core/firebird_version_check.py
# Salvar em: ui/page_verificar_versao_fdb.py
# =============================================================================

from __future__ import annotations

import os

from PyQt6.QtCore    import Qt, pyqtSignal
from PyQt6.QtGui     import QFont, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QFileDialog, QLabel, QFrame,
)

from ui.theme         import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets       import (
    PageTitle, SectionHeader, AlertBox,
    make_primary_btn, make_secondary_btn, make_folder_btn,
    btn_row, spacer, h_line, label,
)
from core.firebird_version_check import verificar_versao_fdb


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
            self,
            "Selecionar banco de dados Firebird",
            "C:\\",
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

class PageVerificarVersaoFdb(QWidget):
    go_menu = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._build_ui()
        theme_manager.theme_changed.connect(self._upd_drop_style)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 20)
        root.setSpacing(10)

        root.addWidget(PageTitle(
            "VERIFICAR VERSÃO DO FIREBIRD",
            "Detecta a versão do Firebird a partir de um arquivo .fdb"
        ))

        root.addWidget(SectionHeader("Arquivo do banco de dados"))

        desc = label(
            "Selecione ou arraste um arquivo .fdb para identificar "
            "a versão do Firebird em que foi criado e a versão instalada na máquina.",
            COLORS["text_mid"], 11,
        )
        desc.setWordWrap(True)
        root.addWidget(desc)
        root.addWidget(spacer(h=4))

        self._fld_db = _PathFieldDB()
        root.addWidget(self._fld_db)

        self._drop_area = _DropArea()
        self._drop_area.arquivo_solto.connect(self._on_arquivo_solto)
        root.addWidget(self._drop_area)
        self._upd_drop_style()

        root.addWidget(h_line())

        btn_verificar = make_primary_btn("🔍  VERIFICAR VERSÃO", 200)
        btn_verificar.clicked.connect(self._on_verificar)
        btn_voltar = make_secondary_btn("← VOLTAR", 80)
        btn_voltar.clicked.connect(self.go_menu.emit)
        root.addWidget(btn_row(btn_verificar, btn_voltar))

        root.addWidget(spacer(h=6))

        self._alert = AlertBox("", "info")
        self._alert.setVisible(False)
        root.addWidget(self._alert)

        self._card_result = _ResultCard()
        self._card_result.setVisible(False)
        root.addWidget(self._card_result)

        root.addStretch()

    def _on_arquivo_solto(self, path: str):
        self._fld_db.value = path
        self._on_verificar()

    def _on_verificar(self):
        path = self._fld_db.value
        if not path:
            self._mostrar_alerta("Informe o caminho de um arquivo .fdb.", "warn")
            self._card_result.setVisible(False)
            return

        result = verificar_versao_fdb(path)

        if not result["ok"]:
            self._mostrar_alerta(f"✕  {result['erro']}", "error")
            self._card_result.setVisible(False)
            return

        self._alert.setVisible(False)
        self._card_result.atualizar(result, path)
        self._card_result.setVisible(True)

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
        self.setFixedHeight(72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._lbl = QLabel("Arraste um arquivo .fdb aqui")
        self._lbl.setFont(QFont(FONT_SANS, 11))
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._lbl)

        self.atualizar_estilo()

    def atualizar_estilo(self):
        border = COLORS.get("border", "#444")
        text   = COLORS.get("text_dim", "#888")
        bg     = COLORS.get("surface", "#1e1e1e")
        self._lbl.setStyleSheet(f"color: {text}; background: transparent; border: none;")
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px dashed {border};
                border-radius: 10px;
                background: {bg};
            }}
        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            accent = COLORS.get("accent", "#0078d4")
            bg     = COLORS.get("accent_dim", "#1a3a5c")
            self.setStyleSheet(f"""
                QFrame {{
                    border: 2px dashed {accent};
                    border-radius: 10px;
                    background: {bg};
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


class _ResultCard(QFrame):
    """Card com versão do arquivo e versão instalada na máquina."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("result_card")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        # ── Versão do arquivo ─────────────────────────────────────────────
        lbl_sec_arquivo = label("Versão que criou o arquivo", COLORS["text_dim"], 10)
        lay.addWidget(lbl_sec_arquivo)

        self._lbl_versao_arquivo = QLabel("")
        self._lbl_versao_arquivo.setFont(QFont(FONT_SANS, 17, QFont.Weight.Bold))
        lay.addWidget(self._lbl_versao_arquivo)

        row_ods = QHBoxLayout()
        row_ods.setSpacing(6)
        row_ods.addWidget(label("ODS:", COLORS["text_mid"], 11))
        self._lbl_ods = QLabel("")
        self._lbl_ods.setFont(QFont(FONT_MONO, 11))
        row_ods.addWidget(self._lbl_ods)
        row_ods.addStretch()
        lay.addLayout(row_ods)

        row_pg = QHBoxLayout()
        row_pg.setSpacing(6)
        row_pg.addWidget(label("Page size:", COLORS["text_mid"], 11))
        self._lbl_page = QLabel("")
        self._lbl_page.setFont(QFont(FONT_MONO, 11))
        row_pg.addWidget(self._lbl_page)
        row_pg.addStretch()
        lay.addLayout(row_pg)

        # Divisor
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1)
        lay.addWidget(div)
        self._div = div

        # ── Versão instalada na máquina ───────────────────────────────────
        lbl_sec_instalada = label("Firebird instalado na máquina", COLORS["text_dim"], 10)
        lay.addWidget(lbl_sec_instalada)

        self._lbl_versao_instalada = QLabel("")
        self._lbl_versao_instalada.setFont(QFont(FONT_SANS, 17, QFont.Weight.Bold))
        lay.addWidget(self._lbl_versao_instalada)

        # Arquivo
        self._lbl_arquivo = QLabel("")
        self._lbl_arquivo.setFont(QFont(FONT_MONO, 9))
        self._lbl_arquivo.setWordWrap(True)
        lay.addWidget(self._lbl_arquivo)

        self._lbl_sec_arquivo   = lbl_sec_arquivo
        self._lbl_sec_instalada = lbl_sec_instalada

        self._atualizar_estilo()

    def atualizar(self, result: dict, path: str):
        self._lbl_versao_arquivo.setText(result["versao_arquivo"])
        self._lbl_ods.setText(f"{result['ods_major']}.{result['ods_minor']}")
        pg = result["page_size"]
        self._lbl_page.setText(f"{pg} bytes ({pg // 1024} KB)" if pg >= 1024 else f"{pg} bytes")
        self._lbl_versao_instalada.setText(result["versao_instalada"])
        self._lbl_arquivo.setText(path)
        self._atualizar_estilo()

    def _atualizar_estilo(self):
        accent  = COLORS.get("accent",   "#0078d4")
        accent2 = COLORS.get("accent2",  "#2ecc71")
        bg      = COLORS.get("surface",  "#1e1e1e")
        border  = COLORS.get("accent",   "#0078d4")
        dim     = COLORS.get("text_dim", "#888")
        mid     = COLORS.get("text_mid", "#aaa")

        self._lbl_versao_arquivo.setStyleSheet(
            f"color: {accent}; background: transparent; border: none;"
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
        self._lbl_sec_arquivo.setStyleSheet(
            f"color: {dim}; background: transparent; border: none;"
        )
        self._lbl_sec_instalada.setStyleSheet(
            f"color: {dim}; background: transparent; border: none;"
        )
        self._div.setStyleSheet(f"background: {COLORS.get('border', '#444')}; border: none;")
        self.setStyleSheet(f"""
            QFrame#result_card {{
                background: {bg};
                border: 2px solid {border};
                border-radius: 10px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)