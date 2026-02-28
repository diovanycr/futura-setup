# CONTEXTO — Futura Setup v4.2.0

## O que é
Ferramenta interna de TI para configurar terminais Windows de uma empresa que usa o software **Futura** (ERP/PDV). Desenvolvida em **Python 3.12 + PyQt6**. Pode rodar como `.exe` (PyInstaller) ou em modo portable via `.bat`.

## Estrutura de pastas
```
futura_setup/
├── main.py              # Janela principal, sidebar, navegação
├── launcher.py          # Entry point para modo portable
├── futura_setup.spec    # Configuração PyInstaller
├── build.bat            # Compila para .exe
├── rodar_portable.bat   # Baixa Python + deps e executa sem instalar nada
├── requirements.txt     # PyQt6, psutil, pywin32, pyinstaller
├── ui/
│   ├── theme.py         # Paleta de cores dark, fontes, STYLESHEET global
│   ├── widgets.py       # Componentes reutilizáveis (PageTitle, AlertBox, LogConsole, etc.)
│   ├── page_menu.py     # Menu principal (4 cards em grid 2x2)
│   ├── page_scan.py     # Escaneamento de rede para encontrar servidor Futura
│   ├── page_atalhos.py  # Modo 01: cria atalhos apontando para o servidor
│   ├── page_terminal.py # Modo 02: copia arquivos localmente
│   ├── page_restaurar.py# Modo 04: restaura backups anteriores
│   └── page_log.py      # Visualiza log de execuções
└── core/
    ├── logger.py        # Singleton FuturaLogger → %APPDATA%\Futura\futura_setup.log
    ├── network.py       # Descoberta de servidores via ARP + teste de share
    └── installer.py     # Workers para atalhos, instalação local e restauração
```

## Fluxo principal
1. Usuário escolhe operação no **Menu Principal**
2. **PageScan** escaneia a rede (lê cache ARP → testa `\\ip\Futura` → resolve hostname)
3. Usuário seleciona um servidor
4. Executa a operação escolhida:
   - **Modo 01 (Atalhos):** lista `.exe` no servidor → cria atalhos no Desktop/Menu Iniciar
   - **Modo 02 (Terminal):** copia arquivos para `C:\FUTURA` ou `C:\FuturaTerminal`
   - **Modo 03 (Log):** exibe `futura_setup.log` com colorização
   - **Modo 04 (Restaurar):** lista backups em `C:\FUTURA` ou `C:\FuturaTerminal` → restaura

## Detalhes técnicos importantes
- **Share do servidor:** `\\hostname\Futura` — identificado pela presença de `Futura.ini` ou `FuturaServer.exe`
- **Scan de rede:** 5 métodos (auto, paralelo rápido/lento, sequencial rápido/lento), todos usando `ThreadPoolExecutor`
- **Workers:** todos herdam de `QThread` e emitem sinais (`log_line`, `progress`, `finished`)
- **Admin check:** `ctypes.windll.shell32.IsUserAnAdmin()` — exibido na sidebar
- **Log:** singleton `FuturaLogger`, grava em arquivo e emite sinal PyQt para UI em tempo real
- **Backup:** salvo automaticamente antes de qualquer restauração
- **Processos em uso:** detecta e encerra processos na pasta de destino antes de restaurar

## Visual
- Tema dark (`#0d0f12` de fundo), fontes Consolas + Segoe UI
- Sidebar fixa de 240px com indicador de admin e versão
- Stack de páginas com transição por índice
- Componentes customizados: `NavItem`, `MenuCard`, `ServerItem`, `FileCheckItem`, `BackupItem`, `LogConsole`, `ProgressBlock`, `ResultBox`
