# =============================================================================
# FUTURA SETUP — UI Components: Database Related
# =============================================================================

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QFileDialog, QApplication, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent

from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.components.base import h_line, spacer, label
from ui.components.buttons import make_folder_btn, make_secondary_btn

class DatabasePathField(QWidget):
    def __init__(self, label_text: str = "Caminho do Banco de Dados", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        
        self.lbl = label(label_text, COLORS["text"], 10, bold=True)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(r"Ex: C:\FuturaDados\DADOS.fdb")
        
        self.btn = make_folder_btn(self)
        self.btn.clicked.connect(self._browse)
        
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.edit, 1)
        row.addWidget(self.btn)
        
        lay.addWidget(self.lbl)
        lay.addLayout(row)
        
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode=""):
        self.edit.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['surface']}; color: {COLORS['text']};
                border: 1.5px solid {COLORS['border']}; border-radius: 6px;
                padding: 6px 14px; font-size: 11px;
            }}
            QLineEdit:focus {{ border-color: {COLORS['accent']}; }}
        """)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Banco de Dados", "C:\\",
            "Firebird (*.fdb *.gdb);;Todos (*.*)"
        )
        if path: self.edit.setText(path.replace("/", "\\"))

    @property
    def value(self) -> str: return self.edit.text().strip()
    @value.setter
    def value(self, v: str): self.edit.setText(v)

class DatabaseDropArea(QFrame):
    arquivo_solto = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        lay = QHBoxLayout(self)
        self.lbl = label("Arraste o arquivo .fdb aqui", COLORS["text_dim"], 11)
        lay.addWidget(self.lbl, 0, Qt.AlignmentFlag.AlignCenter)
        
        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode=""):
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px dashed {COLORS['border']};
                border-radius: 12px;
                background: {COLORS['surface']};
            }}
        """)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            self.setStyleSheet(f"QFrame {{ border-color: {COLORS['accent']}; background: {COLORS['accent_dim']}; border-radius: 12px; border: 2px dashed; }}")
            e.acceptProposedAction()

    def dragLeaveEvent(self, e): self._upd()
    def dropEvent(self, e: QDropEvent):
        self._upd()
        urls = e.mimeData().urls()
        if urls: self.arquivo_solto.emit(urls[0].toLocalFile())

class DatabaseResultCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DatabaseResultCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        # Seções
        self._sec_futura = self._add_section(lay, "SISTEMA FUTURA")
        self._sec_fb = self._add_section(lay, "FIREBIRD")
        self._sec_integ = self._add_section(lay, "INTEGRIDADE")
        
        # Botões de ação
        row = QHBoxLayout()
        self.btn_copy = make_secondary_btn("Copiar Resultados", 160)
        self.btn_copy.clicked.connect(self._copy_all)
        row.addWidget(self.btn_copy)
        row.addStretch()
        lay.addLayout(row)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)
        self._data = {}

    def _add_section(self, parent_lay, title):
        parent_lay.addWidget(label(title, COLORS["accent"], 9, bold=True))
        content = QVBoxLayout()
        content.setSpacing(4)
        parent_lay.addLayout(content)
        parent_lay.addWidget(spacer(h=8))
        return content

    def _upd(self, _mode=""):
        self.setStyleSheet(f"QFrame#DatabaseResultCard {{ background: {COLORS['surface']}; border: 1.5px solid {COLORS['border']}; border-radius: 12px; }}")

    def atualizar(self, data: dict):
        self._data = data
        self._limpar(self._sec_futura)
        self._limpar(self._sec_fb)
        self._limpar(self._sec_integ)

        # Futura
        v_futura = data.get("versao_futura") or "Desconhecida"
        id_cli = data.get("id_cliente") or "N/A"
        self._sec_futura.addWidget(label(f"Versão: {v_futura}", COLORS["text"], 12, bold=True))
        self._sec_futura.addWidget(label(f"Cliente ID: {id_cli}", COLORS["text_dim"], 10))

        # FB
        v_arq = data.get("versao_arquivo") or "N/A"
        ods = f"{data.get('ods_major', 0)}.{data.get('ods_minor', 0)}"
        self._sec_fb.addWidget(label(f"Criado no Firebird: {v_arq}", COLORS["text"], 11))
        self._sec_fb.addWidget(label(f"ODS: {ods} | Page Size: {data.get('page_size', 0)}", COLORS["text_dim"], 10))

        # Integridade
        h_ok = data.get("header_ok", False)
        g_ok = data.get("gfix_ok", False)
        
        status_h = "🟢 Cabeçalho Íntegro" if h_ok else "🔴 Problemas no Cabeçalho"
        status_g = "🟢 Banco Validado (gfix)" if g_ok else "🔴 Erros de Corrupção" if data.get("gfix_executado") else "🟡 Não Validado"
        
        self._sec_integ.addWidget(label(status_h, COLORS["accent2"] if h_ok else COLORS["danger"], 10, bold=True))
        self._sec_integ.addWidget(label(status_g, COLORS["accent2"] if g_ok else COLORS["danger"], 10, bold=True))

    def _limpar(self, lay):
        while lay.count():
            item = lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def _copy_all(self):
        if not self._data: return
        txt = f"RESULTADO VERIFICAÇÃO\n\nVersão Futura: {self._data.get('versao_futura')}\nCliente ID: {self._data.get('id_cliente')}\nFB Arquivo: {self._data.get('versao_arquivo')}\nODS: {self._data.get('ods_major')}.{self._data.get('ods_minor')}"
        QApplication.clipboard().setText(txt)
        self.btn_copy.setText("Copiado!")
        QTimer.singleShot(2000, lambda: self.btn_copy.setText("Copiar Resultados"))
