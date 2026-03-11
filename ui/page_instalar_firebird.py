# =============================================================================
# FUTURA SETUP — Página: Instalar Firebird
# Apenas UI — toda a lógica está em core/instalar_firebird.py
# Salvar em: ui/page_instalar_firebird.py
# =============================================================================

from __future__ import annotations

from PyQt6.QtCore    import Qt, pyqtSignal, QThread
from PyQt6.QtGui     import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QButtonGroup,
    QRadioButton, QFrame, QLabel, QStackedWidget,
)

from ui.theme        import COLORS, FONT_SANS, FONT_MONO
from ui.theme_manager import theme_manager
from ui.widgets      import (
    PageTitle, SectionHeader, AlertBox, LogConsole, ProgressBlock,
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
)


class PageInstalarFirebird(QWidget):
    go_menu = pyqtSignal()

    _IDX_CONFIG    = 0
    _IDX_RUNNING   = 1
    _IDX_RESULTADO = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: InstaladorFirebirdWorker | None = None
        self._checker: QThread | None = None
        self._arch = detect_arch()

        self._stack = QStackedWidget()

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 20)
        root.setSpacing(8)

        root.addWidget(PageTitle("INSTALAR FIREBIRD", "Download e instalação silenciosa"))
        root.addWidget(self._stack, 1)

        self._stack.addWidget(self._build_config())    # 0
        self._stack.addWidget(self._build_running())   # 1
        self._stack.addWidget(self._build_resultado()) # 2

        self._go_step(self._IDX_CONFIG)
        self._run_install_check()

    # =========================================================================
    # Build das telas
    # =========================================================================

    def _build_config(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # Alert — aviso de admin (fixo, sempre visível se sem privilégio)
        if not is_admin():
            admin_alert = AlertBox(
                "⚠  Sem privilégios de administrador — a instalação irá falhar. "
                "Execute o Futura Setup como Administrador.",
                "error"
            )
            lay.addWidget(admin_alert)

        # Alert — status da instalação existente
        self._alert_config = AlertBox("Verificando instalação existente...", "info")
        lay.addWidget(self._alert_config)

        # Informações do sistema
        lay.addWidget(SectionHeader("Sistema"))

        arch_row = QHBoxLayout()
        arch_row.setSpacing(10)
        arch_lbl = label("Arquitetura detectada:", COLORS["text_mid"], 11)
        arch_val = label(self._arch, COLORS["text"], 12)
        arch_val.setFont(QFont(FONT_SANS, 12, QFont.Weight.Bold))
        arch_row.addWidget(arch_lbl)
        arch_row.addWidget(arch_val)
        arch_row.addStretch()
        lay.addLayout(arch_row)

        lay.addWidget(h_line())

        # Seleção de versão
        lay.addWidget(SectionHeader("Versão do Firebird"))

        desc = label(
            "Escolha a versão que deseja instalar. "
            "O instalador será baixado automaticamente do repositório oficial.",
            COLORS["text_mid"], 11,
        )
        desc.setWordWrap(True)
        lay.addWidget(desc)
        lay.addWidget(spacer(h=4))

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        self._card3, self._radio3 = self._make_version_card(
            "Firebird 3", FB_LABEL["3"],
            "Compatível com sistemas legados.\nEstável e amplamente utilizado.", "3",
        )
        self._card4, self._radio4 = self._make_version_card(
            "Firebird 4", FB_LABEL["4"],
            "Versão mais recente.\nMelhor desempenho e novos recursos.", "4",
        )

        self._group = QButtonGroup(w)
        self._group.addButton(self._radio3)
        self._group.addButton(self._radio4)
        self._radio3.setChecked(True)

        cards_row.addWidget(self._card3)
        cards_row.addWidget(self._card4)
        cards_row.addStretch()
        lay.addLayout(cards_row)
        lay.addWidget(spacer(h=4))

        # URL que será baixada
        self._url_lbl = label("", COLORS["text_dim"], 9)
        self._url_lbl.setFont(QFont(FONT_MONO, 9))
        self._url_lbl.setWordWrap(True)
        lay.addWidget(self._url_lbl)

        lay.addStretch()
        lay.addWidget(h_line())
        lay.addWidget(spacer(h=4))

        btn_instalar = make_primary_btn("⬇  BAIXAR E INSTALAR", 200)
        btn_instalar.clicked.connect(self._on_instalar)
        btn_voltar = make_secondary_btn("← VOLTAR", 80)
        btn_voltar.clicked.connect(self.go_menu.emit)
        lay.addWidget(btn_row(btn_instalar, btn_voltar))

        self._group.buttonToggled.connect(lambda *_: self._upd_url_lbl())
        self._group.buttonToggled.connect(lambda *_: self._upd_cards_border())
        self._upd_url_lbl()

        theme_manager.theme_changed.connect(self._upd_cards_border)
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
        lay.addStretch()
        lay.addWidget(h_line())
        lay.addWidget(spacer(h=4))

        btn_nova   = make_secondary_btn("🔄  NOVA INSTALAÇÃO", 160)
        btn_voltar = make_secondary_btn("← VOLTAR", 80)
        btn_nova.clicked.connect(self._go_novo)
        btn_voltar.clicked.connect(self.go_menu.emit)
        lay.addWidget(btn_row(btn_nova, btn_voltar))

        return w

    # =========================================================================
    # Cards de versão
    # =========================================================================

    def _make_version_card(self, heading: str, version_str: str,
                           desc: str, key: str) -> tuple[QFrame, QRadioButton]:
        card = QFrame()
        card.setObjectName(f"vcard_{key}")
        card.setFixedWidth(220)
        card.setMinimumHeight(110)
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        radio = QRadioButton(heading)
        radio.setObjectName(f"vcard_radio_{key}")
        radio.setFont(QFont(FONT_SANS, 13, QFont.Weight.Bold))

        ver_lbl = QLabel(version_str)
        ver_lbl.setObjectName(f"vcard_ver_{key}")
        ver_lbl.setFont(QFont(FONT_MONO, 9))

        desc_lbl = QLabel(desc)
        desc_lbl.setObjectName(f"vcard_desc_{key}")
        desc_lbl.setFont(QFont(FONT_SANS, 10))
        desc_lbl.setWordWrap(True)

        lay.addWidget(radio)
        lay.addWidget(ver_lbl)
        lay.addWidget(desc_lbl)

        card.mousePressEvent = lambda e, r=radio: r.setChecked(True)
        card._radio    = radio
        card._ver_lbl  = ver_lbl
        card._desc_lbl = desc_lbl
        return card, radio

    def _upd_cards_border(self, _mode: str = ""):
        for card, radio in [(self._card3, self._radio3), (self._card4, self._radio4)]:
            sel    = radio.isChecked()
            border = COLORS["accent"]     if sel else COLORS["border"]
            bg     = COLORS["accent_dim"] if sel else COLORS["surface"]
            key    = card.objectName()
            card.setStyleSheet(f"""
                QFrame#{key} {{
                    background: {bg};
                    border: 2px solid {border};
                    border-radius: 10px;
                }}
                QRadioButton {{
                    color: {COLORS['text']};
                    background: transparent;
                    border: none;
                }}
                QLabel {{
                    color: {COLORS['text_dim']};
                    background: transparent;
                    border: none;
                }}
            """)

    def _upd_url_lbl(self):
        version = "3" if self._radio3.isChecked() else "4"
        url     = FB_URLS[version][self._arch]
        self._url_lbl.setText(f"🔗  {url}")

    # =========================================================================
    # Verificação assíncrona de instalação existente
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
        if result:
            ver = result.get("version") or "Desconhecida"
            txt = f"⚠  Firebird instalado: {ver}"
            if result.get("path"):
                txt += f"  |  {result['path']}"
            txt += "  —  será desinstalado antes da nova versão."
            self._alert_config.set_text(txt)
            self._alert_config.set_kind("warn")
        else:
            self._alert_config.set_text("✔  Nenhuma instalação anterior encontrada.")
            self._alert_config.set_kind("success")

    # =========================================================================
    # Ações
    # =========================================================================

    def reset(self):
        self._go_step(self._IDX_CONFIG)
        self._alert_config.set_text("Verificando instalação existente...")
        self._alert_config.set_kind("info")
        self._upd_url_lbl()
        self._upd_cards_border()
        self._run_install_check()

    def _on_instalar(self):
        # Se não tiver admin, solicita elevação via UAC e reinicia o processo
        if not is_admin():
            from PyQt6.QtWidgets import QMessageBox, QApplication
            msg = QMessageBox(self)
            msg.setWindowTitle("Permissão necessária")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText(
                "A instalação do Firebird requer privilégios de Administrador.\n\n"
                "O Futura Setup será reiniciado como Administrador.\n"
                "Confirme no prompt do Windows (UAC) para continuar."
            )
            msg.setStandardButtons(
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
            )
            msg.setDefaultButton(QMessageBox.StandardButton.Ok)
            if msg.exec() == QMessageBox.StandardButton.Ok:
                ok = elevar_como_admin()
                if ok:
                    # Fecha o processo atual — o novo já foi aberto como admin
                    QApplication.quit()
                else:
                    QMessageBox.critical(
                        self,
                        "Erro de elevação",
                        "Não foi possível solicitar privilégios de Administrador.\n"
                        "Execute o programa manualmente como Administrador.",
                    )
            return

        version = "3" if self._radio3.isChecked() else "4"
        self._console.clear_console()
        self._progress.set_progress(0, "Iniciando...")
        self._btn_cancelar.setEnabled(True)
        self._go_step(self._IDX_RUNNING)

        self._worker = InstaladorFirebirdWorker(version, self._arch, parent=self)
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
        self._worker = None
        cancelado  = info.get("cancelado", False)
        sem_admin  = info.get("sem_admin", False)

        if success:
            ver  = info.get("version", "Firebird")
            arch = info.get("arch", self._arch)
            self._res_alert.set_text(f"✔  {ver} ({arch}) instalado com sucesso!")
            self._res_alert.set_kind("success")
            self._res_detalhe.setText(
                "O serviço do Firebird foi iniciado automaticamente.\n"
                "Nenhuma reinicialização é necessária."
            )
        elif cancelado:
            self._res_alert.set_text("⚠  Instalação cancelada pelo usuário.")
            self._res_alert.set_kind("warn")
            self._res_detalhe.setText("")
        elif sem_admin:
            self._res_alert.set_text("✕  Permissão insuficiente — execute como Administrador.")
            self._res_alert.set_kind("error")
            self._res_detalhe.setText(
                "Feche o Futura Setup e abra novamente clicando com o botão direito\n"
                "no ícone do programa → Executar como administrador."
            )
        else:
            self._res_alert.set_text("✕  Falha durante a instalação. Verifique o log para detalhes.")
            self._res_alert.set_kind("error")
            self._res_detalhe.setText("")

        self._go_step(self._IDX_RESULTADO)

    def _go_novo(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(1000)
        self._worker = None
        self.reset()

    def _go_step(self, idx: int):
        self._stack.setCurrentIndex(idx)