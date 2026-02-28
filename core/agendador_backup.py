# =============================================================================
# FUTURA SETUP — core/agendador_backup.py
# Utilitários para criar/remover/consultar Tarefas Agendadas do Windows
# que executam o backup GBAK automaticamente.
#
# A tarefa roda um script Python que chama BackupGbakWorker via subprocess,
# de modo a não precisar de interface gráfica.
# =============================================================================

from __future__ import annotations

import subprocess
import sys
import os


TASK_NAME = "FuturaSetup_BackupGBAK"
_NO_WINDOW = subprocess.CREATE_NO_WINDOW


def criar_tarefa(
    firebird_dir: str,
    dados_fdb: str,
    pasta_backup: str,
    hora: str = "02:00",          # HH:MM
    frequencia: str = "DAILY",    # DAILY | WEEKLY | MONTHLY
) -> tuple[bool, str]:
    """
    Cria (ou substitui) a tarefa agendada FuturaSetup_BackupGBAK.

    Retorna (sucesso: bool, mensagem: str).
    """
    gbak_exe = os.path.join(firebird_dir, "gbak.exe")
    if not os.path.isfile(gbak_exe):
        return False, f"gbak.exe não encontrado em:\n{firebird_dir}"

    # BUG CORRIGIDO: o nome do backup deve usar a data do momento da EXECUÇÃO
    # da tarefa, não do momento da criação. Usando cmd /c com %DATE% e %TIME%
    # para expansão dinâmica em tempo de execução pelo Windows.
    # Formato: DADOS_YYYYMMDD_HHMM.bck
    backup_bck_pattern = os.path.join(pasta_backup, "DADOS_%DATE:~6,4%%DATE:~3,2%%DATE:~0,2%_%TIME:~0,2%%TIME:~3,2%.bck")

    # O comando é encapsulado em cmd /c para permitir a expansão das variáveis
    cmd_backup = (
        f'cmd /c "{gbak_exe}" -b -v '
        f'"localhost:{dados_fdb}" '
        f'"{backup_bck_pattern}"'
    )

    # Monta o schtasks
    try:
        result = subprocess.run(
            [
                "schtasks", "/Create", "/F",
                "/TN",  TASK_NAME,
                "/TR",  cmd_backup,
                "/SC",  frequencia,
                "/ST",  hora,
                "/RL",  "HIGHEST",
            ],
            capture_output=True, text=True, timeout=15,
            creationflags=_NO_WINDOW,
        )
        if result.returncode == 0:
            return True, (
                f"Tarefa '{TASK_NAME}' criada com sucesso.\n"
                f"Frequência: {frequencia}  |  Horário: {hora}\n"
                f"Backup em: {pasta_backup}\n"
                f"Nome do arquivo: DADOS_<DATA>_<HORA>.bck (gerado no momento da execução)"
            )
        else:
            erro = result.stderr.strip() or result.stdout.strip()
            return False, f"schtasks retornou erro:\n{erro}"
    except FileNotFoundError:
        return False, "schtasks não encontrado — execute como Administrador."
    except subprocess.TimeoutExpired:
        return False, "Timeout ao criar tarefa — tente novamente."
    except Exception as e:
        return False, f"Erro inesperado: {e}"


def remover_tarefa() -> tuple[bool, str]:
    """Remove a tarefa agendada se existir."""
    try:
        result = subprocess.run(
            ["schtasks", "/Delete", "/F", "/TN", TASK_NAME],
            capture_output=True, text=True, timeout=10,
            creationflags=_NO_WINDOW,
        )
        if result.returncode == 0:
            return True, f"Tarefa '{TASK_NAME}' removida."
        else:
            return False, result.stderr.strip() or "Tarefa não encontrada."
    except Exception as e:
        return False, str(e)


def tarefa_existe() -> bool:
    """Retorna True se a tarefa FuturaSetup_BackupGBAK já existir."""
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", TASK_NAME],
            capture_output=True, text=True, timeout=10,
            creationflags=_NO_WINDOW,
        )
        return result.returncode == 0
    except Exception:
        return False


def info_tarefa() -> str:
    """Retorna descrição resumida da tarefa existente ou string vazia."""
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"],
            capture_output=True, text=True, timeout=10,
            creationflags=_NO_WINDOW,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""
