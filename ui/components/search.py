# =============================================================================
# FUTURA SETUP — UI Components: Global Search Overlay
# =============================================================================

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QListWidget, 
    QListWidgetItem, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QRect
from PyQt6.QtGui import QFont, QColor

from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.components.containers import BlurOverlay

class SearchResultItem(QWidget):
    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(0)
        
        self.title_lbl = QLabel(title)
        self.title_lbl.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
        
        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setFont(QFont(FONT_SANS, 9))
        self.sub_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        
        lay.addWidget(self.title_lbl)
        lay.addWidget(self.sub_lbl)
        
        self.setStyleSheet("background: transparent;")

class SearchOverlay(QWidget):
    result_selected = pyqtSignal(int)  # index da pagina

    def __init__(self, nav_manager, parent: QWidget):
        super().__init__(parent)
        self._nav = nav_manager
        self._entries = self._nav.get_searchable_entries()
        
        # Blur de fundo
        self._blur = BlurOverlay(parent)
        
        # Config do Widget
        self.setFixedSize(parent.size())
        self.hide()
        
        # Central Box
        self._box = QFrame(self)
        self._box.setFixedWidth(500)
        self._box.setFixedHeight(400)
        self._box.setObjectName("SearchBox")
        
        shadow = QGraphicsDropShadowEffect(self._box)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 180))
        self._box.setGraphicsEffect(shadow)
        
        box_lay = QVBoxLayout(self._box)
        box_lay.setContentsMargins(0, 0, 0, 0)
        box_lay.setSpacing(0)
        
        # Input Area
        input_w = QWidget()
        input_lay = QHBoxLayout(input_w)
        input_lay.setContentsMargins(16, 12, 16, 12)
        
        self._input = QLineEdit()
        self._input.setPlaceholderText("O que você deseja fazer?")
        self._input.setFont(QFont(FONT_SANS, 13))
        self._input.setFrame(False)
        self._input.textChanged.connect(self._on_search)
        self._input.installEventFilter(self)
        
        esc_hint = QLabel("ESC")
        esc_hint.setFont(QFont(FONT_MONO, 8, QFont.Weight.Bold))
        esc_hint.setContentsMargins(6, 2, 6, 2)
        esc_hint.setStyleSheet(f"background: {COLORS['bg']}; border: 1px solid {COLORS['border']}; border-radius: 4px; color: {COLORS['text_dim']};")
        
        input_lay.addWidget(self._input, 1)
        input_lay.addWidget(esc_hint)
        box_lay.addWidget(input_w)
        
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {COLORS['border']};")
        box_lay.addWidget(div)
        
        # Results List
        self._list = QListWidget()
        self._list.setFrameShape(QFrame.Shape.NoFrame)
        self._list.setCursor(Qt.CursorShape.PointingHandCursor)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setObjectName("SearchList")
        box_lay.addWidget(self._list)
        
        self._upd_style()
        theme_manager.theme_changed.connect(self._upd_style)

    def _upd_style(self, _mode=""):
        self.setStyleSheet("background: transparent;")
        bg = COLORS["surface"]
        self._box.setStyleSheet(f"""
            QFrame#SearchBox {{
                background: {bg};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
            QLineEdit {{ background: transparent; color: {COLORS['text']}; }}
            QListWidget#SearchList {{
                background: transparent;
                outline: none;
                border: none;
                padding: 4px;
            }}
            QListWidget#SearchList::item {{
                background: transparent;
                border-radius: 6px;
                padding: 4px;
            }}
            QListWidget#SearchList::item:selected {{
                background: {COLORS['accent_dim']};
                color: {COLORS['accent']};
            }}
        """)

    def show_search(self):
        self._entries = self._nav.get_searchable_entries()
        self.resize(self.parentWidget().size())
        self._blur.resize(self.parentWidget().size())
        self._box.move((self.width() - self._box.width()) // 2, 80)
        
        self._blur.show()
        self.show()
        self.raise_()
        self._input.clear()
        self._on_search("")
        self._input.setFocus()

    def hide_search(self):
        self.hide()
        self._blur.hide()

    def _on_search(self, text: str):
        self._list.clear()
        text = text.lower().strip()
        
        matches = []
        for entry in self._entries:
            score = 0
            if text in entry["title"].lower(): score += 10
            if text in entry["tags"].lower(): score += 5
            
            if score > 0 or not text:
                matches.append((score, entry))
        
        # Ordenar por relevância
        matches.sort(key=lambda x: x[0], reverse=True)
        
        for _, entry in matches:
            item = QListWidgetItem(self._list)
            item.setData(Qt.ItemDataRole.UserRole, entry["idx"])
            
            # Widget customizado para o item
            w = SearchResultItem(entry["title"], entry["tags"].split()[0].upper())
            item.setSizeHint(w.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, w)
            
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _on_item_clicked(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        self.result_selected.emit(idx)
        self.hide_search()

    def eventFilter(self, obj, event):
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.hide_search()
                return True
            if key == Qt.Key.Key_Down:
                self._list.setCurrentRow((self._list.currentRow() + 1) % self._list.count())
                return True
            if key == Qt.Key.Key_Up:
                self._list.setCurrentRow((self._list.currentRow() - 1 + self._list.count()) % self._list.count())
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._list.currentItem():
                    self._on_item_clicked(self._list.currentItem())
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        # Se clicar fora da caixa, fecha
        if not self._box.geometry().contains(event.pos()):
            self.hide_search()
        else:
            super().mousePressEvent(event)
