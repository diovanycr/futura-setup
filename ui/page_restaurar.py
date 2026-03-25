# =============================================================================
# FUTURA SETUP — Página: Restaurar Backup
# Correções v6:
#   - "Outro caminho..." abre QFileDialog (explorador do Windows)
#   - Seta visível no combo via QLabel sobreposto (ArrowCombo)
# =============================================================================

import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QStackedWidget, QLineEdit, QComboBox, QPushButton,
    QFileDialog,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from ui.widgets import (
    PageHeader, SectionHeader, AlertBox, ResultBox,
    ProgressBlock, LogConsole, make_primary_btn, make_secondary_btn,
    btn_row, spacer, label
)
from ui.theme import COLORS, FONT_MONO, FONT_SANS
from ui.theme_manager import theme_manager
from core.installer import (
    listar_backups, listar_processos_na_pasta,
    encerrar_processos, formatar_tamanho, RestauracaoWorker
)
from core.logger import log
from config import PASTAS_INSTALACAO_PADRAO




# ── COMBO COM SETA VISÍVEL ────────────────────────────────────────────────────

class ArrowCombo(QWidget):
    """
    QComboBox envolto num QWidget com um QLabel de seta (▾) sobreposto
    à direita — garante seta visível independente do tema/estilo do Qt.
    """
    currentTextChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)

        self._combo = QComboBox(self)
        self._combo.currentTextChanged.connect(self.currentTextChanged)

        self._arrow = QLabel("▾", self)
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._upd_style()
        theme_manager.theme_changed.connect(self._upd_style)

    def resizeEvent(self, e):
        # O combo preenche o container inteiro — a borda e border-radius
        # ficam no container (self), não no QComboBox interno
        self._combo.setGeometry(2, 2, self.width() - 4, self.height() - 4)
        self._arrow.setGeometry(self.width() - 32, 0, 30, self.height())

    def _upd_style(self, _mode: str = ""):
        # Borda e cantos arredondados no container externo
        self.setStyleSheet(f"""
            ArrowCombo {{
                background: {COLORS["surface"]};
                border: 1.5px solid {COLORS["border"]};
                border-radius: 6px;
            }}
            ArrowCombo:hover {{
                border-color: {COLORS["text_dim"]};
            }}
        """)

        self._combo.setFont(QFont(FONT_MONO, 11))
        self._combo.setCursor(Qt.CursorShape.PointingHandCursor)
        # Combo interno sem borda/radius — apenas fundo e texto
        self._combo.setStyleSheet(f"""
            QComboBox {{
                background: {COLORS["surface"]};
                color: {COLORS["text"]};
                border: none;
                border-radius: 4px;
                padding: 4px 36px 4px 10px;
                font-family: Consolas;
                font-size: 11px;
            }}
            QComboBox::drop-down {{ border: none; width: 0px; }}
            QComboBox::down-arrow {{ width: 0; height: 0; }}
            QComboBox QAbstractItemView {{
                background: {COLORS["surface"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
                selection-background-color: {COLORS["accent_dim"]};
                selection-color: {COLORS["accent"]};
                padding: 4px;
                outline: none;
            }}
        """)
        self._arrow.setStyleSheet(
            f"color: {COLORS['text_mid']}; background: transparent; "
            f"font-size: 16px; border: none;"
        )

    # Delegações para o QComboBox interno
    def addItem(self, text: str):       self._combo.addItem(text)
    def clear(self):                    self._combo.clear()
    def currentText(self) -> str:       return self._combo.currentText()
    def setCurrentIndex(self, i: int):  self._combo.setCurrentIndex(i)
    def setCurrentText(self, t: str):   self._combo.setCurrentText(t)
    def findText(self, t: str) -> int:  return self._combo.findText(t)
    def insertItem(self, i, t: str):    self._combo.insertItem(i, t)
    def blockSignals(self, b: bool):    self._combo.blockSignals(b)
    def count(self) -> int:             return self._combo.count()
    def itemText(self, i: int) -> str:  return self._combo.itemText(i)


# ── CARD DE BACKUP ────────────────────────────────────────────────────────────

class BackupItem(QWidget):
    selected = pyqtSignal(object)

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self.info      = info
        self._selected = False
        self._state    = "normal"
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(38)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(10)

        self._check = QLabel()
        self._check.setObjectName("bi_check")
        self._check.setFixedSize(16, 16)
        self._check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._check.setFont(QFont(FONT_MONO, 8, QFont.Weight.Bold))

        nome = info["nome"]
        try:
            p = nome.replace("-", "_").split("_")
            data_fmt = f"{p[2]}/{p[1]}/{p[0]}  {p[3]}:{p[4]}:{p[5]}"
        except Exception:
            data_fmt = nome

        self._name_lbl = QLabel(data_fmt)
        self._name_lbl.setFont(QFont(FONT_MONO, 10, QFont.Weight.Bold))
        self._name_lbl.setObjectName("bi_name")

        self._sub_lbl = QLabel(f"({nome})")
        self._sub_lbl.setFont(QFont(FONT_MONO, 8))
        self._sub_lbl.setObjectName("bi_sub")

        meta_txt = f"{formatar_tamanho(info['tamanho'])}  ·  {info['arquivos']} arq."
        self._size_lbl = QLabel(meta_txt)
        self._size_lbl.setFont(QFont(FONT_MONO, 9))
        self._size_lbl.setObjectName("bi_size")
        self._size_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._meta_lbl = self._size_lbl

        lay.addWidget(self._check)
        lay.addWidget(self._name_lbl)
        lay.addWidget(self._sub_lbl)
        lay.addStretch()
        lay.addWidget(self._size_lbl)

        self._upd_style()
        theme_manager.theme_changed.connect(self._upd_style)

    def _upd_style(self, _mode: str = ""):
        if self._selected:
            bg      = COLORS["accent2_dim"]
            border  = COLORS["accent2"]
            chk_bg  = COLORS["accent2"]
            chk_bd  = "none"
            chk_txt = "✓"
            name_c  = COLORS["accent2"]
            name_w  = "600"
        elif self._state == "hover":
            bg      = COLORS["panel_hover"]
            border  = COLORS["border_light"]
            chk_bg  = "transparent"
            chk_bd  = f"1px solid {COLORS['border']}"
            chk_txt = ""
            name_c  = COLORS["text"]
            name_w  = "normal"
        else:
            bg      = COLORS["surface"]
            border  = COLORS["border"]
            chk_bg  = "transparent"
            chk_bd  = f"1px solid {COLORS['border']}"
            chk_txt = ""
            name_c  = COLORS["text"]
            name_w  = "normal"

        self._check.setText(chk_txt)
        self.setStyleSheet(f"""
            BackupItem {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 6px;
            }}
            QLabel#bi_check {{
                background: {chk_bg};
                color: white;
                border-radius: 9px;
                border: {chk_bd};
                font-size: 9px;
            }}
            QLabel#bi_name {{
                color: {name_c};
                font-weight: {name_w};
                background: transparent;
                border: none;
            }}
            QLabel#bi_sub  {{ color: {COLORS['text_dim']}; background: transparent; border: none; }}
            QLabel#bi_size {{ color: {COLORS['text_mid']}; background: transparent; border: none; }}
        """)

    def set_selected(self, v: bool):
        self._selected = v
        self._upd_style()

    def enterEvent(self, e):
        self._state = "hover"
        self._upd_style()

    def leaveEvent(self, e):
        self._state = "normal"
        self._upd_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self)


# ── PÁGINA PRINCIPAL ──────────────────────────────────────────────────────────

class PageRestaurar(QWidget):
    go_menu = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backup_items: list[BackupItem]   = []
        self._selected_backup: dict | None     = None
        self._pasta_atual: str                 = ""
        self._worker: RestauracaoWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = PageHeader("RESTAURAR", "Restauração de Backup")
        self._header.back_clicked.connect(self._on_back_clicked)
        root.addWidget(self._header)

        # Container para o conteúdo original
        content_w = QWidget()
        content_lay = QVBoxLayout(content_w)
        content_lay.setContentsMargins(40, 24, 40, 36)
        content_lay.setSpacing(0)

        self._stack = QStackedWidget()
        content_lay.addWidget(self._stack)
        root.addWidget(content_w, 1)

        self._stack.addWidget(self._build_list_page())     # 0
        self._stack.addWidget(self._build_confirm_page())  # 1
        self._stack.addWidget(self._build_progress_page()) # 2
        self._stack.addWidget(self._build_done_page())     # 3

    # ── LISTA ─────────────────────────────────────────────────────────────────

    def _build_list_page(self) -> QWidget:
        root = QWidget()
        root.setStyleSheet("background: transparent;")
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.setSpacing(10)

        self._list_alert = AlertBox(
            "Selecione um backup para restaurar.\n"
            "O conteúdo atual será salvo em backup de segurança antes da restauração.",
            "info"
        )
        lay.addWidget(self._list_alert)

        lay.addWidget(SectionHeader("Pasta de Instalação"))

        self._pasta_combo = ArrowCombo()
        self._pasta_combo.currentTextChanged.connect(self._on_pasta_combo_changed)
        lay.addWidget(self._pasta_combo)

        lay.addWidget(spacer(h=4))
        lay.addWidget(SectionHeader("Backups Disponíveis"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        self._bk_container = QWidget()
        self._bk_container.setStyleSheet("background: transparent;")
        self._bk_lay = QVBoxLayout(self._bk_container)
        self._bk_lay.setContentsMargins(0, 0, 0, 0)
        self._bk_lay.setSpacing(6)
        self._bk_lay.addStretch()
        scroll.setWidget(self._bk_container)
        lay.addWidget(scroll, 1)

        root_lay.addWidget(content, 1)

        # ── Rodapé fixo ───────────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet("background: transparent;")
        footer_lay = QVBoxLayout(footer)
        footer_lay.setContentsMargins(0, 8, 0, 0)
        footer_lay.setSpacing(0)

        self._btn_restaurar = make_primary_btn("↺  RESTAURAR SELECIONADO", 240)
        self._btn_restaurar.clicked.connect(self._confirm)
        self._btn_restaurar.setEnabled(False)
        footer_lay.addWidget(btn_row(self._btn_restaurar))
        root_lay.addWidget(footer, 0)
        return root

    # ── CONFIRMAR ─────────────────────────────────────────────────────────────

    def _build_confirm_page(self) -> QWidget:
        w   = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        lay.addWidget(SectionHeader("Confirmar Restauração"))

        self._confirm_box_w = QWidget()
        self._confirm_box_w.setObjectName("ConfirmBox")
        self._refresh_confirm_style()
        theme_manager.theme_changed.connect(self._refresh_confirm_style)
        confirm_lay = QVBoxLayout(self._confirm_box_w)
        confirm_lay.setContentsMargins(20, 16, 20, 16)
        confirm_lay.setSpacing(8)

        warn_title = QLabel("⚠  ATENÇÃO")
        warn_title.setFont(QFont(FONT_MONO, 12, QFont.Weight.Bold))
        warn_title.setStyleSheet(f"color: {COLORS['warn']}; background: transparent;")
        confirm_lay.addWidget(warn_title)

        warn_msg = QLabel(
            "O conteúdo atual da pasta de destino será movido para um\n"
            "backup de segurança antes da restauração."
        )
        warn_msg.setFont(QFont(FONT_MONO, 11))
        warn_msg.setStyleSheet(f"color: {COLORS['text_mid']}; background: transparent;")
        confirm_lay.addWidget(warn_msg)
        confirm_lay.addWidget(spacer(h=4))

        self._confirm_labels: dict[str, QLabel] = {}
        for campo in ["Backup", "Tamanho", "Arquivos", "Destino"]:
            row = QHBoxLayout()
            k   = QLabel(campo.upper())
            k.setFont(QFont(FONT_MONO, 10))
            k.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
            k.setFixedWidth(100)
            v = QLabel("—")
            v.setFont(QFont(FONT_MONO, 11))
            v.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
            self._confirm_labels[campo] = v
            row.addWidget(k)
            row.addWidget(v)
            row.addStretch()
            row_w = QWidget()
            row_w.setLayout(row)
            row_w.setStyleSheet("background: transparent;")
            confirm_lay.addWidget(row_w)

        lay.addWidget(self._confirm_box_w)
        lay.addWidget(spacer(h=8))

        btn_cancelar = make_secondary_btn("CANCELAR", 120)
        btn_cancelar.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        btn_ok = make_primary_btn("↺  CONFIRMAR RESTAURAÇÃO", 240)
        btn_ok.clicked.connect(self._run_restore)
        lay.addWidget(btn_row(btn_cancelar, btn_ok))
        lay.addStretch()
        return w

    def _refresh_confirm_style(self, _mode: str = ""):
        self._confirm_box_w.setStyleSheet(
            "QWidget#ConfirmBox {"
            f"  background: {COLORS['warn_dim']};"
            f"  border: 1px solid {COLORS['warn']};"
            "  border-radius: 8px;"
            "}"
        )

    def _build_progress_page(self) -> QWidget:
        w   = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        lay.addWidget(SectionHeader("Restaurando..."))
        self._prog_restore = ProgressBlock("Restaurando...")
        lay.addWidget(self._prog_restore)
        lay.addWidget(spacer(h=4))
        self._restore_console = LogConsole(max_height=240)
        lay.addWidget(self._restore_console)
        lay.addStretch()
        return w

    def _build_done_page(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        self._done_lay = QVBoxLayout(w)
        self._done_lay.setContentsMargins(0, 0, 0, 0)
        self._done_lay.setSpacing(12)
        self._done_lay.addStretch()
        return w

    # ── CARREGAR BACKUPS ──────────────────────────────────────────────────────

    def load_backups(self):
        opcoes = list(PASTAS_INSTALACAO_PADRAO)
        for p in log.prefs.pastas_hist:
            if p not in opcoes:
                opcoes.append(p)
        opcoes.append("📂  Outro caminho...")

        self._pasta_combo.blockSignals(True)
        self._pasta_combo.clear()
        for op in opcoes:
            self._pasta_combo.addItem(op)
        self._pasta_combo.setCurrentIndex(0)
        self._pasta_combo.blockSignals(False)

        self._carregar_pasta(opcoes[0])

    def _on_pasta_combo_changed(self, text: str):
        if text == "📂  Outro caminho...":
            self._abrir_explorador()
        else:
            self._carregar_pasta(text)

    def _abrir_explorador(self):
        pasta = QFileDialog.getExistingDirectory(
            self,
            "Selecione a pasta de instalação",
            "C:\\",
            QFileDialog.Option.ShowDirsOnly,
        )

        if pasta:
            pasta = str(Path(pasta))
            idx_outro = self._pasta_combo.findText("📂  Outro caminho...")
            if self._pasta_combo.findText(pasta) == -1:
                self._pasta_combo.blockSignals(True)
                self._pasta_combo.insertItem(idx_outro, pasta)
                self._pasta_combo.blockSignals(False)

            self._pasta_combo.blockSignals(True)
            self._pasta_combo.setCurrentText(pasta)
            self._pasta_combo.blockSignals(False)
            self._carregar_pasta(pasta)
        else:
            self._pasta_combo.blockSignals(True)
            self._pasta_combo.setCurrentIndex(0)
            self._pasta_combo.blockSignals(False)
            self._carregar_pasta(self._pasta_combo.currentText())

    def _carregar_pasta(self, pasta: str):
        if not pasta or pasta == "📂  Outro caminho...":
            return

        pasta = pasta.rstrip("\\")

        for w in self._backup_items:
            self._bk_lay.removeWidget(w)
            w.deleteLater()
        self._backup_items.clear()
        self._selected_backup = None
        self._btn_restaurar.setEnabled(False)
        self._stack.setCurrentIndex(0)

        while self._bk_lay.count() > 1:
            item = self._bk_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        todos = []
        for bk in listar_backups(pasta):
            bk["_pasta"] = pasta
            todos.append(bk)

        if not todos:
            empty = label(
                f"Nenhum backup encontrado em {pasta}.",
                COLORS["warn"], 12
            )
            self._bk_lay.insertWidget(0, empty)
            return

        for info in todos:
            item = BackupItem(info)
            item.selected.connect(self._select_backup)
            self._bk_lay.insertWidget(self._bk_lay.count() - 1, item)
            self._backup_items.append(item)

        if self._backup_items:
            self._select_backup(self._backup_items[0])

    def _select_backup(self, clicked: BackupItem):
        for w in self._backup_items:
            w.set_selected(False)
        clicked.set_selected(True)
        self._selected_backup = clicked.info
        self._pasta_atual     = clicked.info.get("_pasta", PASTAS_INSTALACAO_PADRAO[0])
        self._btn_restaurar.setEnabled(True)

    def _confirm(self):
        if not self._selected_backup:
            return
        bk = self._selected_backup

        log.prefs.add_pasta(self._pasta_atual)

        pasta_existe = os.path.exists(self._pasta_atual)
        destino_info = (self._pasta_atual if pasta_existe
                        else f"{self._pasta_atual}  ⚠ (pasta será criada)")

        self._confirm_labels["Backup"].setText(bk["nome"])
        self._confirm_labels["Tamanho"].setText(formatar_tamanho(bk["tamanho"]))
        self._confirm_labels["Arquivos"].setText(f"{bk['arquivos']} arquivo(s)")
        self._confirm_labels["Destino"].setText(destino_info)
        self._stack.setCurrentIndex(1)

    def _run_restore(self):
        if not self._selected_backup:
            return

        procs = listar_processos_na_pasta(self._pasta_atual)
        if procs:
            encerrar_processos([p["pid"] for p in procs])

        self._restore_console.clear_console()
        self._prog_restore.update(0, "Iniciando...", "Preparando restauração...")
        self._stack.setCurrentIndex(2)

        self._worker = RestauracaoWorker(
            pasta_destino  = self._pasta_atual,
            backup_caminho = self._selected_backup["caminho"],
        )
        self._worker.log_line.connect(self._restore_console.append_line)
        self._worker.status_text.connect(
            lambda txt: self._restore_console.append_line(txt, "info")
        )
        self._worker.progress.connect(
            lambda pct, nome, sub: self._prog_restore.update(pct, nome, sub)
        )
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, sucesso: bool, resumo: dict):
        while self._done_lay.count():
            item = self._done_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        kind   = "success" if sucesso else "error"
        titulo = "Restauração Concluída" if sucesso else "Falha na Restauração"
        rows   = [
            ("Backup",   resumo.get("backup", "—")),
            ("Arquivos", f"{resumo.get('arquivos', 0)} restaurado(s)"),
            ("Erros",    str(resumo.get("erros", 0))),
        ]
        box = ResultBox(titulo, rows, kind)
        btn = None # Redundant
        btn.clicked.connect(self.go_menu.emit)

        self._done_lay.addWidget(box)
        self._done_lay.addWidget(spacer(h=8))
        # No button row needed if menu button is removed
        self._done_lay.addStretch()
        self._stack.setCurrentIndex(3)

    def _on_back_clicked(self):
        idx = self._stack.currentIndex()
        if idx == 1: # Confirmar
            self._stack.setCurrentIndex(0)
        else:
            self.go_menu.emit()
