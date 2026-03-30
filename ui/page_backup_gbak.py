"""
ui/page_backup_gbak.py - Pagina de Backup e Restaure via GBAK

Fluxo da pagina:
  Step 0  - Configuracao (com abas: Backup | Restaure)
  Step 1A - Execucao do Backup  (LogConsole + ProgressBlock)
  Step 1B - Execucao do Restaure (LogConsole + ProgressBlock)
  Step 2  - Resultado final

Deteccao automatica de versao do Firebird:
  - Ao selecionar o .fdb, le o ODS do cabecalho binario do arquivo
  - ODS 11 -> Firebird 2.5 | ODS 12 -> Firebird 3.0 | ODS 13 -> Firebird 4.0 | ODS 14 -> Firebird 5.0
  - Sugere automaticamente o diretorio do gbak compativel com a versao detectada
  - Nao requer Firebird instalado para a deteccao
"""

from __future__ import annotations

import os
import glob
import struct
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTime
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QFileDialog, QStackedWidget, QScrollArea,
    QDialog, QComboBox, QTimeEdit, QPushButton, QApplication,
    QTabWidget,
)

from ui.theme import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets import (
    PageHeader, SectionHeader, AlertBox, LogConsole,
    ProgressBlock, ResultBox, make_primary_btn, make_secondary_btn,
    make_folder_btn, btn_row, spacer, h_line, label, ConfirmDialog,
)
from core.logger import log
from core.backup_gbak import (
    BackupGbakWorker,
    RestaureGbakWorker,
    _DetectarFirebirdWorker,
    find_firebird_dir,
    gerar_nome_backup,
    _fmt_size,
)
from core.agendador_backup import criar_tarefa, remover_tarefa, tarefa_existe

_DEFAULT_PASTA_DADOS  = r"C:\Futura\Dados"
_DEFAULT_PASTA_BACKUP = r"C:\Futura\Backup"

# Mapeamento ODS Major -> versao do Firebird
_ODS_VERSAO_MAP = {
    11: "Firebird 2.5",
    12: "Firebird 3.0",
    13: "Firebird 4.0",
    14: "Firebird 5.0",
}

# Substrings para localizar o diretorio correto ao varrer a instalacao
_VERSAO_DIR_HINT = {
    "Firebird 2.5": ["2_5", "25", "2.5"],
    "Firebird 3.0": ["3_0", "30", "3.0"],
    "Firebird 4.0": ["4_0", "40", "4.0"],
    "Firebird 5.0": ["5_0", "50", "5.0"],
}


# ---------------------------------------------------------------------------
# Helper: le o ODS do cabecalho binario do .fdb sem precisar do Firebird
# ---------------------------------------------------------------------------

def _ler_ods_fdb(fdb_path: str) -> tuple[int, int] | None:
    """Le os bytes ODS major/minor do cabecalho do .fdb."""
    try:
        with open(fdb_path, "rb") as f:
            f.seek(16)
            data = f.read(4)
            if len(data) < 4:
                return None
            ods_major, ods_minor = struct.unpack_from("<HH", data)
            return ods_major, ods_minor
    except Exception:
        return None


def _versao_pelo_ods(ods_major: int) -> str:
    return _ODS_VERSAO_MAP.get(ods_major, f"Firebird desconhecido (ODS {ods_major})")


def _derivar_dados_novo(dados_fdb: str) -> str:
    p = Path(dados_fdb)
    return str(p.with_name(p.stem + "_NOVO" + p.suffix))


# ---------------------------------------------------------------------------
# Dialogo de agendamento
# ---------------------------------------------------------------------------

class _AgendarDialog(QDialog):
    def __init__(self, firebird_dir: str, dados_fdb: str,
                 pasta_backup: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agendar Backup Automatico")
        self.setFixedWidth(460)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint
        )
        self._firebird_dir = firebird_dir
        self._dados_fdb    = dados_fdb
        self._pasta_backup = pasta_backup

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(14)

        titulo = QLabel("Agendar Backup Automatico via GBAK")
        titulo.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))
        titulo.setWordWrap(True)
        lay.addWidget(titulo)

        freq_row = QHBoxLayout()
        freq_lbl = QLabel("Frequencia:")
        freq_lbl.setFixedWidth(100)
        self._freq_combo = QComboBox()
        self._freq_combo.addItems(["Diario (DAILY)", "Semanal (WEEKLY)", "Mensal (MONTHLY)"])
        freq_row.addWidget(freq_lbl)
        freq_row.addWidget(self._freq_combo, 1)
        lay.addLayout(freq_row)

        hora_row = QHBoxLayout()
        hora_lbl = QLabel("Horario:")
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
                "Ja existe uma tarefa agendada para este backup.\n"
                "Ao confirmar, ela sera substituida."
            )
            aviso.setWordWrap(True)
            aviso.setStyleSheet(f"color: {COLORS['warn']}; font-size: 11px;")
            lay.addWidget(aviso)

        self._alert_lbl = QLabel("")
        self._alert_lbl.setWordWrap(True)
        self._alert_lbl.setStyleSheet(f"color: {COLORS['danger']}; font-size: 11px;")
        self._alert_lbl.setVisible(False)
        lay.addWidget(self._alert_lbl)

        lay.addSpacing(4)

        brow = QHBoxLayout()
        brow.setSpacing(8)
        b_cancel  = make_secondary_btn("CANCELAR",    110)
        b_confirm = make_primary_btn("CRIAR TAREFA", 130)
        b_cancel.clicked.connect(self.reject)
        b_confirm.clicked.connect(self._criar)
        brow.addStretch()
        brow.addWidget(b_cancel)
        brow.addWidget(b_confirm)
        lay.addLayout(brow)

        self._upd()
        theme_manager.theme_changed.connect(self._upd)

    def _upd(self, _mode: str = ""):
        self.setStyleSheet(
            f"QDialog {{ background: {COLORS['surface']}; color: {COLORS['text']}; }}"
            f"QLabel  {{ background: transparent; color: {COLORS['text_mid']}; }}"
            f"QComboBox, QTimeEdit {{"
            f"  background: {COLORS['surface']}; color: {COLORS['text']};"
            f"  border: 1.5px solid {COLORS['border']};"
            f"  border-radius: 4px; padding: 2px 6px;"
            f"}}"
        )

    def _criar(self):
        freq_map = {0: "DAILY", 1: "WEEKLY", 2: "MONTHLY"}
        freq     = freq_map.get(self._freq_combo.currentIndex(), "DAILY")
        hora     = self._hora_edit.time().toString("HH:mm")
        sucesso, msg = criar_tarefa(
            self._firebird_dir, self._dados_fdb, self._pasta_backup,
            hora=hora, frequencia=freq,
        )
        if sucesso:
            self.accept()
        else:
            self._alert_lbl.setText(msg)
            self._alert_lbl.setVisible(True)


# ---------------------------------------------------------------------------
# Widget de campo com label + linha editavel + botao de selecao
# ---------------------------------------------------------------------------

class _PathField(QWidget):
    """Campo de caminho reutilizavel."""

    def __init__(
        self,
        label_text: str,
        placeholder: str,
        is_dir: bool = True,
        file_filter: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._is_dir      = is_dir
        self._file_filter = file_filter or "Todos os arquivos (*.*)"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        self._lbl  = QLabel(label_text)
        self._edit = QLineEdit()
        self._edit.setPlaceholderText(placeholder)

        self._btn = make_folder_btn(self)
        self._btn.setMaximumWidth(40)
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
            f"color: {COLORS['text']}; font-size: 12px; font-weight: 600;"
        )
        self._edit.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """)

    def _browse(self):
        current = self._edit.text().strip()
        if not current or not os.path.exists(current):
            current = "C:\\"
        if self._is_dir:
            path = QFileDialog.getExistingDirectory(self, "Selecionar pasta", current)
            if path:
                self._edit.setText(os.path.normpath(path))
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Selecionar arquivo", current, self._file_filter
            )
            if path:
                self._edit.setText(os.path.normpath(path))

    @property
    def value(self) -> str:
        return self._edit.text().strip()

    @value.setter
    def value(self, v: str):
        self._edit.setText(v)


# ---------------------------------------------------------------------------
# Aba de Configuracao Compartilhada (Firebird + Banco)
# ---------------------------------------------------------------------------

class _SharedConfigSection(QWidget):
    """Secao compartilhada: Diretorio Firebird + Arquivo .fdb."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: QThread | None = None
        self._versao_fdb_detectada: str = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._alert = AlertBox("Detectando instalacao do Firebird...", "info")
        lay.addWidget(self._alert)

        lay.addWidget(SectionHeader("Configuracao do Firebird"))

        self._fld_firebird = _PathField(
            "Diretorio do Firebird (onde fica o gbak.exe)",
            r"Ex: C:\Program Files\Firebird\Firebird_4_0",
            is_dir=True,
        )
        lay.addWidget(self._fld_firebird)

        # Dispara deteccao do Firebird instalado
        self.iniciar_deteccao()

    # -------------------------------------------------------------------------
    # Deteccao do Firebird instalado
    # -------------------------------------------------------------------------

    def iniciar_deteccao(self):
        self._alert.set_text("Detectando instalacao do Firebird...")
        self._alert.set_kind("info")
        self._worker = _DetectarFirebirdWorker()
        self._worker.finished.connect(
            self._on_deteccao, Qt.ConnectionType.SingleShotConnection
        )
        self._worker.start()

    def _on_deteccao(self, fb_dir: str):
        if not fb_dir:
            fb_dir = self._buscar_firebird_fallback()
        if fb_dir:
            self._fld_firebird.value = fb_dir
            self._alert.set_text(f"Firebird encontrado em: {fb_dir}")
            self._alert.set_kind("success")
        else:
            self._alert.set_text(
                "Nenhuma instalacao do Firebird foi encontrada no computador. "
                "Informe o caminho manualmente."
            )
            self._alert.set_kind("danger")



    @staticmethod
    def _buscar_firebird_fallback() -> str:
        raizes = [
            r"C:\Program Files\Firebird",
            r"C:\Program Files (x86)\Firebird",
            r"C:\Firebird",
        ]
        candidatos = []
        for raiz in raizes:
            if os.path.isdir(raiz):
                for gbak in glob.glob(
                    os.path.join(raiz, "**", "gbak.exe"), recursive=True
                ):
                    candidatos.append(os.path.dirname(gbak))
        if not candidatos:
            return ""
        candidatos.sort(reverse=True)
        return candidatos[0]

    # -------------------------------------------------------------------------
    # Validacao base
    # -------------------------------------------------------------------------

    def validar_base(self) -> str | None:
        """Valida apenas o diretorio do Firebird (comum a backup e restaure)."""
        if not self._fld_firebird.value:
            return "Informe o diretorio do Firebird."
        gbak = os.path.join(self._fld_firebird.value, "gbak.exe")
        if not os.path.isfile(gbak):
            return f"gbak.exe nao encontrado em: {self._fld_firebird.value}"
        return None

    # -------------------------------------------------------------------------
    # Propriedades publicas
    # -------------------------------------------------------------------------

    @property
    def firebird_dir(self) -> str:
        return self._fld_firebird.value

    def set_alert_text(self, text: str, kind: str = "danger"):
        self._alert.set_text(text)
        self._alert.set_kind(kind)


# ---------------------------------------------------------------------------
# Aba de Backup
# ---------------------------------------------------------------------------

class _TabBackup(QWidget):
    go_backup = pyqtSignal()
    finished  = pyqtSignal(bool, dict)

    def __init__(self, shared: _SharedConfigSection, parent=None):
        super().__init__(parent)
        self._shared  = shared
        self._worker: BackupGbakWorker | None = None
        self._versao_fdb_detectada: str = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(8)

        lay.addWidget(SectionHeader("Banco de Dados"))

        self._fld_dados = _PathField(
            "Arquivo do banco de dados (.fdb)",
            r"Ex: C:\Futura\Dados\DADOS.fdb",
            is_dir=False,
            file_filter="Banco Firebird (*.fdb);;Todos os arquivos (*.*)",
        )
        lay.addWidget(self._fld_dados)

        self._alert_versao_fdb = AlertBox("", "info")
        self._alert_versao_fdb.setVisible(False)
        lay.addWidget(self._alert_versao_fdb)

        self._fld_dados._edit.textChanged.connect(self._on_fdb_changed)

        lay.addWidget(SectionHeader("Destino do Backup"))

        self._fld_backup_dir = _PathField(
            "Pasta de destino dos backups (.bck)",
            r"Ex: C:\Futura\Backup",
            is_dir=True,
        )
        lay.addWidget(self._fld_backup_dir)

        # --- Progresso e log (ocultos ate iniciar) ---
        self._progress = ProgressBlock("Backup via GBAK")
        self._progress.setVisible(False)
        lay.addWidget(self._progress)

        self._console = LogConsole(max_height=0)
        self._console.setVisible(False)
        lay.addWidget(self._console, 1)

        lay.addWidget(h_line())

        footer_lay = QHBoxLayout()
        footer_lay.setContentsMargins(0, 6, 0, 0)
        footer_lay.setSpacing(10)

        self._btn_backup = make_primary_btn("INICIAR BACKUP", 200)
        self._btn_backup.clicked.connect(self._on_backup)
        footer_lay.addWidget(self._btn_backup)

        self._btn_cancel = make_secondary_btn("CANCELAR", 130)
        self._btn_cancel.clicked.connect(self._cancelar)
        self._btn_cancel.setVisible(False)
        footer_lay.addWidget(self._btn_cancel)

        footer_lay.addStretch()
        lay.addLayout(footer_lay)

        theme_manager.theme_changed.connect(self._upd)
        self._upd()



    # -------------------------------------------------------------------------
    # Deteccao de versao pelo ODS do .fdb
    # -------------------------------------------------------------------------

    def _on_fdb_changed(self, texto: str):
        path = texto.strip()
        if path and os.path.isfile(path) and path.lower().endswith(".fdb"):
            self._detectar_versao_pelo_fdb(path)
        else:
            self._versao_fdb_detectada = ""
            self._alert_versao_fdb.setVisible(False)

    def _detectar_versao_pelo_fdb(self, path: str):
        ods = _ler_ods_fdb(path)
        if ods is None:
            self._versao_fdb_detectada = ""
            self._alert_versao_fdb.set_text(
                "Nao foi possivel ler o cabecalho do arquivo .fdb."
            )
            self._alert_versao_fdb.set_kind("warn")
            self._alert_versao_fdb.setVisible(True)
            return

        ods_major, ods_minor = ods
        versao = _versao_pelo_ods(ods_major)
        self._versao_fdb_detectada = versao

        self._alert_versao_fdb.set_text(
            f"Banco criado com {versao}  (ODS {ods_major}.{ods_minor})  "
            f"— o gbak.exe precisa ser da mesma versao."
        )
        self._alert_versao_fdb.set_kind("info")
        self._alert_versao_fdb.setVisible(True)
        self._sugerir_firebird_para_versao(versao)

    def _sugerir_firebird_para_versao(self, versao: str):
        hints = _VERSAO_DIR_HINT.get(versao, [])
        if not hints:
            return
        atual = self._shared.firebird_dir
        if atual and any(h in atual.lower() for h in hints):
            return
        raizes = [
            r"C:\Program Files\Firebird",
            r"C:\Program Files (x86)\Firebird",
            r"C:\Firebird",
        ]
        candidatos = []
        for raiz in raizes:
            if os.path.isdir(raiz):
                for gbak in glob.glob(
                    os.path.join(raiz, "**", "gbak.exe"), recursive=True
                ):
                    dir_gbak = os.path.dirname(gbak)
                    if any(h in dir_gbak.lower() for h in hints):
                        candidatos.append(dir_gbak)
        if candidatos:
            candidatos.sort(reverse=True)
            self._shared._fld_firebird.value = candidatos[0]
            self._shared.set_alert_text(f"{versao} encontrado em: {candidatos[0]}", "success")
        else:
            self._shared.set_alert_text(
                f"Nenhuma instalacao do {versao} encontrada. "
                f"Informe o caminho do gbak.exe manualmente.", "danger"
            )

    # -------------------------------------------------------------------------

    def _upd(self, _mode: str = ""):
        pass

    def _validar(self) -> str | None:
        err = self._shared.validar_base()
        if err:
            return err
        if not self._fld_dados.value:
            return "Informe o arquivo do banco de dados (.fdb)."
        if not os.path.isfile(self._fld_dados.value):
            return f"Arquivo .fdb nao encontrado: {self._fld_dados.value}"
        if not self._fld_backup_dir.value:
            return "Informe a pasta de destino dos backups."
        if self._versao_fdb_detectada:
            hints    = _VERSAO_DIR_HINT.get(self._versao_fdb_detectada, [])
            fb_lower = self._shared.firebird_dir.lower()
            if hints and not any(h in fb_lower for h in hints):
                return (
                    f"ATENCAO: o banco e {self._versao_fdb_detectada}, mas o "
                    f"diretorio do gbak informado pode nao ser compativel.\n"
                    f"Verifique se o gbak.exe e da versao correta antes de continuar."
                )
        return None

    def _on_backup(self):
        err = self._validar()
        if err:
            self._shared.set_alert_text(err, "danger")
            return

        dados_fdb = self._fld_dados.value
        bck_dest  = gerar_nome_backup(self._fld_backup_dir.value)
        versao    = self._versao_fdb_detectada

        dlg = ConfirmDialog(
            "Iniciar Backup do Banco de Dados",
            [
                f"Banco de origem:    {dados_fdb}",
                f"Destino do backup:  {bck_dest}",
                *(
                    [f"Versao detectada:   {versao}"]
                    if versao else []
                ),
                "",
                "O Firebird sera pausado durante o processo.",
                "O banco sera renomeado temporariamente durante o backup.",
            ],
            self,
        )
        dlg.exec()
        if dlg.confirmado():
            self.go_backup.emit()
            self._iniciar_worker(dados_fdb, bck_dest)

    def _iniciar_worker(self, dados_fdb: str, bck_dest: str):
        self._console.clear_console()
        self._progress.set_progress(0, "Iniciando backup...")
        self._progress.setVisible(True)
        self._console.setVisible(True)
        self._btn_backup.setEnabled(False)
        self._btn_cancel.setVisible(True)
        self._btn_cancel.setEnabled(True)

        firebird_dir = self._shared.firebird_dir
        self._worker = BackupGbakWorker(firebird_dir, dados_fdb, bck_dest)
        self._worker.log_line.connect(self._console.append_line)
        self._worker.progress.connect(
            lambda pct, t, d: self._progress.set_progress(pct, f"{t}  {d}".strip())
        )
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self, sucesso: bool, info: dict):
        self._btn_backup.setEnabled(True)
        self._btn_cancel.setVisible(False)
        self._worker = None
        self.finished.emit(sucesso, info)

    def _cancelar(self):
        if self._worker:
            self._btn_cancel.setEnabled(False)
            self._worker.stop()
            self._worker.wait(3000)

    @property
    def pasta_backup(self) -> str:
        return self._fld_backup_dir.value

    @property
    def dados_fdb(self) -> str:
        return self._fld_dados.value

    @property
    def dados_novo_fdb(self) -> str:
        return _derivar_dados_novo(self._fld_dados.value)

    @property
    def versao_detectada(self) -> str:
        return self._versao_fdb_detectada


# ---------------------------------------------------------------------------
# Aba de Restaure
# ---------------------------------------------------------------------------

class _TabRestaure(QWidget):
    go_restaure = pyqtSignal()
    finished    = pyqtSignal(bool, dict)

    def __init__(self, shared: _SharedConfigSection, parent=None):
        super().__init__(parent)
        self._shared   = shared
        self._worker: RestaureGbakWorker | None = None
        self._bck_selecionado: str = ""   # caminho completo do .bck escolhido
        self._btn_itens: list[QPushButton] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(8)

        # --- Pasta de backups ---
        lay.addWidget(SectionHeader("Pasta de Backups"))

        self._fld_backup_dir = _PathField(
            "Pasta dos backups (.bck)",
            r"Ex: C:\Futura\Backup",
            is_dir=True,
        )
        lay.addWidget(self._fld_backup_dir)

        # Ao mudar a pasta, recarrega a lista automaticamente
        self._fld_backup_dir._edit.textChanged.connect(
            lambda _: self._carregar_lista()
        )

        # --- Lista de backups disponiveis ---
        self._lista_widget = QWidget()
        self._lista_layout = QVBoxLayout(self._lista_widget)
        self._lista_layout.setContentsMargins(0, 0, 0, 0)
        self._lista_layout.setSpacing(3)

        self._scroll_lista = QScrollArea()
        self._scroll_lista.setWidgetResizable(True)
        self._scroll_lista.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll_lista.setFixedHeight(180)
        self._scroll_lista.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_lista.setWidget(self._lista_widget)
        lay.addWidget(self._scroll_lista)

        # --- Banco de dados destino ---
        lay.addWidget(SectionHeader("Banco de Dados Restaurado"))

        self._fld_dados_novo = _PathField(
            "Arquivo de destino (.fdb)",
            r"Ex: C:\Futura\Dados\DADOS_NOVO.fdb",
            is_dir=False,
            file_filter="Banco Firebird (*.fdb);;Todos os arquivos (*.*)",
        )
        lay.addWidget(self._fld_dados_novo)

        # --- Progresso e log (ocultos ate iniciar) ---
        self._progress = ProgressBlock("Restaure via GBAK")
        self._progress.setVisible(False)
        lay.addWidget(self._progress)

        self._console = LogConsole(max_height=0)
        self._console.setVisible(False)
        lay.addWidget(self._console, 1)

        lay.addWidget(h_line())

        footer_lay = QHBoxLayout()
        footer_lay.setContentsMargins(0, 6, 0, 0)
        footer_lay.setSpacing(10)

        self._btn_restaure = make_primary_btn("INICIAR RESTAURE", 200)
        self._btn_restaure.clicked.connect(self._on_restaure)
        footer_lay.addWidget(self._btn_restaure)

        self._btn_cancel = make_secondary_btn("CANCELAR", 130)
        self._btn_cancel.clicked.connect(self._cancelar)
        self._btn_cancel.setVisible(False)
        footer_lay.addWidget(self._btn_cancel)

        footer_lay.addStretch()
        lay.addLayout(footer_lay)

        theme_manager.theme_changed.connect(self._upd)
        self._upd()

        # Carrega lista inicial
        self._carregar_lista()

    # -------------------------------------------------------------------------
    # Lista de backups
    # -------------------------------------------------------------------------

    def _carregar_lista(self):
        """Varre a pasta e recria os itens da lista."""
        # Limpa itens anteriores
        while self._lista_layout.count():
            item = self._lista_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._bck_selecionado = ""
        self._btn_itens: list[QPushButton] = []

        pasta = self._fld_backup_dir.value
        if not pasta or not os.path.isdir(pasta):
            self._scroll_lista.setVisible(False)
            return

        arquivos = sorted(
            [
                os.path.join(pasta, f)
                for f in os.listdir(pasta)
                if f.lower().endswith(".bck") and os.path.isfile(os.path.join(pasta, f))
            ],
            key=os.path.getmtime,
            reverse=True,  # mais recente primeiro
        )

        if not arquivos:
            self._scroll_lista.setVisible(False)
            return

        self._label_vazio.setVisible(False)
        self._scroll_lista.setVisible(True)

        for idx, path in enumerate(arquivos):
            nome     = os.path.basename(path)
            tamanho  = _fmt_size(os.path.getsize(path))
            mtime    = os.path.getmtime(path)
            from datetime import datetime
            data_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y  %H:%M")

            btn = QPushButton(f"  {nome}    {tamanho}    {data_str}")
            btn.setCheckable(True)
            btn.setProperty("bck_path", path)
            btn.clicked.connect(lambda checked, p=path, b=btn: self._selecionar(p, b))
            self._btn_itens.append(btn)
            self._lista_layout.addWidget(btn)

            # Seleciona automaticamente o mais recente
            if idx == 0:
                self._selecionar(path, btn)

        self._lista_layout.addStretch()
        self._upd()

    def _selecionar(self, path: str, btn_clicado: QPushButton):
        """Marca o item selecionado e desmarca os outros."""
        self._bck_selecionado = path
        for b in self._btn_itens:
            b.setChecked(b is btn_clicado)
        self._upd_itens()


    def _upd_itens(self):
        for b in self._btn_itens:
            if b.isChecked():
                b.setStyleSheet(f"""
                    QPushButton {{
                        background: {COLORS['accent']};
                        color: #ffffff;
                        border: 1.5px solid {COLORS['accent']};
                        border-radius: 6px;
                        padding: 6px 12px;
                        font-size: 11px;
                        text-align: left;
                    }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background: {COLORS['surface']};
                        color: {COLORS['text']};
                        border: 1px solid {COLORS['border']};
                        border-radius: 6px;
                        padding: 6px 12px;
                        font-size: 11px;
                        text-align: left;
                    }}
                    QPushButton:hover {{
                        background: {COLORS['border']};
                    }}
                """)

    # -------------------------------------------------------------------------

    def _upd(self, _mode: str = ""):
        self._scroll_lista.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: {COLORS['surface']};
                width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['border']};
                border-radius: 3px;
            }}
        """)
        self._upd_itens()

    def _validar(self) -> str | None:
        err = self._shared.validar_base()
        if err:
            return err
        if not self._bck_selecionado:
            return "Selecione um arquivo de backup para restaurar."
        if not os.path.isfile(self._bck_selecionado):
            return f"Arquivo de backup nao encontrado: {self._bck_selecionado}"
        if not self._fld_dados_novo.value:
            return "Informe o arquivo de destino do banco restaurado (.fdb)."
        return None

    def _on_restaure(self):
        err = self._validar()
        if err:
            self._shared.set_alert_text(err, "danger")
            return

        dados_novo = self._fld_dados_novo.value
        nome_bck   = os.path.basename(self._bck_selecionado)

        dlg = ConfirmDialog(
            "Iniciar Restaure do Banco de Dados",
            [
                f"Arquivo de backup:  {nome_bck}",
                f"Banco restaurado:   {dados_novo}",
                "",
                "O banco original NAO sera alterado.",
            ],
            self,
        )
        dlg.exec()
        if dlg.confirmado():
            self.go_restaure.emit()
            self._iniciar_worker(self._bck_selecionado, dados_novo)

    def _iniciar_worker(self, bck_file: str, dados_novo: str):
        self._console.clear_console()
        self._progress.set_progress(0, "Iniciando restaure...")
        self._progress.setVisible(True)
        self._console.setVisible(True)
        self._btn_restaure.setEnabled(False)
        self._btn_cancel.setVisible(True)
        self._btn_cancel.setEnabled(True)

        firebird_dir = self._shared.firebird_dir

        if self._worker is not None:
            try:
                self._worker.finished.disconnect(self._on_worker_finished)
            except RuntimeError:
                pass
            self._worker = None

        self._worker = RestaureGbakWorker(firebird_dir, bck_file, dados_novo)
        self._worker.log_line.connect(self._console.append_line)
        self._worker.progress.connect(
            lambda pct, t, d: self._progress.set_progress(pct, f"{t}  {d}".strip())
        )
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self, sucesso: bool, info: dict):
        self._btn_restaure.setEnabled(True)
        self._btn_cancel.setVisible(False)
        self._worker = None
        self.finished.emit(sucesso, info)

    def _cancelar(self):
        if self._worker:
            self._btn_cancel.setEnabled(False)
            self._worker.stop()
            self._worker.wait(3000)

    @property
    def pasta_backup(self) -> str:
        return self._fld_backup_dir.value

    @property
    def bck_especifico(self) -> str:
        return self._bck_selecionado

    @property
    def dados_novo_fdb(self) -> str:
        return self._fld_dados_novo.value


# ---------------------------------------------------------------------------
# Step 0 - Configuracao com abas Backup | Restaure
# ---------------------------------------------------------------------------

class _StepConfig(QWidget):
    go_backup   = pyqtSignal()
    go_restaure = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        lay   = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 16, 0)
        lay.setSpacing(8)

        # Secao compartilhada (Firebird + .fdb) — aparece acima das abas
        self._shared = _SharedConfigSection()
        lay.addWidget(self._shared)

        lay.addWidget(h_line())

        # Abas: Backup | Restaure
        self._tabs = QTabWidget()
        self._tab_backup   = _TabBackup(self._shared)
        self._tab_restaure = _TabRestaure(self._shared)
        self._tabs.addTab(self._tab_backup,   "  Backup  ")
        self._tabs.addTab(self._tab_restaure, "  Restaure  ")
        lay.addWidget(self._tabs)

        lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # Conexoes das abas para os sinais da pagina
        self._tab_backup.go_backup.connect(self.go_backup)
        self._tab_restaure.go_restaure.connect(self.go_restaure)

        theme_manager.theme_changed.connect(self._upd_tabs)
        self._upd_tabs()

    def _upd_tabs(self, _mode: str = ""):
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {COLORS['border']};
                border-radius: 0 6px 6px 6px;
                background: transparent;
            }}
            QTabBar::tab {{
                background: {COLORS['surface']};
                color: {COLORS['text_mid']};
                border: 1px solid {COLORS['border']};
                border-bottom: none;
                padding: 6px 20px;
                font-size: 12px;
                font-weight: 600;
                margin-right: 2px;
                border-radius: 6px 6px 0 0;
            }}
            QTabBar::tab:selected {{
                background: {COLORS['accent']};
                color: #ffffff;
                border-color: {COLORS['accent']};
            }}
            QTabBar::tab:hover:!selected {{
                background: {COLORS['border']};
                color: {COLORS['text']};
            }}
        """)

    # --- Propriedades publicas (compatibilidade com PageBackupGbak) ---

    @property
    def firebird_dir(self) -> str:
        return self._shared.firebird_dir

    @property
    def dados_fdb(self) -> str:
        return self._tab_backup.dados_fdb

    @property
    def dados_novo_fdb(self) -> str:
        idx = self._tabs.currentIndex()
        if idx == 1:
            return self._tab_restaure.dados_novo_fdb
        return self._tab_backup.dados_novo_fdb

    @property
    def pasta_backup(self) -> str:
        idx = self._tabs.currentIndex()
        if idx == 0:
            return self._tab_backup.pasta_backup
        return self._tab_restaure.pasta_backup

    @property
    def bck_especifico(self) -> str:
        return self._tab_restaure.bck_especifico

    def set_aba_restaure(self):
        self._tabs.setCurrentIndex(1)

    def set_aba_backup(self):
        self._tabs.setCurrentIndex(0)


# ---------------------------------------------------------------------------
# Step 2 - Resultado
# ---------------------------------------------------------------------------

class _StepResultado(QWidget):
    go_menu          = pyqtSignal()
    iniciar_restaure = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self._alert      = AlertBox("", "success")
        self._result_box = ResultBox("Detalhes", [], "success")
        self._nota       = label("", COLORS["text_mid"], 11)
        self._nota.setWordWrap(True)

        lay.addWidget(self._alert)
        lay.addWidget(self._result_box)
        lay.addWidget(self._nota)
        lay.addStretch()
        lay.addWidget(h_line())

        self._btn_menu = make_secondary_btn("MENU PRINCIPAL", 160)
        self._btn_menu.clicked.connect(self.go_menu.emit)

        self._btn_restaure = make_primary_btn("INICIAR RESTAURE", 200)
        self._btn_restaure.clicked.connect(self._on_iniciar_restaure)
        self._btn_restaure.setVisible(False)

        self._ultimo_bck: str = ""

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addWidget(self._btn_menu)
        btns.addWidget(self._btn_restaure)
        btns.addStretch()

        btn_w = QWidget()
        btn_w.setLayout(btns)
        btn_w.setStyleSheet("background: transparent;")
        lay.addWidget(btn_w)

        theme_manager.theme_changed.connect(self._upd)
        self._upd()

    def _upd(self, _mode: str = ""):
        self._nota.setStyleSheet(f"color: {COLORS['text_mid']}; font-size: 11px;")

    def _on_iniciar_restaure(self):
        self.iniciar_restaure.emit(self._ultimo_bck)

    def set_resultado(self, operacao: str, sucesso: bool, info: dict):
        lay = self.layout()
        lay.removeWidget(self._result_box)
        self._result_box.deleteLater()

        mostrar_restaure = (operacao == "Backup" and sucesso)
        self._btn_restaure.setVisible(mostrar_restaure)
        self._ultimo_bck = info.get("backup_path", "") if mostrar_restaure else ""

        if sucesso:
            self._alert.set_text(f"{operacao} concluido com sucesso!")
            self._alert.set_kind("success")
            rows = []
            if "backup_path" in info:
                rows.append(("Arquivo gerado",   info["backup_path"]))
            if "dados_novo" in info:
                rows.append(("Banco restaurado", info["dados_novo"]))
            if "tamanho" in info:
                rows.append(("Tamanho",          _fmt_size(info["tamanho"])))
            self._result_box = ResultBox(f"Resultado do {operacao}", rows, "success")
            if operacao == "Restaure":
                self._nota.setText(
                    "O arquivo _NOVO.fdb foi gerado com sucesso na mesma pasta do banco original. "
                    "O banco original nao foi alterado.\n"
                    "Revise o banco restaurado antes de substituir o banco em producao."
                )
            else:
                self._nota.setText("")
        else:
            cancelado = info.get("cancelado", False)
            self._alert.set_text(
                f"{operacao} cancelado." if cancelado else f"{operacao} falhou."
            )
            self._alert.set_kind("warn" if cancelado else "danger")
            self._result_box = ResultBox(
                f"Resultado do {operacao}", [], "warning" if cancelado else "error"
            )
            self._nota.setText("")

        lay.insertWidget(1, self._result_box)


# ---------------------------------------------------------------------------
# PageBackupGbak - pagina principal
# ---------------------------------------------------------------------------

class PageBackupGbak(QWidget):
    go_menu = pyqtSignal()

    _IDX_CONFIG = 0
    _IDX_RESULT = 1

    def __init__(self, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = PageHeader("BACKUP / RESTAURE", "Geração e restauração de backups via GBAK")
        self._header.back_clicked.connect(self.go_menu.emit)
        root.addWidget(self._header)

        content_w = QWidget()
        content_lay = QVBoxLayout(content_w)
        content_lay.setContentsMargins(40, 20, 40, 20)
        content_lay.setSpacing(8)

        self._stack = QStackedWidget()

        self._cfg       = _StepConfig()
        self._resultado = _StepResultado()

        self._stack.addWidget(self._cfg)        # idx 0
        self._stack.addWidget(self._resultado)  # idx 1

        content_lay.addWidget(self._stack)
        root.addWidget(content_w, 1)

        # Conexoes
        self._cfg._tab_backup.finished.connect(self._on_backup_finished)
        self._cfg._tab_restaure.finished.connect(self._on_restaure_finished)
        self._resultado.go_menu.connect(self._on_go_menu)
        self._resultado.iniciar_restaure.connect(self._on_iniciar_restaure_do_resultado)

    def reset(self):
        self._stack.setCurrentIndex(self._IDX_CONFIG)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self._stack.currentIndex() == self._IDX_CONFIG:
                self.go_menu.emit()
        else:
            super().keyPressEvent(event)

    def _on_backup_finished(self, sucesso: bool, info: dict):
        self._resultado.set_resultado("Backup", sucesso, info)
        self._stack.setCurrentIndex(self._IDX_RESULT)

    def _on_restaure_finished(self, sucesso: bool, info: dict):
        self._resultado.set_resultado("Restaure", sucesso, info)
        self._stack.setCurrentIndex(self._IDX_RESULT)

    def _on_go_menu(self):
        self._stack.setCurrentIndex(self._IDX_CONFIG)
        self.go_menu.emit()

    def _on_iniciar_restaure_do_resultado(self, bck_path: str):
        """Botao 'Iniciar Restaure' na tela de resultado: volta para config na aba restaure."""
        self._cfg.set_aba_restaure()
        self._stack.setCurrentIndex(self._IDX_CONFIG)