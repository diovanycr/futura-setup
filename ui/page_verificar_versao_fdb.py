# =============================================================================
# FUTURA SETUP — Página: Verificar Versão + Download de Atualização
# Salvar em: ui/page_verificar_versao_fdb.py
# =============================================================================
from __future__ import annotations

import os
import re
import shutil
import socket
import zipfile
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from PyQt6.QtCore    import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui     import QFont, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QFileDialog, QLabel, QFrame,
    QScrollArea, QPushButton, QApplication,
    QTabWidget, QCheckBox, QProgressBar,
)

from ui.theme         import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets       import (
    PageHeader, SectionHeader, AlertBox,
    make_primary_btn, make_secondary_btn, make_folder_btn,
    btn_row, spacer, h_line, label, BusyOverlay,
)
from ui.components.database_widgets import (
    DatabasePathField as _PathFieldDB,
    DatabaseDropArea as _DropArea,
    DatabaseResultCard as _ResultCard
)
from core.firebird_version_check import verificar_versao_fdb

_DEFAULT_USER     = "SYSDBA"
_DEFAULT_PASSWORD = "sbofutura"
_BASE_URL         = "https://www.futurasistemas.com.br/Web/arquivos/atualizacao/new/"
_DLL_URL          = (
    "https://repositorio.futurasistemas.com.br/download.php"
    "?dirfisico=D:/Backup//repositorio//01%20-%20DLLs%20Sistema/atual/32/DLLx86.zip"
    "&caminho=https://repositorio.futurasistemas.com.br/repositorio/01%20-%20DLLs%20Sistema/atual/32/DLLx86.zip"
    "&filename=DLLx86.zip"
)


# =============================================================================
# Workers
# =============================================================================

class _VerificarWorker(QThread):
    concluido = pyqtSignal(dict)
    erro      = pyqtSignal(str)

    def __init__(self, path: str, user: str, password: str):
        super().__init__()
        self._path, self._user, self._password = path, user, password

    def run(self):
        try:
            result = verificar_versao_fdb(
                self._path, user=self._user,
                password=self._password, rodar_gfix=True,
            )
            self.concluido.emit(result)
        except Exception as e:
            self.erro.emit(str(e))


class _VarreduraWorker(QThread):
    concluido = pyqtSignal(dict)
    erro      = pyqtSignal(str)

    def __init__(self, versao_manual: str = ""):
        super().__init__()
        self._versao_manual = versao_manual.strip()

    def run(self):
        try:
            r = requests.get(_BASE_URL, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            todas = [
                a.get_text(strip=True).strip("/") for a in soup.find_all("a")
                if re.match(r"\d{4}\.\d{2}", a.get_text(strip=True))
            ]
            if not todas:
                self.erro.emit("Nenhuma versao encontrada em " + _BASE_URL)
                return

            if self._versao_manual:
                filtradas = [v for v in todas if v.startswith(self._versao_manual)]
                if not filtradas:
                    self.erro.emit(
                        f"Nenhuma versao encontrada para '{self._versao_manual}'. "
                        f"Versoes disponiveis: {', '.join(sorted(todas)[-5:])}"
                    )
                    return
                versao = sorted(filtradas)[-1]
            else:
                versao = sorted(todas)[-1]

            url_versao = _BASE_URL + versao + "/"
            r = requests.get(url_versao, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            sistemas_links = [
                a.get_text(strip=True).strip("/") for a in soup.find_all("a")
                if a.get_text(strip=True) not in ("", "Parent Directory")
                and not a.get_text(strip=True).startswith("?")
                and a.get_text(strip=True).strip("/").isupper()
            ]

            resultado = {"versao": versao, "sistemas": {}}
            for sistema in sistemas_links:
                url_sis = url_versao + sistema + "/"
                try:
                    r2 = requests.get(url_sis, timeout=10)
                    soup2 = BeautifulSoup(r2.text, "html.parser")
                    subpastas = [
                        a.get_text(strip=True).strip("/") for a in soup2.find_all("a")
                        if a.get_text(strip=True) not in ("", "Parent Directory")
                        and not a.get_text(strip=True).startswith("?")
                        and "/" not in a.get_text(strip=True).strip("/")
                        and not a.get_text(strip=True).endswith(".zip")
                        and a.get_text(strip=True).strip("/").upper() != "GENERICO"
                    ]
                    resultado["sistemas"][sistema] = {}
                    for sub in subpastas:
                        url_sub = url_sis + sub + "/"
                        try:
                            r3 = requests.get(url_sub, timeout=10)
                            soup3 = BeautifulSoup(r3.text, "html.parser")
                            arquivos = [
                                a.get_text(strip=True) for a in soup3.find_all("a")
                                if a.get_text(strip=True).endswith(".zip")
                            ]
                            if arquivos:
                                mais_recente = sorted(arquivos)[-1]
                                resultado["sistemas"][sistema][sub] = {
                                    "arquivo": mais_recente,
                                    "url": url_sub + mais_recente,
                                }
                        except Exception:
                            pass
                except Exception:
                    pass

            self.concluido.emit(resultado)
        except Exception as e:
            self.erro.emit(str(e))


class _DownloadWorker(QThread):
    progresso  = pyqtSignal(str, int)
    concluido  = pyqtSignal(str)
    erro       = pyqtSignal(str)

    def __init__(self, itens: list[dict], pasta: str, baixar_dll: bool, gerar_ini: bool = True):
        super().__init__()
        self._itens      = itens
        self._pasta      = pasta
        self._baixar_dll = baixar_dll
        self._gerar_ini  = gerar_ini

    def run(self):
        try:
            if os.path.isdir(self._pasta):
                conteudo = [f for f in os.listdir(self._pasta) if not f.startswith("_backup_")]
                if conteudo:
                    data_str  = datetime.now().strftime("%Y%m%d_%H%M%S")
                    pasta_bkp = os.path.join(self._pasta, f"_backup_{data_str}")
                    self.progresso.emit("Criando backup da pasta existente...", 0)
                    try:
                        os.makedirs(pasta_bkp, exist_ok=True)
                        for nome in conteudo:
                            origem  = os.path.join(self._pasta, nome)
                            destino = os.path.join(pasta_bkp, nome)
                            shutil.move(origem, destino)
                        self.progresso.emit(f"Arquivos movidos para: _backup_{data_str}", 2)
                    except Exception as e_bkp:
                        self.erro.emit(
                            f"Falha ao criar backup — download cancelado.\n"
                            f"Erro: {e_bkp}\n\n"
                            f"Verifique se os arquivos nao estao em uso e tente novamente."
                        )
                        return

            os.makedirs(self._pasta, exist_ok=True)
            total = len(self._itens) + (1 if self._baixar_dll else 0)
            feito = 0

            for item in self._itens:
                self.progresso.emit(f"Baixando {item['nome']}...", int(feito / total * 100))
                zip_path = os.path.join(self._pasta, item["nome"])
                self._baixar(item["url"], zip_path)
                self.progresso.emit(f"Extraindo {item['nome']}...", int(feito / total * 100))
                self._extrair(zip_path, self._pasta)
                os.remove(zip_path)
                feito += 1

            if self._baixar_dll:
                self.progresso.emit("Baixando DLLs...", int(feito / total * 100))
                dll_path = os.path.join(self._pasta, "DLLx86.zip")
                self._baixar(_DLL_URL, dll_path)
                self.progresso.emit("Extraindo DLLs...", 95)
                self._extrair(dll_path, self._pasta)
                os.remove(dll_path)

            if self._gerar_ini:
                self.progresso.emit("Gerando Futura.ini...", 98)
                self._gerar_futura_ini(self._pasta)

            self.progresso.emit("Concluido!", 100)
            self.concluido.emit(self._pasta)
        except Exception as e:
            self.erro.emit(str(e))

    def _gerar_futura_ini(self, pasta: str):
        nome_maquina = socket.gethostname()
        pasta_backup = os.path.join(pasta, "Backup")
        os.makedirs(pasta_backup, exist_ok=True)
        backup_path  = pasta_backup + os.sep
        conteudo = (
            "[GERAL]\n"
            "EMPRESA_DEFAULT=1\n"
            "QTDE_BASE=1\n"
            "BASE_DEFAULT=1\n"
            "BASE_OPCIONAL=1\n"
            "[BASE_01]\n"
            "\n"
            "FIREBIRD_PORTA=3050\n"
            "DADOS_ALIAS=Dados\n"
            f"DADOS_IP={nome_maquina}\n"
            "DADOS_PATH=Dados\n"
            f"CEP_IP={nome_maquina}\n"
            "CEP_PATH=CEP\n"
            f"BACKUP_PATH={backup_path}\n"
        )
        with open(os.path.join(pasta, "Futura.ini"), "w", encoding="utf-8") as f:
            f.write(conteudo)

    def _baixar(self, url: str, dest: str):
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    def _extrair(self, zip_path: str, dest: str):
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(dest)


# Componentes movidos para database_widgets.py


class _AbaVerificar(QWidget):
    ir_para_download = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._worker: QThread | None = None
        self._build_ui()
        theme_manager.theme_changed.connect(self._upd_drop_style)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(24, 24, 24, 20)
        lay.setSpacing(10)

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

        self._btn_ir_download = make_secondary_btn("Baixar Atualizacao", 180)
        self._btn_ir_download.setVisible(False)
        self._btn_ir_download.clicked.connect(self._on_ir_download)

        lay.addWidget(btn_row(self._btn_verificar, self._btn_ir_download))
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

    def _on_arquivo_solto(self, path):
        self._fld_db.value = path

    def _on_verificar(self):
        path = self._fld_db.value
        if not path:
            self._mostrar_alerta("Informe o caminho de um arquivo .fdb.", "warn")
            return
        self._btn_verificar.setEnabled(False)
        self._card_result.setVisible(False)
        self._alert.setVisible(False)
        self._overlay.show_with("Validando banco com gfix... aguarde.")

        worker = _VerificarWorker(path, _DEFAULT_USER, _DEFAULT_PASSWORD)
        worker.concluido.connect(self._on_concluido)
        worker.erro.connect(self._on_erro)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _on_concluido(self, result):
        self._overlay.hide_spinner()
        self._btn_verificar.setEnabled(True)
        if not result["ok"]:
            self._mostrar_alerta(f"Erro: {result['erro']}", "error")
            return
        self._alert.setVisible(False)
        self._card_result.atualizar(result, self._fld_db.value)
        self._card_result.setVisible(True)

        versao = result.get("versao_futura", "")
        if versao:
            self._btn_ir_download.setText(f"Baixar Atualizacao {versao}")
            self._btn_ir_download.setVisible(True)
        else:
            self._btn_ir_download.setVisible(False)

    def _on_erro(self, msg):
        self._overlay.hide_spinner()
        self._btn_verificar.setEnabled(True)
        self._mostrar_alerta(f"Erro: {msg}", "error")

    def _mostrar_alerta(self, txt, kind):
        self._alert.set_text(txt)
        self._alert.set_kind(kind)
        self._alert.setVisible(True)

    def _on_ir_download(self):
        versao = self._card_result._result_cache.get("versao_futura", "")
        if versao:
            self.ir_para_download.emit(versao)

    def _upd_drop_style(self, _mode=""):
        self._drop_area.atualizar_estilo()

    def reset(self):
        self._fld_db.value = ""
        self._alert.setVisible(False)
        self._card_result.setVisible(False)
        self._btn_verificar.setEnabled(True)
        self._btn_ir_download.setVisible(False)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            self._on_arquivo_solto(urls[0].toLocalFile())


# =============================================================================
# Aba 2 — Download de Atualização
# =============================================================================

class _CheckItem(QWidget):
    def __init__(self, sistema: str, subpasta: str, arquivo: str, url: str, parent=None):
        super().__init__(parent)
        self.sistema  = sistema
        self.subpasta = subpasta
        self.arquivo  = arquivo
        self.url      = url

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(8)

        self._chk = QCheckBox()
        self._chk.setChecked(True)

        lbl_sistema = QLabel(subpasta)
        lbl_sistema.setFont(QFont(FONT_MONO, 9, QFont.Weight.Bold))
        lbl_sistema.setStyleSheet(f"color: {COLORS.get('accent','#00c2ff')}; background: transparent;")
        lbl_sistema.setFixedWidth(220)

        lbl_arq = QLabel(arquivo)
        lbl_arq.setFont(QFont(FONT_MONO, 9))
        lbl_arq.setStyleSheet(f"color: {COLORS.get('text','#eee')}; background: transparent;")
        lbl_arq.setMinimumWidth(200)

        lay.addWidget(self._chk)
        lay.addWidget(lbl_sistema)
        lay.addWidget(lbl_arq, 1)

    @property
    def selecionado(self) -> bool:
        return self._chk.isChecked()


class _AbaDownload(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: QThread | None = None
        self._itens_ui: list[_CheckItem] = []
        self._id_cliente: str = ""
        self._versao_futura: str = ""
        self._build_ui()

    def definir_contexto(self, id_cliente: str, versao_futura: str):
        self._id_cliente    = id_cliente.strip()
        self._versao_futura = versao_futura.strip()
        self._atualizar_pasta_padrao()

    def _pasta_padrao(self) -> str:
        id_part  = self._id_cliente   if self._id_cliente   else "0000"
        ver_part = self._versao_futura if self._versao_futura else "0000.00"
        return rf"C:\Futura_{id_part}_{ver_part}"

    def _atualizar_pasta_padrao(self):
        if hasattr(self, "_chk_pasta_padrao") and self._chk_pasta_padrao.isChecked():
            self._edit_pasta.setText(self._pasta_padrao())

    def _on_pasta_padrao_toggle(self, state):
        marcado = bool(state)
        if marcado:
            self._edit_pasta.setText(self._pasta_padrao())
            self._edit_pasta.setReadOnly(True)
            self._btn_pasta.setEnabled(False)
            self._edit_pasta.setStyleSheet(f"""
                QLineEdit {{
                    background: {COLORS.get('bg','#0a0e1a')};
                    color: {COLORS.get('accent','#0078d4')};
                    border: 1.5px solid {COLORS.get('accent','#0078d4')};
                    border-radius: 5px; padding: 0 10px; font-weight: 600;
                }}
            """)
        else:
            self._edit_pasta.setReadOnly(False)
            self._btn_pasta.setEnabled(True)
            self._edit_pasta.setStyleSheet(f"""
                QLineEdit {{
                    background: {COLORS.get('surface','#111')};
                    color: {COLORS.get('text','#eee')};
                    border: 1.5px solid {COLORS.get('border','#333')};
                    border-radius: 5px; padding: 0 10px;
                }}
                QLineEdit:focus {{ border-color: {COLORS.get('accent','#0078d4')}; }}
            """)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        self._lay = QVBoxLayout(inner)
        self._lay.setContentsMargins(24, 24, 24, 20)
        self._lay.setSpacing(10)

        self._lay.addWidget(SectionHeader("Pasta de destino"))

        self._chk_pasta_padrao = QCheckBox(r"Usar pasta padrão:  C:\Futura_{ID do cliente}_{versão}")
        self._chk_pasta_padrao.setChecked(True)
        self._chk_pasta_padrao.setFont(QFont(FONT_SANS, 10))
        self._chk_pasta_padrao.setStyleSheet(f"""
            QCheckBox {{ color: {COLORS.get('accent','#0078d4')}; background: transparent; spacing: 6px; font-weight: 600; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; border: 1.5px solid {COLORS.get('border','#444')}; border-radius: 3px; background: {COLORS.get('surface','#111')}; }}
            QCheckBox::indicator:checked {{ background: {COLORS.get('accent','#0078d4')}; border-color: {COLORS.get('accent','#0078d4')}; }}
        """)
        self._chk_pasta_padrao.stateChanged.connect(self._on_pasta_padrao_toggle)
        self._lay.addWidget(self._chk_pasta_padrao)

        row_pasta = QHBoxLayout()
        row_pasta.setSpacing(4)
        self._edit_pasta = QLineEdit()
        self._edit_pasta.setPlaceholderText(r"Ex: C:\Futura_9999_2025.11")
        self._edit_pasta.setFixedHeight(32)
        self._edit_pasta.setFont(QFont(FONT_MONO, 10))
        self._btn_pasta = make_folder_btn(self)
        self._btn_pasta.clicked.connect(self._browse_pasta)
        row_pasta.addWidget(self._edit_pasta, 1)
        row_pasta.addWidget(self._btn_pasta)
        self._lay.addLayout(row_pasta)
        self._on_pasta_padrao_toggle(True)

        self._lay.addWidget(h_line())
        self._lay.addWidget(SectionHeader("Versao a baixar"))

        row_versao = QHBoxLayout()
        row_versao.setSpacing(8)
        lbl_v = QLabel("Versao:")
        lbl_v.setFont(QFont(FONT_SANS, 10))
        lbl_v.setStyleSheet(f"color: {COLORS.get('text_mid','#aaa')}; background: transparent;")
        self._edit_versao = QLineEdit()
        self._edit_versao.setPlaceholderText("Ex: 2026.02.09  (vazio = mais recente)")
        self._edit_versao.setFixedHeight(30)
        self._edit_versao.setFont(QFont(FONT_MONO, 10))
        self._edit_versao.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS.get('surface','#111')}; color: {COLORS.get('text','#eee')};
                border: 1.5px solid {COLORS.get('border','#333')}; border-radius: 5px; padding: 0 10px;
            }}
            QLineEdit:focus {{ border-color: {COLORS.get('accent','#0078d4')}; }}
        """)
        row_versao.addWidget(lbl_v)
        row_versao.addWidget(self._edit_versao, 1)
        self._lay.addLayout(row_versao)

        lbl_hint = QLabel("Deixe em branco para varrer e pegar a versao mais recente automaticamente.")
        lbl_hint.setFont(QFont(FONT_SANS, 9))
        lbl_hint.setStyleSheet(f"color: {COLORS.get('text_dim','#666')}; background: transparent;")
        self._lay.addWidget(lbl_hint)

        self._lay.addWidget(h_line())

        self._progress = QProgressBar()
        self._progress.setFixedHeight(22)
        self._progress.setTextVisible(True)
        self._progress.setFormat("%p%")
        self._progress.setValue(0)
        self._progress.setFont(QFont(FONT_SANS, 9, QFont.Weight.Bold))
        self._progress.setStyleSheet(f"""
            QProgressBar {{ background: {COLORS.get('border','#333')}; border-radius: 5px; border: none; color: {COLORS.get('text','#eee')}; text-align: center; }}
            QProgressBar::chunk {{ background: {COLORS.get('accent','#0078d4')}; border-radius: 5px; }}
        """)
        self._progress.setVisible(False)
        self._lay.addWidget(self._progress)

        self._lbl_resultado = QLabel("")
        self._lbl_resultado.setFont(QFont(FONT_SANS, 10, QFont.Weight.Bold))
        self._lbl_resultado.setWordWrap(True)
        self._lbl_resultado.setVisible(False)
        self._lay.addWidget(self._lbl_resultado)

        self._btn_varrer = make_primary_btn("VARRER SITE", 150)
        self._btn_varrer.clicked.connect(self._on_varrer)
        self._btn_baixar = make_primary_btn("BAIXAR SELECIONADOS", 180)
        self._btn_baixar.clicked.connect(self._on_baixar)
        self._btn_baixar.setVisible(False)

        row_acoes = QHBoxLayout()
        row_acoes.setSpacing(8)
        row_acoes.addWidget(self._btn_varrer)
        row_acoes.addWidget(self._btn_baixar)
        row_acoes.addStretch()
        self._lay.addLayout(row_acoes)

        self._alert = AlertBox("", "info")
        self._alert.setVisible(False)
        self._lay.addWidget(self._alert)

        self._lbl_versao = QLabel("")
        self._lbl_versao.setFont(QFont(FONT_SANS, 11, QFont.Weight.Bold))
        self._lbl_versao.setStyleSheet(f"color: {COLORS.get('accent','#0078d4')}; background: transparent;")
        self._lbl_versao.setVisible(False)
        self._lay.addWidget(self._lbl_versao)

        self._lay.addWidget(SectionHeader("Arquivos disponíveis"))

        self._btn_toggle = QCheckBox("Selecionar todos")
        self._btn_toggle.setChecked(True)
        self._btn_toggle.setFont(QFont(FONT_SANS, 10))
        self._btn_toggle.setStyleSheet(f"""
            QCheckBox {{ color: {COLORS.get('text','#eee')}; background: transparent; spacing: 6px; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; border: 1.5px solid {COLORS.get('border','#444')}; border-radius: 3px; background: {COLORS.get('surface','#111')}; }}
            QCheckBox::indicator:checked {{ background: {COLORS.get('accent','#0078d4')}; border-color: {COLORS.get('accent','#0078d4')}; }}
        """)
        self._btn_toggle.setVisible(False)
        self._btn_toggle.stateChanged.connect(self._toggle_todos)
        self._lay.addWidget(self._btn_toggle)

        self._frame_lista = QFrame()
        self._frame_lista.setVisible(False)
        self._lista_lay = QVBoxLayout(self._frame_lista)
        self._lista_lay.setContentsMargins(0, 0, 0, 0)
        self._lista_lay.setSpacing(0)
        self._lay.addWidget(self._frame_lista)

        self._chk_dll = QCheckBox("Baixar e extrair DLLs (DLLx86.zip)")
        self._chk_dll.setChecked(True)
        self._chk_dll.setFont(QFont(FONT_SANS, 10))
        self._chk_dll.setStyleSheet(f"color: {COLORS.get('text','#eee')}; background: transparent;")
        self._chk_dll.setVisible(False)
        self._lay.addWidget(self._chk_dll)

        self._chk_ini = QCheckBox("Gerar Futura.ini com nome da máquina")
        self._chk_ini.setChecked(True)
        self._chk_ini.setFont(QFont(FONT_SANS, 10))
        self._chk_ini.setStyleSheet(f"color: {COLORS.get('text','#eee')}; background: transparent;")
        self._chk_ini.setVisible(False)
        self._lay.addWidget(self._chk_ini)

        self._lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

        self._overlay = BusyOverlay(self)

    def _browse_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecionar pasta de destino", "C:\\")
        if pasta:
            self._edit_pasta.setText(os.path.normpath(pasta))

    def _on_varrer(self):
        self._btn_varrer.setEnabled(False)
        self._alert.setVisible(False)
        self._lbl_versao.setVisible(False)
        self._frame_lista.setVisible(False)
        self._chk_dll.setVisible(False)
        self._chk_ini.setVisible(False)
        self._btn_baixar.setVisible(False)
        self._overlay.show_with("Varrendo site... aguarde.")

        worker = _VarreduraWorker(self._edit_versao.text().strip())
        worker.concluido.connect(self._on_varredura_concluida)
        worker.erro.connect(self._on_varredura_erro)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _on_varredura_concluida(self, data: dict):
        self._overlay.hide_spinner()
        self._btn_varrer.setEnabled(True)

        versao   = data.get("versao", "")
        sistemas = data.get("sistemas", {})

        if not sistemas:
            self._mostrar_alerta("Nenhum arquivo encontrado no site.", "warn")
            return

        self._lbl_versao.setText(f"Versao encontrada: {versao}")
        self._lbl_versao.setVisible(True)

        if not self._edit_pasta.text().strip() and not self._chk_pasta_padrao.isChecked():
            self._edit_pasta.setText(f"C:\\FUTURA-{versao}")

        while self._lista_lay.count():
            item = self._lista_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._itens_ui.clear()

        for sistema, subpastas in sorted(sistemas.items()):
            for sub, info in sorted(subpastas.items()):
                item = _CheckItem(sistema, sub, info["arquivo"], info["url"])
                self._lista_lay.addWidget(item)
                self._itens_ui.append(item)

        self._btn_toggle.setChecked(True)
        self._btn_toggle.setVisible(True)
        self._frame_lista.setVisible(True)
        self._chk_dll.setVisible(True)
        self._chk_ini.setVisible(True)
        self._btn_baixar.setVisible(True)

    def _toggle_todos(self, state: int):
        for it in self._itens_ui:
            it._chk.setChecked(bool(state))

    def _on_varredura_erro(self, msg):
        self._overlay.hide_spinner()
        self._btn_varrer.setEnabled(True)
        self._mostrar_alerta(f"Erro ao varrer site: {msg}", "error")

    def _on_baixar(self):
        pasta = self._edit_pasta.text().strip()
        if not pasta:
            self._mostrar_alerta("Informe a pasta de destino.", "warn")
            return
        selecionados = [{"nome": it.arquivo, "url": it.url} for it in self._itens_ui if it.selecionado]
        if not selecionados and not self._chk_dll.isChecked():
            self._mostrar_alerta("Selecione ao menos um arquivo.", "warn")
            return

        self._btn_baixar.setEnabled(False)
        self._btn_varrer.setEnabled(False)
        self._lbl_resultado.setVisible(False)
        self._progress.setValue(0)
        self._progress.setFormat("0%")
        self._progress.setVisible(True)
        self._overlay.show_with("Baixando arquivos...")

        worker = _DownloadWorker(selecionados, pasta, self._chk_dll.isChecked(), self._chk_ini.isChecked())
        worker.progresso.connect(self._on_progresso)
        worker.concluido.connect(self._on_download_concluido)
        worker.erro.connect(self._on_download_erro)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _on_progresso(self, msg, pct):
        self._progress.setValue(pct)
        self._progress.setFormat(f"%p%  —  {msg}")

    def _on_download_concluido(self, pasta):
        self._overlay.hide_spinner()
        self._btn_baixar.setEnabled(True)
        self._btn_varrer.setEnabled(True)
        self._progress.setValue(100)
        self._progress.setFormat("100%  —  Concluido!")
        self._lbl_resultado.setText(f"✔  Download concluido com sucesso!\n{pasta}")
        self._lbl_resultado.setStyleSheet(f"color: {COLORS.get('accent2','#2ecc71')}; background: transparent;")
        self._lbl_resultado.setVisible(True)

    def _on_download_erro(self, msg):
        self._overlay.hide_spinner()
        self._btn_baixar.setEnabled(True)
        self._btn_varrer.setEnabled(True)
        self._progress.setFormat("Erro!")
        self._lbl_resultado.setText(f"✖  {msg}")
        self._lbl_resultado.setStyleSheet(f"color: {COLORS.get('danger','#e74c3c')}; background: transparent;")
        self._lbl_resultado.setVisible(True)

    def _mostrar_alerta(self, txt, kind):
        self._alert.set_text(txt)
        self._alert.set_kind(kind)
        self._alert.setVisible(True)

    def reset(self):
        self._id_cliente    = ""
        self._versao_futura = ""
        self._alert.setVisible(False)
        self._lbl_versao.setVisible(False)
        self._btn_toggle.setVisible(False)
        self._frame_lista.setVisible(False)
        self._chk_dll.setVisible(False)
        self._chk_ini.setVisible(False)
        self._btn_baixar.setVisible(False)
        self._progress.setVisible(False)
        self._progress.setValue(0)
        self._lbl_resultado.setVisible(False)
        self._btn_varrer.setEnabled(True)
        self._btn_baixar.setEnabled(True)
        self._chk_pasta_padrao.setChecked(True)
        self._on_pasta_padrao_toggle(True)


# =============================================================================
# Página principal com QTabWidget
# =============================================================================

class PageVerificarVersaoFdb(QWidget):
    go_menu = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        theme_manager.theme_changed.connect(self._upd_style)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = PageHeader(
            "VERIFICAR VERSÃO / DOWNLOAD",
            "Detecta versão do .fdb e baixa atualizações do site Futura"
        )
        self._header.back_clicked.connect(self.go_menu.emit)
        root.addWidget(self._header)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._aba_verificar = _AbaVerificar()
        self._aba_download  = _AbaDownload()

        self._tabs.addTab(self._aba_verificar, "  Verificar Versao  ")
        self._tabs.addTab(self._aba_download,  "  Download Atualizacao  ")

        self._aba_verificar.ir_para_download.connect(self._ir_para_download)

        root.addWidget(self._tabs, 1)
        self._upd_style()

    def _ir_para_download(self, versao: str):
        result     = self._aba_verificar._card_result._result_cache
        id_cliente = result.get("id_cliente", "")
        self._tabs.setCurrentIndex(1)
        self._aba_download.definir_contexto(id_cliente, versao)
        self._aba_download._edit_versao.setText(versao)
        self._aba_download._on_varrer()

    def _upd_style(self, _mode: str = ""):
        bg      = COLORS.get("bg",      "#0a0e1a")
        surface = COLORS.get("surface", "#111827")
        accent  = COLORS.get("accent",  "#0078d4")
        text    = COLORS.get("text",    "#e2e8f0")
        dim     = COLORS.get("text_dim","#64748b")
        border  = COLORS.get("border",  "#1e2d45")

        self.findChild(QWidget, "page_header").setStyleSheet(
            f"QWidget#page_header {{ background: {surface}; border-bottom: 1px solid {border}; }}"
        )
        self.findChild(QLabel).setStyleSheet(f"color: {text}; background: transparent;")

        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {bg}; }}
            QTabBar::tab {{
                background: {surface}; color: {dim};
                font-family: {FONT_SANS}; font-size: 11px; font-weight: 600;
                padding: 8px 16px; border: none; border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{ color: {accent}; border-bottom: 2px solid {accent}; background: {bg}; }}
            QTabBar::tab:hover:!selected {{ color: {text}; background: {bg}; }}
        """)

    def reset(self):
        self._aba_verificar.reset()
        self._aba_download.reset()

    @property
    def _worker(self):
        w = getattr(self._aba_verificar, "_worker", None)
        if w and w.isRunning():
            return w
        w = getattr(self._aba_download, "_worker", None)
        if w and w.isRunning():
            return w
        return None