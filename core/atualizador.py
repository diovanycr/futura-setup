# =============================================================================
# FUTURA SETUP — Módulo: Atualização Completa do Sistema
# Convertido de Futura-AtualizacaoCompleta.ps1 v2.6.0
# Melhorias v2:
#   - _atualizar_secao: substituído por configparser (stdlib) — remove ~50 linhas frágeis
#   - banco_temp: usa Path.stem em vez de str.replace (evita substituição errada)
#   - find_instalacoes: corrigido duplo timeout redundante
#   - download_*: reutiliza funções de installer.py (sem duplicação)
# =============================================================================

import os
import re
import shutil
import string
import subprocess
import tempfile
import time
import zipfile
import configparser
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.logger import log
from core.installer import download_com_retry, _BaseWorker
from core.firebird_services import (
    stop_firebird_services, start_firebird_services, find_firebird_dir,
)
from config import (
    URL_DLLS, URL_ATUALIZADOR, MAX_TENTATIVAS_DOWNLOAD,
    FIREBIRD_CONF_PATHS, FIREBIRD_SERVICES, CONNECTIVITY_HOSTS,
)


# ── DETECÇÃO DE INSTALAÇÕES ───────────────────────────────────────────────────

def find_instalacoes() -> list[str]:
    """
    Busca pastas com Futura.ini em todos os drives disponíveis.
    Usa timeout por drive para não travar em drives de rede ou removíveis lentos.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    pastas: list[str] = []

    try:
        drives = [
            f"{d}:\\"
            for d in string.ascii_uppercase
            if Path(f"{d}:\\").exists()
        ]
    except Exception:
        drives = ["C:\\"]

    def _buscar_drive(drive: str) -> list[str]:
        encontradas = []
        try:
            for item in Path(drive).iterdir():
                if item.is_dir():
                    if (item / "Futura.ini").exists() and str(item) not in encontradas:
                        encontradas.append(str(item))
            # Profundidade 2 apenas em C:\
            if drive.upper().startswith("C"):
                for ini in Path(drive).glob("*/*/Futura.ini"):
                    pasta = str(ini.parent)
                    if pasta not in encontradas:
                        encontradas.append(pasta)
        except PermissionError:
            pass  # Drive sem permissão de leitura — ignorado silenciosamente
        except Exception as e:
            log.warn(f"Erro ao buscar instalações em {drive}: {e}")
        return encontradas

    # Um único timeout global de 30s — sem duplo timeout redundante
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_buscar_drive, d): d for d in drives}
        for f in as_completed(futures, timeout=30):
            try:
                for p in f.result():
                    if p not in pastas:
                        pastas.append(p)
            except Exception:
                drive = futures[f]
                log.warn(f"Timeout ou erro ao buscar em {drive} — ignorado")

    return pastas


# ── DETECÇÃO DE BANCO DE DADOS ────────────────────────────────────────────────

def _find_banco_alternativo(caminho_original: str) -> Optional[str]:
    pasta     = Path(caminho_original).parent
    nome_base = Path(caminho_original).stem
    temp_path = pasta / f"{nome_base}_temp.fdb"
    if temp_path.exists():
        return str(temp_path)
    for f in pasta.glob(f"{nome_base}*.fdb"):
        return str(f)
    return None


def _get_bancos_firebird(excluir_temp: bool = False) -> list[dict]:
    bancos = []
    for conf_path in FIREBIRD_CONF_PATHS:
        if not Path(conf_path).exists():
            continue
        try:
            dentro_live = False
            with open(conf_path, encoding="utf-8", errors="ignore") as f:
                for linha in f:
                    linha = linha.strip()
                    if re.search(r"Live\s+Databases", linha, re.IGNORECASE):
                        dentro_live = True
                        continue
                    if not dentro_live:
                        continue
                    if linha.startswith("#") or not linha:
                        continue
                    m = re.match(r"(\S+)\s*=\s*(.+\.fdb)", linha)
                    if m:
                        alias   = m.group(1).strip()
                        caminho = m.group(2).strip()
                        if excluir_temp and caminho.endswith("_temp.fdb"):
                            continue
                        status = "OK"
                        if not Path(caminho).exists():
                            alt = _find_banco_alternativo(caminho)
                            if alt:
                                if excluir_temp and alt.endswith("_temp.fdb"):
                                    continue
                                caminho = alt
                                status  = "Renomeado"
                            else:
                                status = "NaoExiste"
                        bancos.append({"alias": alias, "caminho": caminho,
                                       "status": status, "fonte": "Firebird"})
            if bancos:
                break
        except PermissionError as e:
            log.warn(f"Sem permissão para ler configuração do Firebird: {conf_path}: {e}")
        except Exception as e:
            # BUG CORRIGIDO: falha silenciosa — agora loga o erro
            log.warn(f"Erro ao ler configuração do Firebird em {conf_path}: {e}")
    return bancos


def _get_bancos_locais(pasta: str, excluir_temp: bool = False) -> list[dict]:
    bancos = []
    locais = [
        Path(pasta) / "dados" / "dados.fdb",
        Path(pasta) / "dados.fdb",
        Path(pasta) / "FuturaDados" / "dados.fdb",
        Path(pasta) / "Database" / "dados.fdb",
        Path(pasta) / "DB" / "dados.fdb",
    ]
    for loc in locais:
        if loc.exists():
            if excluir_temp and str(loc).endswith("_temp.fdb"):
                continue
            bancos.append({"alias": loc.name, "caminho": str(loc),
                           "status": "OK", "fonte": "Local Padrão"})
    return bancos


def _get_bancos_recursivo(pasta: str, excluir_temp: bool = False) -> list[dict]:
    bancos = []
    try:
        for f in Path(pasta).rglob("*.fdb"):
            if excluir_temp and f.name.endswith("_temp.fdb"):
                continue
            bancos.append({"alias": f.name, "caminho": str(f),
                           "status": "OK", "fonte": "Busca Recursiva"})
    except Exception:
        pass
    return bancos


def find_bancos(pasta: str, excluir_temp: bool = False) -> list[dict]:
    """Retorna lista de bancos .fdb usando múltiplas estratégias."""
    bancos = _get_bancos_firebird(excluir_temp)
    if not bancos:
        bancos = _get_bancos_locais(pasta, excluir_temp)
    if not bancos:
        bancos = _get_bancos_recursivo(pasta, excluir_temp)
    return [b for b in bancos if b["status"] != "NaoExiste"]








# ── DOWNLOAD ──────────────────────────────────────────────────────────────────
# Reutiliza download_com_retry de installer.py para evitar duplicação

def _get_download_fn():
    """Importação lazy para evitar import circular."""
    from core.installer import download_com_retry, _download_arquivo
    return download_com_retry, _download_arquivo


def download_dlls(destino: str, progress_cb=None) -> bool:
    """Baixa e extrai DLLx86.zip para a pasta destino."""
    download_com_retry, _ = _get_download_fn()
    # BUG CORRIGIDO: antes usava int(time.time()) em dois lugares separados,
    # podendo gerar timestamps diferentes (ex: 1700000000 e 1700000001)
    # se a chamada cruzasse a virada do segundo, tornando o caminho de extração
    # inconsistente com o arquivo baixado.
    ts = int(time.time())
    tmp = Path(tempfile.gettempdir()) / f"dlls_{ts}.zip"
    try:
        ok = download_com_retry(URL_DLLS, str(tmp), "Baixando DLLs", progress_cb)
        if not ok:
            return False

        extract = Path(tempfile.gettempdir()) / f"dlls_{ts}_extracted"
        extract.mkdir(exist_ok=True)
        try:
            with zipfile.ZipFile(tmp, "r") as z:
                z.extractall(extract)
        except Exception as e:
            log.error(f"Erro ao extrair DLLs: {e}")
            # BUG CORRIGIDO: pasta extract ficava órfã no TEMP quando a extração falhava
            shutil.rmtree(extract, ignore_errors=True)
            return False

        n = 0
        erros = 0
        for src in extract.rglob("*"):
            if src.is_file():
                dst = Path(destino) / src.relative_to(extract)
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(str(src), str(dst))
                    n += 1
                except Exception as e:
                    log.warn(f"Erro ao copiar DLL {src.name}: {e}")
                    erros += 1

        shutil.rmtree(extract, ignore_errors=True)
        if erros:
            log.warn(f"DLLs instaladas com {erros} erro(s): {n} arquivo(s) copiado(s)")
        else:
            log.ok(f"DLLs instaladas: {n} arquivo(s)")
        return n > 0
    finally:
        tmp.unlink(missing_ok=True)


# ── PESQUISA.INI ──────────────────────────────────────────────────────────────

def criar_pesquisa_ini(pasta_instalacao: str,
                       pasta_firebird: Optional[str],
                       caminho_banco: str) -> bool:
    """
    Cria ou atualiza PESQUISA.INI com as configurações de atualização.
    Usa manipulação de texto direta para garantir compatibilidade com TIniFile do Delphi 
    (sem espaços ao redor do '=').
    """
    try:
        if not pasta_firebird:
            pasta_firebird = find_firebird_dir() or r"C:\Program Files\Firebird\Firebird_4_0"

        pasta_backup = Path(pasta_instalacao) / "backup"
        pasta_backup.mkdir(parents=True, exist_ok=True)

        valores = {
            "PASTA_FIREBIRD": pasta_firebird,
            "PASTA_BACKUP":   str(pasta_backup),
            "PASTA_SISTEMA":  pasta_instalacao,
            "BASE_IP":        "localhost",
            "BASE_PATH":      caminho_banco,
        }

        # Extrai a lógica de escrita para uma função interna para reutilizar
        def _escrever_ini(caminho_arquivo: Path):
            linhas = []
            if caminho_arquivo.exists():
                shutil.copy2(str(caminho_arquivo), str(caminho_arquivo) + ".bak")
                with open(caminho_arquivo, "r", encoding="cp1252", errors="ignore") as f:
                    linhas = f.read().splitlines()

            secao = "[ATUALIZADO_AUTOMATICO]"
            idx_secao: int = -1
            
            for i, linha in enumerate(linhas):
                if linha.strip().upper() == secao:
                    idx_secao = i
                    break
                    
            if idx_secao == -1:
                linhas.append("")
                linhas.append(secao)
                idx_secao = len(linhas) - 1

            chaves_alvo = list(valores.keys())
            i = int(idx_secao) + 1
            while i < len(linhas):
                linha = linhas[i].strip()
                if linha.startswith("[") and linha.endswith("]"):
                    break 
                
                if "=" in linha:
                    k = linha.split("=", 1)[0].strip()
                    if k.upper() in chaves_alvo:
                        linhas.pop(i)
                        continue
                i += 1

            for k, v in reversed(list(valores.items())):
                linhas.insert(int(idx_secao) + 1, f"{k}={v}")

            with open(caminho_arquivo, "w", encoding="cp1252") as f:
                f.write("\n".join(linhas) + "\n")

        # 1. Escreve na pasta principal selecionada
        arquivo_principal = Path(pasta_instalacao) / "PESQUISA.INI"
        _escrever_ini(arquivo_principal)
        log.ok(f"PESQUISA.INI gravado: {arquivo_principal}")

        # 2. Escreve também em C:\FUTURA caso exista e seja diferente da pasta selecionada
        pasta_padrao = Path("C:\\FUTURA")
        if pasta_padrao.exists() and pasta_padrao.resolve() != Path(pasta_instalacao).resolve():
            arquivo_padrao = pasta_padrao / "PESQUISA.INI"
            _escrever_ini(arquivo_padrao)
            log.ok(f"PESQUISA.INI gravado (fallback): {arquivo_padrao}")
        return True

    except Exception as e:
        log.error(f"Erro ao criar PESQUISA.INI: {e}")
        return False


# ── WORKER PRINCIPAL ──────────────────────────────────────────────────────────

class AtualizacaoWorker(_BaseWorker):
    """
    Executa a atualização completa em background.

    Sinais:
        log_line(msg, kind)
        progress(pct, titulo, subtitulo)
        finished(sucesso, resumo)
        precisa_pasta(lista_pastas)  — UI deve escolher e reiniciar worker
        precisa_banco(lista_bancos)  — UI deve escolher e reiniciar worker

    Fluxo com seleção pendente:
        Quando há múltiplas opções, o worker emite precisa_pasta/precisa_banco
        e retorna. A página de UI instancia um novo AtualizacaoWorker com
        pasta_escolhida/banco_escolhido preenchidos e inicia novamente.
    """
    finished      = pyqtSignal(bool, dict)
    precisa_pasta = pyqtSignal(list)
    precisa_banco = pyqtSignal(list)

    _LOG_PREFIX = "[Atualizacao]"

    def __init__(self, pasta_escolhida: str = "",
                 banco_escolhido: str = "",
                 parent=None):
        super().__init__(parent)
        self._pasta = pasta_escolhida
        self._banco = banco_escolhido
        # Rastreia serviços parados para garantir reinício mesmo em falhas
        self._servicos_parados: list[str] = []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _reiniciar_firebird(self):
        """
        Reinicia os serviços do Firebird que foram parados por este worker.
        Idempotente: limpa _servicos_parados após reiniciar para não tentar duas vezes.
        """
        if not self._servicos_parados:
            return
        self._log("Reiniciando Firebird...", "info")
        start_firebird_services(self._servicos_parados)
        self._servicos_parados = []
        self._log("Firebird reiniciado", "ok")

    # ── run ───────────────────────────────────────────────────────────────────

    def run(self):
        self._log("=== INICIANDO ATUALIZAÇÃO COMPLETA ===", "info")

        try:
            # 1. Detectar pasta de instalação
            if not self._pasta:
                self._log("Buscando instalações do Futura...", "info")
                self._pct(5, "Detectando instalação...", "Buscando Futura.ini")
                pastas = find_instalacoes()
                if not pastas:
                    self._log("Nenhuma instalação encontrada!", "err")
                    self.finished.emit(False, {"erro": "Nenhuma instalação encontrada"})
                    return
                if len(pastas) == 1:
                    self._pasta = pastas[0]
                    self._log(f"Instalação detectada: {self._pasta}", "ok")
                else:
                    # Worker suspende; UI reiniciará com _pasta preenchida
                    self.precisa_pasta.emit(pastas)
                    return

            # 2. Detectar banco de dados
            if not self._banco:
                self._log(f"Buscando banco de dados em: {self._pasta}", "info")
                self._pct(10, "Localizando banco...", "Verificando Firebird e .fdb")
                bancos = find_bancos(self._pasta)
                if not bancos:
                    self._log("Nenhum banco .fdb encontrado!", "err")
                    self.finished.emit(False, {"erro": "Banco de dados não encontrado"})
                    return
                if len(bancos) == 1:
                    self._banco = bancos[0]["caminho"]
                    self._log(f"Banco detectado: {self._banco}", "ok")
                else:
                    self.precisa_banco.emit(bancos)
                    return

            if self._stop:
                return

            # 3. Parar Firebird e renomear banco
            banco_path         = Path(self._banco)
            banco_ja_renomeado = self._banco.endswith("_temp.fdb")

            if not banco_ja_renomeado:
                self._log("Parando serviços do Firebird...", "info")
                self._pct(20, "Parando Firebird...", "Aguardando liberação do banco")
                self._servicos_parados = stop_firebird_services()
                if self._servicos_parados:
                    self._log(f"Serviços parados: {', '.join(self._servicos_parados)}", "ok")
                else:
                    self._log("Nenhum serviço do Firebird estava ativo", "warn")

                banco_temp = banco_path.with_name(banco_path.stem + "_temp.fdb")
                self._log(f"Renomeando banco: {banco_path.name}", "info")
                self._pct(30, "Renomeando banco...", banco_path.name)
                try:
                    if banco_temp.exists():
                        banco_temp.unlink()
                    banco_path.rename(banco_temp)
                    self._banco = str(banco_temp)
                    self._log(f"Banco renomeado para: {banco_temp.name}", "ok")
                except Exception as e:
                    self._log(f"Erro ao renomear banco: {e}", "err")
                    # Firebird já foi parado — reinicia antes de retornar
                    self._reiniciar_firebird()
                    self.finished.emit(False, {"erro": str(e)})
                    return

                self._log("Reiniciando Firebird...", "info")
                self._reiniciar_firebird()
                self._log("Firebird reiniciado", "ok")
            else:
                self._log("Banco já renomeado (_temp.fdb) — pulando etapa", "warn")

            if self._stop:
                # BUG CORRIGIDO: se cancelado após o Firebird ter sido parado (passo 3),
                # os serviços ficavam parados indefinidamente. Garante reinício antes de sair.
                self._reiniciar_firebird()
                return

            # 4. Baixar Atualizador.exe
            at_dir = Path(self._pasta) / "Atualizador"
            shutil.rmtree(at_dir, ignore_errors=True)
            at_dir.mkdir(parents=True, exist_ok=True)
            exe = str(at_dir / "Atualizador.exe")

            self._log("Baixando Atualizador.exe...", "info")
            self._pct(40, "Baixando atualizador...", "Atualizador.exe")

            def prog_exe(baixado, total):
                # BUG CORRIGIDO: total pode ser 0 se o servidor não enviar Content-Length
                if total > 0:
                    pct = 40 + int((baixado / total) * 20)
                    mb  = round(baixado / 1048576, 1)
                    self._pct(pct, "Baixando Atualizador.exe...", f"{mb} MB")

            ok = download_com_retry(URL_ATUALIZADOR, exe, "Atualizador.exe", prog_exe)
            if not ok:
                self._log("Falha ao baixar Atualizador.exe", "err")
                self.finished.emit(False, {"erro": "Falha ao baixar Atualizador.exe"})
                return
            self._log("Atualizador.exe baixado", "ok")

            if self._stop:
                # BUG CORRIGIDO: garante reinício do Firebird se cancelado neste ponto
                self._reiniciar_firebird()
                return

            # 5. Baixar DLLs
            self._log("Baixando DLLs do sistema...", "info")
            self._pct(62, "Baixando DLLs...", "DLLx86.zip")

            def prog_dll(baixado, total):
                # BUG CORRIGIDO: total pode ser 0 se o servidor não enviar Content-Length
                if total > 0:
                    pct = 62 + int((baixado / total) * 18)
                    mb  = round(baixado / 1048576, 1)
                    self._pct(pct, "Baixando DLLs...", f"{mb} MB")

            dlls_ok = download_dlls(str(at_dir), prog_dll)
            if not dlls_ok:
                self._log("Aviso: falha ao baixar DLLs — atualizador pode não funcionar", "warn")
            else:
                self._log("DLLs instaladas com sucesso", "ok")

            if self._stop:
                # BUG CORRIGIDO: garante reinício do Firebird se cancelado neste ponto
                self._reiniciar_firebird()
                return

            # 6. Criar PESQUISA.INI
            self._log("Configurando PESQUISA.INI...", "info")
            self._pct(82, "Configurando PESQUISA.INI...", "")
            firebird_dir = find_firebird_dir()
            ini_ok = criar_pesquisa_ini(self._pasta, firebird_dir, self._banco)
            if ini_ok:
                self._log("PESQUISA.INI configurado", "ok")
            else:
                self._log("Aviso: falha ao criar PESQUISA.INI — configuração manual necessária", "warn")

            # 7. Executar Atualizador.exe
            self._log("Iniciando Atualizador.exe...", "info")
            self._pct(92, "Iniciando atualizador...", exe)
            try:
                subprocess.Popen([exe], cwd=str(at_dir))
                self._log("Atualizador iniciado em nova janela", "ok")
            except Exception as e:
                self._log(f"Erro ao executar atualizador: {e}", "err")
                self.finished.emit(False, {"erro": f"Erro ao executar atualizador: {e}"})
                return

            self._pct(100, "Concluído!", "")
            self._log("=== ATUALIZAÇÃO PREPARADA COM SUCESSO ===", "ok")
            self.finished.emit(True, {
                "pasta":       self._pasta,
                "banco":       self._banco,
                "atualizador": exe,
                "dlls":        "OK" if dlls_ok else "Aviso",
                "ini":         "OK" if ini_ok  else "Aviso",
            })

        except Exception as e:
            self._log(f"Erro geral: {e}", "err")
            log.error(f"AtualizacaoWorker erro geral: {e}")
            # Garante reinício do Firebird mesmo em exceção não tratada
            self._reiniciar_firebird()
            self.finished.emit(False, {"erro": str(e)})
