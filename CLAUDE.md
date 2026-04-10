# CLAUDE.md — Futura Setup v5.0

## O que é este projeto

Ferramenta interna de TI para configurar terminais Windows de uma empresa que usa o software **Futura** (ERP/PDV). Desenvolvida em **Python 3.12 + PyQt6**. Distribui como `.exe` (PyInstaller) ou em modo portable via `.bat`.

---

## Estrutura de arquivos

```
futura_setup/
├── main.py                    # Janela principal, sidebar, navegação, entry point
├── launcher.py                # Entry point para modo portable
├── config.py                  # Todas as constantes e URLs centralizadas
├── futura_setup.spec          # Configuração PyInstaller
├── build.bat                  # Compila para .exe (usa python_portable\python.exe)
├── executar.bat               # Abre o sistema sem abrir o CMD
├── rodar_portable.bat         # Baixa Python + deps e executa sem instalar nada
├── requirements.txt           # PyQt6, psutil, pywin32, pyinstaller
├── pass/
│   ├── trocar_senha.py        # Troca a senha de acesso e atualiza main.py
│   └── trocar_senha.bat       # Duplo clique para trocar senha sem abrir CMD
├── ui/
│   ├── components/            # Fragmentação de ui/widgets.py
│   │   ├── base.py            # Utilitários, labels, spacers, linhas
│   │   ├── buttons.py         # Fábricas de botões (primary, secondary)
│   │   ├── cards.py           # Itens selecionáveis (ServerItem, RadioRow, etc.)
│   │   ├── containers.py      # LogConsole, FadeStackedWidget, Overlays
│   │   ├── dialogs.py         # ConfirmDialog, WorkerGuardDialog
│   │   └── feedback.py        # AlertBox, Header, Progress, StepIndicator
│   ├── theme.py               # Paleta de cores (light/dark), COLORS global
│   ├── theme_manager.py       # Singleton ThemeManager, sinal theme_changed
│   ├── widgets.py             # Facade que exporta componentes de ui/components/
│   ├── page_menu.py           # Menu principal
│   ├── page_scan.py           # Escaneamento de rede
│   └── ...                    # Outras páginas
└── core/
    ├── app_state.py           # NEW: Singleton Global Reativo (AppState)
    ├── logger.py              # Singleton FuturaLogger + Prefs
    ├── network.py             # Descoberta de servidores
    ├── installer.py           # Workers de instalação
    └── atualizador.py         # Worker de atualização completa do ERP
```

---

## Autenticação (main.py)

O app exige senha ao iniciar. A senha é verificada por hash SHA-256.

```python
_SENHA_HASH = "..."  # senha: <plaintext>
```

- `LoginDialog`: diálogo modal com 3 tentativas antes de bloquear 30 segundos.
- Fechar sem autenticar encerra o app.
- Para trocar a senha: executar `pass\trocar_senha.bat` (ou `python_portable\python.exe pass\trocar_senha.py`).
- Após trocar a senha, recompilar com `build.bat`.

---

## Fluxo de navegação (main.py)

```
Menu Principal
├── Modo 01 (Atalhos)     → PageScan → PageAtalhos
├── Modo 02 (Terminal)    → PageScan → PageTerminal
├── Modo 03 (Atualizar)   → PageAtualizacao (sem scan)
├── Modo 04 (Log)         → PageLog (sem scan)
└── Modo 05 (Restaurar)   → PageRestaurar (sem scan)
```

**Índices do QStackedWidget em main.py:**
```python
_IDX_MENU        = 0
_IDX_SCAN        = 1
_IDX_ATALHOS     = 2
_IDX_TERMINAL    = 3
_IDX_RESTAURAR   = 4
_IDX_LOG         = 5
_IDX_ATUALIZACAO = 6
```

---

## Sistema de temas (ui/theme.py + ui/theme_manager.py)

- `COLORS` é um **dict mutável global** atualizado in-place por `set_theme(mode)`.
- Widgets devem ler `COLORS` **sempre em `_upd()`**, nunca em `__init__`, para refletir o tema atual.
- `get_stylesheet(mode)` retorna o stylesheet completo sem depender do `COLORS` global — usar em `QApplication.setStyleSheet()`.
- `ThemeManager` é **singleton** via `__new__` + guard `_initialized`. Instância global: `theme_manager`.
- Conectar mudança de tema: `theme_manager.theme_changed.connect(self._upd)`.
- O sinal emite o `mode` como `str`: `"light"` ou `"dark"`.
- Para alternar: `theme_manager.toggle()`. Para definir: `theme_manager.set_mode("dark")`.

### Cores principais
| Chave | Light | Dark | Uso |
|---|---|---|---|
| `bg` | `#f3f3f3` | `#202020` | Fundo da janela |
| `surface` | `#ffffff` | `#2c2c2c` | Cards, painéis |
| `surface2` | `#f9f9f9` | `#272727` | Fundo alternativo |
| `accent` | `#0078D4` | `#60CDFF` | Botões primary, destaques |
| `accent_dim` | `#EFF6FC` | `#0d2a38` | Fundo de itens selecionados |
| `accent2` | `#107C10` | `#6CCB5F` | Sucesso, backup |
| `accent2_dim` | `#EEF7EE` | `#0d2a0d` | Fundo de backup selecionado |
| `warn` | `#9D5D00` | `#FCE100` | Avisos |
| `warn_dim` | `#FFF4CE` | `#2a2500` | Fundo de avisos |
| `danger` | `#C42B1C` | `#FF99A4` | Erros, ações destrutivas |
| `danger_dim` | `#FDE7E9` | `#2a0f10` | Fundo de erros |
| `text` | `#1a1a1a` | `#ffffff` | Texto principal |
| `text_mid` | `#5a5a5a` | `#c0c0c0` | Texto secundário |
| `text_dim` | `#9a9a9a` | `#808080` | Labels, rótulos |
| `text_disabled` | `#bbbbbb` | `#505050` | Texto desabilitado |
| `log_ok` | `#107C10` | `#6CCB5F` | Cor de log OK |
| `log_info` | `#0078D4` | `#60CDFF` | Cor de log info |
| `log_warn` | `#9D5D00` | `#FCE100` | Cor de log aviso |
| `log_err` | `#C42B1C` | `#FF99A4` | Cor de log erro |

---

## Logger e Prefs (core/logger.py)

- `FuturaLogger` é **singleton** via `__new__` + guard `_initialized`.
- Instância global: `from core.logger import log`.
- Arquivo de log: `%APPDATA%\Futura\futura_setup.log` (RotatingFileHandler, máx 2MB × 3 backups).
- Prefs: `%APPDATA%\Futura\prefs.json` — salva `theme`, `servidores_hist`, `pastas_hist`.

### API do logger
```python
log.info("mensagem")      # info
log.ok("mensagem")        # info com prefixo [OK]
log.warn("mensagem")      # warning com prefixo [!]
log.error("mensagem")     # error com prefixo [X]
log.section("TITULO")     # info com decoração === TITULO ===
log.read_log_tail(5000)   # últimas N linhas (evita carregar 8MB)
log.read_log_all()        # todos os arquivos rotacionados (~8MB)
log.prefs.theme           # "light" | "dark"
log.prefs.add_servidor(ip, hostname, path)
log.prefs.add_pasta(pasta)
```

### Sinal em tempo real
```python
log.signals.new_line.connect(fn)  # fn(mensagem: str, kind: str)
# kind ∈ {"ok", "info", "warn", "err"}
```

---

## Rede (core/network.py)

### Modelo `Servidor`
```python
@dataclass
class Servidor:
    ip:       str
    hostname: str = ""
    path:     str = ""     # \\hostname\Futura
    path_ip:  str = ""     # \\ip\Futura
    version:  str = ""
```

Propriedades úteis: `srv.display` (hostname + IP formatado), `srv.version_display`.

### `ScanWorker` (QThread)
- Métodos disponíveis em `ScanWorker.METODOS` (lista de `MetodoScan` NamedTuple com `.key`, `.nome`, `.descricao`).
- Sinais: `log_line(str, str)`, `progress(int, int)`, `finished(list[Servidor])`, `status_text(str)`.
- Para parar: `worker.stop()`.
- Usa `max_workers=25` para não saturar redes corporativas.

### Funções auxiliares
```python
get_hosts_via_arp() -> list[str]          # IPs do cache ARP
testar_conectividade(hosts=None) -> bool  # Testa porta 80 com create_connection
resolve_hostname(ip) -> str               # DNS/NetBIOS
```

---

## Installer (core/installer.py)

### Workers disponíveis

| Worker | Sinais | Função |
|---|---|---|
| `InstalacaoWorker` | `log_line`, `step_done(int)`, `progress(int,str,str)`, `finished(bool,dict)`, `status_text` | Copia arquivos do servidor, instala DLLs, cria atalhos |
| `RestauracaoWorker` | `log_line`, `progress(int,str,str)`, `finished(bool,dict)`, `status_text` | Restaura backup |
| `AtalhosWorker` | `log_line`, `progress(int,str,str)`, `finished(bool,int,int)` | Cria atalhos via rede |

### Steps do `InstalacaoWorker` (índices para `step_done`)
```
3=Backup  4=Servidor  5=Arquivos  6=DLLs  7=Atalhos
```

### Funções utilitárias
```python
listar_executaveis(path) -> list[dict]         # EXEs no share (priorizando EXES_CONHECIDOS)
listar_backups(pasta_futura) -> list[dict]     # Backups em pasta/Backup_Atualizacao
listar_processos_na_pasta(pasta) -> list[dict] # Processos rodando na pasta (psutil)
encerrar_processos(pids) -> tuple[int,int]     # (encerrados, falhos)
criar_atalho_windows(target, name, desc, desktop, start_menu) -> list[str]
formatar_tamanho(bytes_) -> str                # "1.2 MB" ou "512 KB"
espaco_livre_mb(caminho) -> float
download_com_retry(url, destino, descricao, progress_cb, max_tentativas) -> bool
_hash_arquivo(path) -> str                     # SHA-256 para verificação de integridade
```

### Resumo retornado por `InstalacaoWorker.finished`
```python
{
    "pasta":         str,
    "servidor":      str,
    "copiados":      int,
    "atalhos":       int,
    "atalhos_nomes": list[str],
    "backup":        str,
    "dlls":          bool,
    "cancelado":     bool,  # presente apenas se cancelado
}
```

---

## Atualizador (core/atualizador.py)

### `AtualizacaoWorker` (QThread)
Fluxo: detectar instalação → detectar banco → parar Firebird → renomear banco → reiniciar Firebird → baixar Atualizador.exe → baixar DLLs → criar PESQUISA.INI → executar Atualizador.exe.

**Sinais especiais** (UI deve tratar e reiniciar o worker com a escolha):
```python
precisa_pasta = pyqtSignal(list)   # múltiplas instalações encontradas
precisa_banco = pyqtSignal(list)   # múltiplos bancos .fdb encontrados
```

**Construção com escolha pendente:**
```python
worker = AtualizacaoWorker(pasta_escolhida="C:\\FUTURA", banco_escolhido="C:\\...\\dados.fdb")
```

### Funções auxiliares
```python
find_instalacoes() -> list[str]                         # busca Futura.ini em todos os drives
find_bancos(pasta, excluir_temp) -> list[dict]          # Firebird → local → recursivo
find_firebird_dir() -> Optional[str]
stop_firebird_services() -> list[str]                   # retorna serviços parados
start_firebird_services(servicos)
criar_pesquisa_ini(pasta, pasta_firebird, caminho_banco) -> bool  # usa configparser
download_dlls(destino, progress_cb) -> bool
```

### Workers de detecção não-bloqueantes (em page_atualizacao.py)
```python
_DetectarPastasWorker(QThread)  # emite finished(list[str])
_DetectarBancosWorker(QThread)  # emite finished(list[dict])
```
Esses workers usam `Qt.ConnectionType.SingleShotConnection` para evitar chamadas duplicadas.

---

## Arquitetura de Componentes (ui/components/)

O arquivo `ui/widgets.py` agora serve apenas como uma **facade** para manter retrocompatibilidade. Os componentes estão divididos logicamente:

| Arquivo | Componentes principais |
|---|---|
| `base.py` | `hex_to_rgb`, `card_style`, `spacer`, `h_line`, `HLine`, `label` |
| `buttons.py` | `make_primary_btn`, `make_secondary_btn`, `make_folder_btn`, `btn_row` |
| `feedback.py` | `PageHeader`, `SectionHeader`, `AlertBox`, `ProgressBlock`, `StepIndicator`, `LoadingSpinner` |
| `containers.py` | `LogConsole`, `FadeStackedWidget`, `BusyOverlay` |
| `cards.py` | `ServerItem`, `RadioRow`, `MiniFileItem`, `DestPanel`, `ProcessCard`, `MenuCard` |
| `dialogs.py` | `ConfirmDialog`, `WorkerGuardDialog` |

### Reactive App State (core/app_state.py)
O singleton `state` centraliza dados globais sem acoplamento direto entre classes:
- `state.servidor` (Servidor selecionado)
- `state.servidor_changed` (Signal)
- `state.pasta` (Caminho de destino)
- `state.flow_mode` (atalhos, terminal, etc.)
- `state.is_worker_running` (Signal Worker running)

### Helpers de layout
```python
spacer(w=0, h=0)                              # QWidget com tamanho fixo
h_line()                                      # linha horizontal QFrame
label(text, color, size, bold, mono)          # QLabel simples
make_btn(text, cls="secondary", min_width=120) # QPushButton
make_btn_row(btns, back=None)                 # linha de botões com "← VOLTAR" opcional
card_style(state, selected) -> (bg, border)   # helper centralizado para estados de card
hex_to_rgb(hex_color) -> tuple[int,int,int]   # converte cor hex em RGB
```

### `LogConsole` — detalhes
- `document().setMaximumBlockCount(max_lines)` limita memória automaticamente.
- `append_line(text, kind)` — kinds: `"ok"`, `"info"`, `"warn"`, `"err"`, `"dim"`.
- `clear_console()` limpa o conteúdo.

### `AlertBox` — alterar após criação
```python
alert.set_text("nova mensagem")
alert._kind = "warn"
alert._upd()
```

---

## Widgets de página (padrão de implementação)

Todas as páginas seguem o mesmo padrão:

```python
class PageXxx(QWidget):
    go_menu = pyqtSignal()           # sinal de retorno ao menu

    def set_servidor(self, srv: Servidor):  # páginas que dependem de scan
        ...

    def reset(self):                 # páginas sem scan (restaurar, log, atualizar)
        ...
```

### Padrão de steps (páginas com fluxo em etapas)
- `QStackedWidget` interno com um widget por step.
- `StepIndicator` atualizado via `_step_ind.set_step(idx)`.
- Navegação via `_go_step(idx)`.

---

## Convenções importantes

### Sinal vs callback
- **Use `pyqtSignal`** para comunicação entre widgets — nunca monkey-patch via `widget.on_click = fn`.
- Exceção: `NavItem.on_click(fn)` em `main.py` (padrão legado mantido intencionalmente).
- `ServerItem`, `BackupItem`, `ActionButton` emitem sinais — conectar com `.signal.connect(fn)`.

### Workers (QThread)
- Todos herdam de `QThread` e implementam `stop()`.
- Emitem `log_line(str, str)` onde `kind ∈ {"ok","info","warn","err","dim"}`.
- Nunca acessar UI diretamente de dentro do worker — só via sinais.
- Para parar: chamar `worker.stop()` e depois `worker.wait(2000)`.
- Workers de detecção de curta duração (ex: `_DetectarPastasWorker`) usam `SingleShotConnection`.

### Tema
- **Nunca** ler `COLORS` em `__init__` — sempre em `_upd()`.
- Assinar `theme_manager.theme_changed.connect(self._upd)` em todo widget que usa cores.
- Assinatura de `_upd`: `def _upd(self, _mode: str = "")` para aceitar o sinal com ou sem argumento.
- `card_style(state, selected)` centraliza a lógica de bg/border para cards clicáveis.

### Imports
- `from core.logger import log` — singleton global.
- `from ui.theme_manager import theme_manager` — singleton global.
- Imports tardios (lazy) apenas para evitar circulares (ex: `atualizador.py` importa `installer.py` dentro de função via `_get_download_fn()`).

### Layout
- Páginas com conteúdo + rodapé fixo usam dois `QWidget` com `stretch=1` e `stretch=0`.
- `spacer(h=N)` é preferível a `addSpacing(N)` para transparência garantida.

---

## Config (config.py)

```python
APP_VERSION              # "4.3.0"
URL_DLLS                 # URL do DLLx86.zip no repositório
URL_ATUALIZADOR          # URL do Atualizador.exe no repositório
CONNECTIVITY_HOSTS       # Hosts para teste de conectividade
EXES_CONHECIDOS          # list[tuple[nome, descrição]] — EXEs do Futura
MAX_BACKUPS              # 5
ESPACO_MIN_MB            # 500
MAX_TENTATIVAS_DOWNLOAD  # 3
MAX_TENTATIVAS_COPIA     # 3
BACKUP_SUBDIR            # "Backup_Atualizacao"
FIREBIRD_CONF_PATHS      # caminhos para databases.conf do Firebird
FIREBIRD_SERVICES        # nomes dos serviços Windows do Firebird
FUTURA_SHARE_NAME        # "Futura"
FUTURA_MARKER_FILES      # ["Futura.ini", "FuturaServer.exe"]
PASTAS_INSTALACAO_PADRAO # ["C:\\FUTURA", "C:\\FuturaTerminal"]
```

---

## Build e distribuição

### Executar sem compilar
```
executar.bat   # duplo clique — abre direto usando python_portable
```

### Modo portable (sem instalar nada)
```
rodar_portable.bat
```
Baixa Python 3.12 embeddable + pip + dependências automaticamente em `python_portable/`.

### Build como .exe
```
build.bat
```
Usa `python_portable\python.exe`, detecta versão de `config.py` e gera `dist\FuturaSetup_v{VERSION}_{DATA}.exe`.

### Dependências
```
PyQt6
psutil
pywin32
pyinstaller
```

---

## Checklist ao criar uma nova página

1. Herdar de `QWidget`, declarar `go_menu = pyqtSignal()`.
2. Implementar `reset()` ou `set_servidor(srv)` conforme o fluxo.
3. Conectar `theme_manager.theme_changed.connect(self._upd)` em todo widget com cor customizada.
4. Ler `COLORS` apenas em `_upd()`, nunca em `__init__`.
5. Usar `make_btn`, `make_btn_row`, `spacer`, `LogConsole`, `ProgressBlock` de `ui/widgets.py`.
6. Registrar a página em `main.py`: adicionar ao `QStackedWidget`, definir constante `_IDX_*`, conectar sinais e adicionar item na sidebar.
7. Se tiver worker, garantir que `_worker` é acessível como atributo para `_get_active_workers()` em `MainWindow`.
8. Para rodapé fixo: usar dois `QWidget` no layout raiz com `stretch=1` (conteúdo) e `stretch=0` (rodapé).
