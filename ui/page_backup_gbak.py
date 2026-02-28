"""
ui/page_backup_gbak.py — Página de Backup e Restaure via GBAK (Modo 06)

Fluxo da página:
  Step 0 — Configuração (detecta caminhos, permite editar, escolhe Backup ou Restaure)
  Step 1A — Execução do Backup  (LogConsole + ProgressBlock)
  Step 1B — Execução do Restaure (LogConsole + ProgressBlock + seleção de .bck)
  Step 2  — Resultado final
"""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTime
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QFileDialog, QStackedWidget, QScrollArea, QSizePolicy,
    QButtonGroup, QRadioButton, QDialog, QComboBox, QTimeEdit, QPushButton,
    QApplication,
)

from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets import (
    PageTitle, SectionHeader, AlertBox, LogConsole,
    ProgressBlock, ResultBox, make_btn, make_btn_row, spacer, h_line, label,
    ConfirmDialog,
)
from core.logger import log
from core.backup_gbak import (
    BackupGbakWorker,
    RestaureGbakWorker,
    _DetectarFirebirdWorker,
    find_firebird_dir,
    find_dados_fdb,
    gerar_nome_backup,
    _fmt_size,
)
from core.agendador_backup import criar_tarefa, remover_tarefa, tarefa_existe

_DEFAULT_PASTA_DADOS     = r"C:\Futura\Dados"
_DEFAULT_PASTA_BACKUP    = r"C:\Futura\Backup"
_DEFAULT_PASTA_DADOSNOVO = r"C:\Futura\Dados"


# ── HELPERS DE BOTÃO ─────────────────────────────────────────────────────────

def _make_primary_btn(text: str, min_width: int = 180) -> QPushButton:
    btn = QPushButton(text)
    btn.setMinimumWidth(min_width)
    btn.setMinimumHeight(36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
    _apply_primary(btn)
    theme_manager.theme_changed.connect(lambda _: _apply_primary(btn))
    return btn

def _make_secondary_btn(text: str, min_width: int = 120) -> QPushButton:
    btn = QPushButton(text)
    btn.setMinimumWidth(min_width)
    btn.setMinimumHeight(36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFont(QFont(FONT_SANS, 12))
    _apply_secondary(btn)
    theme_manager.theme_changed.connect(lambda _: _apply_secondary(btn))
    return btn

def _apply_primary(btn: QPushButton):
    text_color = "#ffffff" if theme_manager.mode == "light" else "#001826"
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {COLORS["accent"]};
            color: {text_color};
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-weight: 700;
            font-size: 13px;
        }}
        QPushButton:hover {{ background-color: {COLORS["accent_hover"]}; }}
        QPushButton:pressed {{ background-color: {COLORS["accent_press"]}; }}
        QPushButton:disabled {{
            background-color: {COLORS["panel_hover"]};
            color: {COLORS["text_disabled"]};
        }}
    """)

def _apply_secondary(btn: QPushButton):
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: transparent;
            color: {COLORS["text"]};
            border: 1.5px solid {COLORS["btn_border"]};
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: {COLORS["panel_hover"]};
            border-color: {COLORS["text_dim"]};
        }}
        QPushButton:pressed {{ background-color: {COLORS["panel_press"]}; }}
    """)


# ---------------------------------------------------------------------------
# Diálogo de agendamento
# ---------------------------------------------------------------------------

class _AgendarDialog(QDialog):
    def __init__(self, firebird_dir: str, dados_fdb: str,
                 pasta_backup: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agendar Backup Automático")
        self.setFixedWidth(460)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint)
        self._firebird_dir  = firebird_dir
        self._dados_fdb     = dados_fdb
        self._pasta_backup  = pasta_backup

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(14)

        t = QLabel("🕐  Agendar Backup Automático via GBAK")
        t.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
        t.setWordWrap(True)
        lay.addWidget(t)

        freq_row = QHBoxLayout()
        freq_lbl = QLabel("Frequência:")
        freq_lbl.setFixedWidth(100)
        self._freq_combo = QComboBox()
        self._freq_combo.addItems(["Diário (DAILY)", "Semanal (WEEKLY)", "Mensal (MONTHLY)"])
        freq_row.addWidget(freq_lbl)
        freq_row.addWidget(self._freq_combo, 1)
        lay.addLayout(freq_row)

        hora_row = QHBoxLayout()
        hora_lbl = QLabel("Horário:")
        hora_lbl.setFixedWidth(100)
        self._hora_edit = QTimeEdit()
        self._hora_edit.setTime(QTime(2, 0))
        self._hora_edit.setDisplayFormat("HH:mm")
        self._hora_edit.setFixedWidth(80)
        hora_row.addWidget(hora_lbl)
        hora_row.addWidget(self._hora_edit)
        hora_row.addStretch()
        lay.addLayout(hora_row)

        if tarefa_existe():
            aviso = QLabel(
                "⚠  Já existe uma tarefa agendada para este backup.\n"
                "Ao confirmar, ela será substituída."
            )
            aviso.setWordWrap(True)
            aviso.setStyleSheet(f"color: {COLORS['warn']}; font-size: 11px;")
            lay.addWidget(aviso)

        self._alert = QLabel("")
        self._alert.setWordWrap(True)
        self._alert.setStyleSheet(f"color: {COLORS['danger']}; font-size: 11px;")
        self._alert.setVisible(False)
        lay.addWidget(self._alert)

        lay.addSpacing(4)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        b_cancel  = make_btn("Cancelar",     "secondary", min_width=110)
        b_confirm = make_btn("Criar tarefa", "primary",   min_width=130)
        b_cancel.clicked.connect(self.reject)
        b_confirm.clicked.connect(self._criar)
        btn_row.addStretch()
        btn_row.addWidget(b_cancel)
        btn_row.addWidget(b_confirm)
        lay.addLayout(btn_row)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(
            f"QDialog {{ background: {COLORS['surface']}; color: {COLORS['text']}; }}"
            f"QLabel {{ background: transparent; color: {COLORS['text_mid']}; }}"
            f"QComboBox, QTimeEdit {{ background: {COLORS['surface']}; color: {COLORS['text']}; "
            f"  border: 1.5px solid {COLORS['border']}; border-radius: 4px; padding: 2px 6px; }}"
        )

    def _criar(self):
        freq_map = {0: "DAILY", 1: "WEEKLY", 2: "MONTHLY"}
        freq  = freq_map.get(self._freq_combo.currentIndex(), "DAILY")
        hora  = self._hora_edit.time().toString("HH:mm")
        sucesso, msg = criar_tarefa(
            self._firebird_dir, self._dados_fdb, self._pasta_backup,
            hora=hora, frequencia=freq,
        )
        if sucesso:
            self.accept()
        else:
            self._alert.setText(msg)
            self._alert.setVisible(True)


# ---------------------------------------------------------------------------
# Widget de campo com label + linha editável + botão "..."
# ---------------------------------------------------------------------------

class _PathField(QWidget):
    def __init__(self, label_text: str, placeholder: str, is_dir: bool = True, parent=None):
        super().__init__(parent)
        self._is_dir = is_dir
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)          # ← reduzido

        self._lbl = QLabel(label_text)
        self._edit = QLineEdit()
        self._edit.setPlaceholderText(placeholder)
        self._edit.setMinimumHeight(28)    # ← reduzido

        self._btn = make_btn("", "secondary", min_width=40)  # ← ícone de pasta nativo
        folder_icon = QApplication.style().standardIcon(
            QApplication.style().StandardPixmap.SP_DirOpenIcon
        )
        self._btn.setIcon(folder_icon)
        self._btn.setMaximumWidth(40)
        self._btn.setMinimumHeight(28)     # ← reduzido
        self._btn.clicked.connect(self._browse)

        row = QHBoxLayout()
        row.setSpacing(5)
        row.addWidget(self._edit)
        row.addWidget(self._btn)

        lay.addWidget(self._lbl)
        lay.addLayout(row)

        theme_manager.theme_changed.connect(self._upd)
        self._upd()

    def _upd(self, _mode: str = ""):
        self._lbl.setStyleSheet(
            f"color:{COLORS['text']}; font-size:12px; font-weight:600;"   # ← font menor
        )
        self._edit.setStyleSheet(
            f"background:{COLORS['surface']}; color:{COLORS['text']};"
            f"border:1px solid {COLORS['text_dim']}; border-radius:5px; padding:3px 7px;"
            f"font-size:12px;"    # ← font menor
        )

    def _browse(self):
        if self._is_dir:
            p = QFileDialog.getExistingDirectory(self, "Selecionar pasta", self._edit.text())
            if p:
                self._edit.setText(os.path.normpath(p))
        else:
            p, _ = QFileDialog.getOpenFileName(
                self, "Selecionar arquivo de backup", self._edit.text(),
                "Backup Firebird (*.bck)"
            )
            if p:
                self._edit.setText(os.path.normpath(p))

    @property
    def value(self) -> str:
        return self._edit.text().strip()

    @value.setter
    def value(self, v: str):
        self._edit.setText(v)


# ---------------------------------------------------------------------------
# Step 0 — Configuração
# ---------------------------------------------------------------------------

class _StepConfig(QWidget):
    go_backup   = pyqtSignal()
    go_restaure = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: QThread | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 16, 0)
        lay.setSpacing(8)          # ← reduzido de 14

        self._alert = AlertBox("Detectando instalação do Firebird e caminhos padrão...", "info")
        lay.addWidget(self._alert)

        lay.addWidget(SectionHeader("Caminhos"))

        self._fld_firebird = _PathField(
            "Diretório do Firebird (onde fica o gbak.exe)",
            r"Ex: C:\Program Files (x86)\Firebird\Firebird_3_0",
        )
        lay.addWidget(self._fld_firebird)

        self._fld_dados = _PathField(
            "Pasta do banco de dados (onde fica DADOS.fdb)",
            r"Ex: C:\Futura\Dados",
        )
        self._fld_dados.value = _DEFAULT_PASTA_DADOS
        lay.addWidget(self._fld_dados)

        self._fld_backup_dir = _PathField(
            "Pasta de destino dos backups (.bck)",
            r"Ex: C:\Futura\Backup",
        )
        self._fld_backup_dir.value = _DEFAULT_PASTA_BACKUP
        lay.addWidget(self._fld_backup_dir)

        self._fld_dados_novo = _PathField(
            "Pasta de destino do DADOSNOVO.fdb (restaure)",
            r"Ex: C:\Futura\Dados",
        )
        self._fld_dados_novo.value = _DEFAULT_PASTA_DADOSNOVO
        lay.addWidget(self._fld_dados_novo)

        lay.addWidget(h_line())

        lay.addWidget(SectionHeader("Arquivo de backup para Restaure"))

        self._alert_bck = AlertBox(
            "Deixe em branco para o GBAK usar o backup mais recente da pasta acima.",
            "info",
        )
        lay.addWidget(self._alert_bck)

        self._fld_bck_file = _PathField(
            "Arquivo .bck (opcional — selecione apenas para restaure específico)",
            r"Ex: C:\Futura\Backup\BACKUP_2025-01-15_14-30.bck",
            is_dir=False,
        )
        lay.addWidget(self._fld_bck_file)

        self._info_lbl = label("", COLORS["text_mid"], 11)
        self._info_lbl.setWordWrap(True)
        lay.addWidget(self._info_lbl)

        lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # Rodapé
        footer = QWidget()
        foot_lay = QVBoxLayout(footer)
        foot_lay.setContentsMargins(0, 8, 0, 0)
        foot_lay.setSpacing(6)

        self._btn_backup   = _make_primary_btn("▶  Iniciar BACKUP",   200)
        self._btn_restaure = _make_secondary_btn("▶  Iniciar RESTAURE", 200)
        self._btn_backup.clicked.connect(self._on_backup)
        self._btn_restaure.clicked.connect(self._on_restaure)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addWidget(self._btn_backup)
        btn_row.addWidget(self._btn_restaure)
        btn_row.addStretch()

        foot_lay.addWidget(h_line())
        foot_lay.addLayout(btn_row)
        root.addWidget(footer, 0)

        theme_manager.theme_changed.connect(self._upd)
        self._upd()

    def _upd(self, _mode: str = ""):
        self._info_lbl.setStyleSheet(f"color:{COLORS['text_mid']}; font-size:11px;")

    def iniciar_deteccao(self):
        self._alert.set_text("Detectando instalação do Firebird e caminhos padrão...")
        self._alert.set_kind("info")
        self._worker = _DetectarFirebirdWorker(_DEFAULT_PASTA_DADOS)
        self._worker.finished.connect(
            self._on_deteccao, Qt.ConnectionType.SingleShotConnection
        )
        self._worker.start()

    def _on_deteccao(self, fb_dir: str, dados_fdb: str):
        if fb_dir:
            self._fld_firebird.value = fb_dir
            self._alert.set_text(f"Firebird encontrado em: {fb_dir}")
            self._alert.set_kind("success")
        else:
            self._alert.set_text(
                "Firebird não detectado automaticamente. Informe o caminho manualmente."
            )
            self._alert.set_kind("warn")

        if dados_fdb:
            pasta = os.path.dirname(dados_fdb)
            self._fld_dados.value = pasta
            self._info_lbl.setText(f"DADOS.fdb detectado em: {dados_fdb}")

    def _validar(self) -> str | None:
        if not self._fld_firebird.value:
            return "Informe o diretório do Firebird."
        gbak = os.path.join(self._fld_firebird.value, "gbak.exe")
        if not os.path.isfile(gbak):
            return f"gbak.exe não encontrado em: {self._fld_firebird.value}"
        if not self._fld_dados.value:
            return "Informe a pasta do banco de dados."
        if not self._fld_backup_dir.value:
            return "Informe a pasta de destino dos backups."
        return None

    def _on_backup(self):
        err = self._validar()
        if err:
            self._alert.set_text(err)
            self._alert.set_kind("danger")
            return
        dados_fdb = os.path.join(self._fld_dados.value, "DADOS.fdb")
        bck_dest  = gerar_nome_backup(self._fld_backup_dir.value)
        dlg = ConfirmDialog(
            "Iniciar Backup do Banco de Dados",
            [
                f"Banco de origem:  {dados_fdb}",
                f"Destino do backup:  {bck_dest}",
                "",
                "O Firebird será pausado durante o processo.",
                "O banco será renomeado para DADOS_TEMP.fdb temporariamente.",
            ],
            self,
        )
        dlg.exec()
        if dlg.confirmado():
            self.go_backup.emit()

    def _on_restaure(self):
        err = self._validar()
        if err:
            self._alert.set_text(err)
            self._alert.set_kind("danger")
            return
        bck = self._fld_bck_file.value or "(mais recente da pasta)"
        dlg = ConfirmDialog(
            "Iniciar Restaure do Banco de Dados",
            [
                f"Arquivo de backup:  {bck}",
                f"Banco gerado:  {os.path.join(self._fld_dados_novo.value, 'DADOSNOVO.fdb')}",
                "",
                "O banco DADOS.fdb original NÃO será alterado.",
                "O arquivo DADOSNOVO.fdb será gerado para revisão.",
            ],
            self,
        )
        dlg.exec()
        if dlg.confirmado():
            self.go_restaure.emit()

    @property
    def firebird_dir(self) -> str:
        return self._fld_firebird.value

    @property
    def pasta_dados(self) -> str:
        return self._fld_dados.value

    @property
    def pasta_backup(self) -> str:
        return self._fld_backup_dir.value

    @property
    def pasta_dados_novo(self) -> str:
        return self._fld_dados_novo.value

    @property
    def bck_especifico(self) -> str:
        return self._fld_bck_file.value


# ---------------------------------------------------------------------------
# Step 1A — Execução do Backup
# ---------------------------------------------------------------------------

class _StepBackup(QWidget):
    finished = pyqtSignal(bool, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: BackupGbakWorker | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._progress = ProgressBlock("Backup via GBAK")
        lay.addWidget(self._progress)

        self._console = LogConsole(max_height=0)
        lay.addWidget(self._console, 1)

        footer = QWidget()
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(0, 8, 0, 0)
        self._btn_cancel = _make_secondary_btn("✕  Cancelar", 140)
        self._btn_cancel.clicked.connect(self._cancelar)
        f_lay.addStretch()
        f_lay.addWidget(self._btn_cancel)

        lay.addWidget(h_line())
        lay.addWidget(footer, 0)

    def iniciar(self, firebird_dir: str, dados_fdb: str, backup_bck: str):
        self._console.clear_console()
        self._progress.set_progress(0, "Iniciando backup...")
        self._btn_cancel.setEnabled(True)

        self._worker = BackupGbakWorker(firebird_dir, dados_fdb, backup_bck)
        self._worker.log_line.connect(self._console.append_line)
        self._worker.progress.connect(
            lambda pct, t, d: self._progress.set_progress(pct, f"{t}  {d}".strip())
        )
        self._worker.finished.connect(self.finished)
        self._worker.start()

    def _cancelar(self):
        if self._worker:
            self._btn_cancel.setEnabled(False)
            self._worker.stop()
            self._worker.wait(3000)


# ---------------------------------------------------------------------------
# Step 1B — Execução do Restaure
# ---------------------------------------------------------------------------

class _StepRestaure(QWidget):
    finished = pyqtSignal(bool, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: RestaureGbakWorker | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._progress = ProgressBlock("Restaure via GBAK")
        lay.addWidget(self._progress)

        self._console = LogConsole(max_height=0)
        lay.addWidget(self._console, 1)

        footer = QWidget()
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(0, 8, 0, 0)
        self._btn_cancel = _make_secondary_btn("✕  Cancelar", 140)
        self._btn_cancel.clicked.connect(self._cancelar)
        f_lay.addStretch()
        f_lay.addWidget(self._btn_cancel)

        lay.addWidget(h_line())
        lay.addWidget(footer, 0)

    def iniciar(self, firebird_dir: str, backup_bck: str, dados_novo: str):
        self._console.clear_console()
        self._progress.set_progress(0, "Iniciando restaure...")
        self._btn_cancel.setEnabled(True)

        self._worker = RestaureGbakWorker(firebird_dir, backup_bck, dados_novo)
        self._worker.log_line.connect(self._console.append_line)
        self._worker.progress.connect(
            lambda pct, t, d: self._progress.set_progress(pct, f"{t}  {d}".strip())
        )
        self._worker.finished.connect(self.finished)
        self._worker.start()

    def _cancelar(self):
        if self._worker:
            self._btn_cancel.setEnabled(False)
            self._worker.stop()
            self._worker.wait(3000)


# ---------------------------------------------------------------------------
# Step 2 — Resultado
# ---------------------------------------------------------------------------

class _StepResultado(QWidget):
    go_menu        = pyqtSignal()
    go_config      = pyqtSignal()
    agendar_backup = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self._alert = AlertBox("", "success")
        lay.addWidget(self._alert)

        self._result_box = ResultBox("Detalhes", [], "success")
        lay.addWidget(self._result_box)

        self._nota = label("", COLORS["text_mid"], 11)
        self._nota.setWordWrap(True)
        lay.addWidget(self._nota)

        lay.addStretch()
        lay.addWidget(h_line())

        btn_nova = _make_secondary_btn("Nova operação", 150)
        btn_nova.clicked.connect(self.go_config.emit)
        btn_agendar = _make_secondary_btn("🕐 Agendar Backup Auto", 180)
        btn_agendar.clicked.connect(self.agendar_backup.emit)
        btn_menu = _make_primary_btn("← Menu Principal", 160)
        btn_menu.clicked.connect(self.go_menu.emit)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addWidget(btn_menu)
        btns.addWidget(btn_nova)
        btns.addWidget(btn_agendar)
        btns.addStretch()

        btn_w = QWidget()
        btn_w.setLayout(btns)
        btn_w.setStyleSheet("background: transparent;")
        lay.addWidget(btn_w)

        theme_manager.theme_changed.connect(self._upd)
        self._upd()

    def _upd(self, _mode: str = ""):
        self._nota.setStyleSheet(f"color:{COLORS['text_mid']}; font-size:11px;")

    def set_resultado(self, operacao: str, sucesso: bool, info: dict):
        lay = self.layout()
        lay.removeWidget(self._result_box)
        self._result_box.deleteLater()

        if sucesso:
            self._alert.set_text(f"✓ {operacao} concluído com sucesso!")
            self._alert.set_kind("success")
            rows = []
            if "backup_path" in info:
                rows.append(("Arquivo gerado", info["backup_path"]))
            if "dados_novo" in info:
                rows.append(("Banco restaurado", info["dados_novo"]))
            if "tamanho" in info:
                rows.append(("Tamanho", _fmt_size(info["tamanho"])))
            self._result_box = ResultBox(f"Resultado do {operacao}", rows, "success")
            if operacao == "Restaure":
                self._nota.setText(
                    "O arquivo DADOSNOVO.fdb foi gerado com sucesso. "
                    "O banco DADOS.fdb original não foi alterado.\n"
                    "Revise o banco restaurado antes de substituir o banco em produção."
                )
        else:
            cancelado = info.get("cancelado", False)
            self._alert.set_text(
                f"⚠ {operacao} cancelado." if cancelado else f"✕ {operacao} falhou."
            )
            self._alert.set_kind("warn" if cancelado else "danger")
            self._result_box = ResultBox(
                f"Resultado do {operacao}", [], "warning" if cancelado else "error"
            )
            self._nota.setText("")

        lay.insertWidget(1, self._result_box)


# ---------------------------------------------------------------------------
# PageBackupGbak — página principal
# ---------------------------------------------------------------------------

class PageBackupGbak(QWidget):
    go_menu = pyqtSignal()

    _IDX_CONFIG   = 0
    _IDX_BACKUP   = 1
    _IDX_RESTAURE = 2
    _IDX_RESULT   = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: QThread | None = None
        self._operacao_atual = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 20)   # ← margens padronizadas
        root.setSpacing(8)                          # ← reduzido

        root.addWidget(PageTitle("", "Backup / Restaure de Banco de Dados"))  # ← "06" removido

        self._stack = QStackedWidget()

        self._cfg       = _StepConfig()
        self._bk        = _StepBackup()
        self._rst       = _StepRestaure()
        self._resultado = _StepResultado()

        self._stack.addWidget(self._cfg)
        self._stack.addWidget(self._bk)
        self._stack.addWidget(self._rst)
        self._stack.addWidget(self._resultado)

        root.addWidget(self._stack, 1)

        self._cfg.go_backup.connect(self._iniciar_backup)
        self._cfg.go_restaure.connect(self._iniciar_restaure)
        self._bk.finished.connect(self._on_backup_finished)
        self._rst.finished.connect(self._on_restaure_finished)
        self._resultado.go_menu.connect(self.go_menu)
        self._resultado.go_config.connect(self._go_config)
        self._resultado.agendar_backup.connect(self._abrir_agendador)

    def _abrir_agendador(self):
        firebird_dir = self._cfg.firebird_dir
        pasta_dados  = self._cfg.pasta_dados
        pasta_backup = self._cfg.pasta_backup

        dados_fdb = None
        for name in ("DADOS.fdb", "dados.fdb", "Dados.fdb"):
            candidate = os.path.join(pasta_dados, name)
            if os.path.isfile(candidate):
                dados_fdb = candidate
                break
        if not dados_fdb:
            dados_fdb = os.path.join(pasta_dados, "DADOS.fdb")

        dlg = _AgendarDialog(firebird_dir, dados_fdb, pasta_backup, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._resultado._nota.setText(
                "✓ Tarefa agendada criada com sucesso no Agendador de Tarefas do Windows."
            )

    def reset(self):
        self._go_step(self._IDX_CONFIG)
        self._cfg.iniciar_deteccao()

    def _go_step(self, idx: int):
        self._stack.setCurrentIndex(idx)

    def _go_config(self):
        self._go_step(self._IDX_CONFIG)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self._stack.currentIndex() == self._IDX_CONFIG:
                self.go_menu.emit()
        else:
            super().keyPressEvent(event)

    def _iniciar_backup(self):
        firebird_dir = self._cfg.firebird_dir
        pasta_dados  = self._cfg.pasta_dados
        pasta_backup = self._cfg.pasta_backup

        dados_fdb = None
        for name in ("DADOS.fdb", "dados.fdb", "Dados.fdb"):
            candidate = os.path.join(pasta_dados, name)
            if os.path.isfile(candidate):
                dados_fdb = candidate
                break
        if not dados_fdb:
            dados_fdb = os.path.join(pasta_dados, "DADOS.fdb")

        backup_bck = gerar_nome_backup(pasta_backup)
        self._operacao_atual = "Backup"
        self._go_step(self._IDX_BACKUP)
        self._bk.iniciar(firebird_dir, dados_fdb, backup_bck)
        self._worker = self._bk._worker

    def _iniciar_restaure(self):
        firebird_dir     = self._cfg.firebird_dir
        pasta_backup     = self._cfg.pasta_backup
        pasta_dados_novo = self._cfg.pasta_dados_novo

        bck_file = self._cfg.bck_especifico
        if not bck_file:
            bck_file = self._ultimo_backup(pasta_backup)

        if not bck_file:
            log.warn("[BackupGBAK] Nenhum arquivo .bck encontrado para restaure.")
            self._cfg._alert.set_text(
                "Nenhum arquivo .bck encontrado. Selecione o arquivo manualmente."
            )
            self._cfg._alert.set_kind("danger")
            return

        dados_novo = os.path.join(pasta_dados_novo, "DADOSNOVO.fdb")
        self._operacao_atual = "Restaure"
        self._go_step(self._IDX_RESTAURE)
        self._rst.iniciar(firebird_dir, bck_file, dados_novo)
        self._worker = self._rst._worker

    def _on_backup_finished(self, sucesso: bool, info: dict):
        self._worker = None
        self._resultado.set_resultado("Backup", sucesso, info)
        self._go_step(self._IDX_RESULT)

    def _on_restaure_finished(self, sucesso: bool, info: dict):
        self._worker = None
        self._resultado.set_resultado("Restaure", sucesso, info)
        self._go_step(self._IDX_RESULT)

    @staticmethod
    def _ultimo_backup(pasta: str) -> str | None:
        if not os.path.isdir(pasta):
            return None
        bcks = sorted(
            [os.path.join(pasta, f) for f in os.listdir(pasta) if f.endswith(".bck")],
            key=os.path.getmtime,
            reverse=True,
        )
        return bcks[0] if bcks else None
