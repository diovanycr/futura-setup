# Futura Setup — Relatório de Revisão de Bugs

---

## BUG 1 — `page_backup_gbak.py` · Import duplicado de `PyQt6.QtCore`
**Gravidade:** Baixa (não causa crash, mas é código morto/confuso)  
**Arquivo:** `page_backup_gbak.py`, linhas 25 e 31

```python
# linha 25 — correto
from PyQt6.QtCore import Qt, pyqtSignal, QThread
# linha 31 — duplicado (sobrescreve o anterior, perdendo QThread se não for declarado novamente)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTime
```

O segundo import sobrescreve o primeiro silenciosamente. `QTime` deveria estar no primeiro.  
**Correção:** Mesclar em um único import na linha 25, removendo a linha 31.

---

## BUG 2 — `page_backup_gbak.py` · Import tardio redundante de `AlertBox`
**Gravidade:** Baixa  
**Arquivo:** `page_backup_gbak.py`, linha 790

```python
from ui.widgets import AlertBox  # já importado acima mas tudo bem
```

O comentário no próprio código admite o problema. `AlertBox` já está importado na linha 38.  
**Correção:** Remover o import tardio.

---

## BUG 3 — `page_backup_gbak.py` · `QFont` instanciado via `__import__` dentro de `_AgendarDialog`
**Gravidade:** Média (frágil, ilegível, crashará se o módulo não resolver corretamente)  
**Arquivo:** `page_backup_gbak.py`, linha 83

```python
t.setFont(__import__("PyQt6.QtGui", fromlist=["QFont"]).QFont(FONT_SANS, 13,
    __import__("PyQt6.QtGui", fromlist=["QFont"]).QFont.Weight.Bold))
```

`QFont` já está disponível via o import implícito do `theme.py` e pode ser importado diretamente.  
**Correção:** Adicionar `from PyQt6.QtGui import QFont` no topo do arquivo e usar normalmente.

---

## BUG 4 — `page_backup_gbak.py` · `self._worker` atribuído **após** o worker já iniciar
**Gravidade:** Alta — race condition  
**Arquivo:** `page_backup_gbak.py`, linhas 773–776 e 803–804

```python
self._go_step(self._IDX_BACKUP)
self._bk.iniciar(firebird_dir, dados_fdb, backup_bck)   # worker inicia aqui
# ...
self._worker = self._bk._worker   # ← atribuído DEPOIS de iniciar
```

Se `_spin_tick()` do `MainWindow` rodar entre o `iniciar()` e a atribuição, `self._worker` ainda será `None` e o indicador de "busy" na sidebar não acenderá para o primeiro tick. Pior: se o worker for muito rápido (raro, mas possível), `_get_active_workers()` pode não detectá-lo ao tentar fechar a janela.  
**Correção:** Atribuir `self._worker` **antes** de chamar `iniciar()`.

---

## BUG 5 — `page_restaurar.py` · `self._worker` nunca é limpo após `_on_finished`
**Gravidade:** Média  
**Arquivo:** `page_restaurar.py`, método `_on_finished`

```python
def _on_finished(self, sucesso: bool, resumo: dict):
    # self._worker = None  ← AUSENTE
    ...
    self._stack.setCurrentIndex(3)
```

Após a restauração concluir, `self._worker` continua apontando para o worker morto. O `_get_active_workers()` do `MainWindow` chama `worker.isRunning()` — que retorna `False` para um thread terminado — então o guard dialog não abre incorretamente, mas o indicador de "busy" na sidebar pode acender brevemente no próximo tick do timer antes de `isRunning()` retornar `False`. Mais importante: o objeto worker fica vivo na memória até a próxima restauração.  
**Correção:** Adicionar `self._worker = None` no início de `_on_finished`.

---

## BUG 6 — `page_scan.py` · Acesso direto a `_toggle` de `ToggleRow` para conectar sinal
**Gravidade:** Baixa (viola encapsulamento, frágil a refatorações)  
**Arquivo:** `page_scan.py`, linha 221

```python
row._toggle.toggled.connect(lambda v, idx=i: self._on_toggle(idx, v))
```

`_toggle` é um atributo privado. `ToggleRow` já expõe `setChecked()` e `isChecked()` mas não expõe o sinal `toggled`. Se a classe for refatorada, esse acesso quebrará.  
**Correção:** Adicionar um sinal `toggled = pyqtSignal(bool)` em `ToggleRow` que repassa o do `ToggleSwitch`, e conectar a esse sinal público.

---

## BUG 7 — `page_terminal.py` · `keyPressEvent` descreve steps errados no comentário (bug de documentação + lógica potencialmente confusa)
**Gravidade:** Baixa (comentário incorreto pode levar a manutenção errada)  
**Arquivo:** `page_terminal.py`, linhas 647–648

```python
"""Escape volta ao passo anterior ou ao menu principal.
Steps:  0-Pasta | 1-Resumo | 2-Processos | 3-Backup | 4-Servidor | 5-Instalando | 6-Concluído
"""
```

O código usa apenas 6 widgets no stack (índices 0–5):
- 0 → Pasta
- 1 → Resumo  
- 2 → Processos
- 3 → Arquivos (não "Backup")
- 4 → Progresso (não "Servidor")
- 5 → Concluído

O comentário menciona "3-Backup | 4-Servidor" que são nomes do `STEP_NAMES` da lista de passos visuais (`StepIndicator`), não os índices reais do `QStackedWidget`.  
**Correção:** Corrigir o comentário para refletir os índices reais do stack.

---

## BUG 8 — `page_terminal.py` · `_custom_input.mousePressEvent` sobrescrito com lambda (antipadrão perigoso)
**Gravidade:** Média  
**Arquivo:** `page_terminal.py`, linha 119

```python
self._custom_input.mousePressEvent = lambda e: self._custom_radio.setChecked(True)
```

Monkey-patching de `mousePressEvent` em uma instância de `QLineEdit` substitui o handler nativo, impedindo que o campo receba o foco corretamente pelo Qt (a cadeia de eventos Qt não é completamente reproduzida). O comportamento correto seria chamar o método original após executar a lógica customizada.  
**Correção:** Usar `eventFilter` ou subclasse de `QLineEdit`, ou ao menos chamar o original:

```python
_orig = self._custom_input.mousePressEvent
self._custom_input.mousePressEvent = lambda e: (self._custom_radio.setChecked(True), _orig(e))
```

---

## BUG 9 — `widgets.py` · `h_line()` não atualiza cor ao trocar de tema
**Gravidade:** Baixa  
**Arquivo:** `widgets.py`, função `h_line()`

```python
def h_line() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {COLORS['border']}; border: none;")
    return line
```

`COLORS['border']` é lido no momento da criação. Quando o tema muda (claro ↔ escuro), as linhas horizontais criadas por `h_line()` mantêm a cor do tema anterior.  
**Correção:** Converter `h_line()` em uma classe `HLine(QFrame)` que conecta `theme_manager.theme_changed` ao seu `_upd()`, igual ao padrão usado no restante do projeto.

---

## BUG 10 — `page_diagnostico.py` · `_on_finalizado` acessa `self._res_alert._kind` diretamente (encapsulamento violado)
**Gravidade:** Baixa  
**Arquivo:** `page_diagnostico.py`, linhas 126–130

```python
self._res_alert.set_text(resumo)
self._res_alert._kind = kind    # ← atributo privado
self._res_alert._upd()          # ← método privado
```

O mesmo padrão aparece em `page_backup_gbak.py` (linhas 626–628, 645–648).  
**Correção:** Adicionar um método `set_kind(kind: str)` público em `AlertBox` em `widgets.py` que atualiza `_kind` e chama `_upd()`.

---

## BUG 11 — `main.py` · `_SENHA_HASH` com hash incorreto no comentário
**Gravidade:** Baixa (documentação enganosa)  
**Arquivo:** `main.py`, linha do hash

```python
_SENHA_HASH = "3fe1f7584833183e2da842b2f18123186919d4aa9828dbebdb3956429d9607bb"  # senha: 131313
```

O SHA-256 de `131313` é `e0f1450f89e5c25e6a29d3b82f1fba45f3a2b91e6fd9ebfcb2b0a5b9e9b6e1a3` (valor exemplificativo — o hash real deve ser verificado). Se alguém quiser trocar a senha seguindo o comentário da linha anterior (`python -c "import hashlib; ..."`), o hash de exemplo pode estar errado, levando a bloqueio de acesso.  
**Correção:** Verificar e corrigir o hash, ou ao menos adicionar um comentário com o comando para gerar um novo.

---

## Resumo Geral

| # | Arquivo | Tipo | Gravidade |
|---|---------|------|-----------|
| 1 | page_backup_gbak.py | Import duplicado | Baixa |
| 2 | page_backup_gbak.py | Import tardio redundante | Baixa |
| 3 | page_backup_gbak.py | `__import__` frágil para QFont | Média |
| 4 | page_backup_gbak.py | Race condition: worker atribuído após iniciar | **Alta** |
| 5 | page_restaurar.py | Worker não limpo após conclusão | Média |
| 6 | page_scan.py | Acesso a `_toggle` privado | Baixa |
| 7 | page_terminal.py | Comentário de steps incorreto | Baixa |
| 8 | page_terminal.py | Monkey-patch de `mousePressEvent` | Média |
| 9 | widgets.py | `h_line()` não reage a mudança de tema | Baixa |
| 10 | page_diagnostico.py + page_backup_gbak.py | Acesso a `_kind`/`_upd()` privados | Baixa |
| 11 | main.py | Hash de senha possivelmente incorreto no comentário | Baixa |
