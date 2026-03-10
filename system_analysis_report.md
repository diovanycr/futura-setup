# Relatório de Análise: Futura Setup v4.3.0

## Visão Geral
O **Futura Setup** é uma ferramenta robusta de automação de TI desenvolvida em **Python 3.12** com a interface **PyQt6**. Seu objetivo principal é facilitar a configuração, manutenção e atualização de terminais Windows que utilizam o ecossistema de software da **Futura Sistemas** (ERP e PDV).

---

## Arquitetura do Sistema

O projeto segue uma estrutura modular bem definida, separando a lógica de negócio da interface do usuário.

### 1. Núcleo (Core)
- **`core/network.py`**: Gerencia a descoberta de servidores na rede local. Utiliza cache ARP e testes de conectividade via SMB (porta 445/TCP 80) para identificar máquinas que possuem o compartilhamento "Futura" ativo.
- **`core/installer.py`**: Contém os *workers* principais para operações de longa duração (Instalação, Restauração e Atalhos). Implementa verificação de integridade via **SHA-256**, gestão automática de backups (mantendo os últimos 5) e criação de atalhos via Win32 COM.
- **`core/atualizador.py`**: Orquestra a atualização completa do ERP. Inclui lógica sensível como:
    - Parada e reinício de serviços **Firebird**.
    - Renomeação de bancos de dados para segurança (`_temp.fdb`).
    - Configuração automática do `PESQUISA.INI`.
- **`core/logger.py`**: Singleton global que gerencia logs rotativos e preferências do usuário em `%APPDATA%\Futura\`.

### 2. Interface (UI)
- **Sistema de Temas**: Implementado em `ui/theme.py` e `ui/theme_manager.py`, permitindo alternância dinâmica entre modo Claro (Light) e Escuro (Dark).
- **Widgets Reutilizáveis**: `ui/widgets.py` contém uma biblioteca de componentes customizados (Alertas, Barras de Progresso, Consoles de Log) que seguem um padrão visual moderno e consistente.
- **Navegação**: Baseada em um `QStackedWidget` no `main.py`, garantindo uma experiência de usuário fluida através de diferentes etapas (Scan → Seleção → Execução).

### 3. Configuração e Segurança
- **`config.py`**: Centraliza URLs de repositório, constantes de timeout, nomes de processos conhecidos e caminhos padrão.
- **Segurança**: O acesso ao sistema é protegido por uma senha (verificada via hash SHA-256 no `main.py`).

---

## Pontos Fortes Observados
1. **Confiabilidade**: O uso de retentativas para download/cópia e validação de hash garante que os terminais sejam configurados sem arquivos corrompidos.
2. **Segurança de Operação**: A lógica de backup obrigatório antes de qualquer alteração na pasta do sistema minimiza riscos de perda de dados.
3. **Escalabilidade**: O sistema de *workers* baseados em `QThread` mantém a interface responsiva mesmo durante operações pesadas de rede ou disco.
4. **Manutenibilidade**: O uso de Singletons para Logger e ThemeManager e a centralização de configurações facilitam futuras expansões.

---

## Fluxos Principais
- **Instalação de Terminal**: Scan de Rede → Escolha de Servidor → Seleção de EXEs → Cópia + DLLs + Atalhos.
- **Atualização Completa**: Detecção Local → Backup do Banco → Parar Firebird → Baixar Atualizador → Configurar INI → Executar.

---
*Análise gerada em 10 de Março de 2026.*
