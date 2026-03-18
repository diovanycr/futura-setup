# =============================================================================
# FUTURA SETUP — Core: Security Database para Firebird INSTALADO
#
# Garante que o SYSDBA tem a senha correta no Firebird instalado via .exe
# (Program Files), diferente do portable que usa fb_portable.py.
#
# Salvar em: core/firebird_installer_security.py
# =============================================================================
from __future__ import annotations

import os
import subprocess
import time

# Credenciais padrão do Futura
_FB_USER     = "SYSDBA"
_FB_PASSWORD = "sbofutura"

# Senhas de fábrica que o instalador pode ter definido
_SENHAS_FABRICA = ["sbofutura", "masterkey", "masterke", ""]


def _encontrar_exe_instalado(pasta: str, nomes: list[str]) -> str:
    """Procura um executável na pasta de instalação e em subpasta 'bin'."""
    for subdir in ("", "bin"):
        base = os.path.join(pasta, subdir) if subdir else pasta
        for nome in nomes:
            p = os.path.join(base, nome)
            if os.path.isfile(p):
                return p
    return ""


def _security_db_path_instalado(pasta: str, versao: str) -> str:
    """Retorna o caminho do security DB do Firebird instalado."""
    nome = f"security{versao}.fdb"
    # Pode estar na raiz ou em subpasta
    for subdir in ("", "bin"):
        base = os.path.join(pasta, subdir) if subdir else pasta
        p = os.path.join(base, nome)
        if os.path.isfile(p):
            return p
    return os.path.join(pasta, nome)


def _servico_rodando_instalado(versao: str) -> bool:
    """Verifica se algum serviço do Firebird instalado está rodando."""
    candidatos = [
        "FirebirdServerDefaultInstance",
        "FirebirdGuardianDefaultInstance",
        "FirebirdServer",
        "FirebirdGuardian",
    ]
    try:
        import subprocess
        for nome in candidatos:
            r = subprocess.run(
                ["sc", "query", nome],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0 and "RUNNING" in r.stdout:
                return True
    except Exception:
        pass
    return False


def _parar_servico_instalado_tmp(log_fn=None) -> list[str]:
    """Para todos os serviços Firebird instalados. Retorna lista dos que estavam rodando."""
    def log(m):
        if log_fn: log_fn(m)

    candidatos = [
        "FirebirdGuardianDefaultInstance",
        "FirebirdServerDefaultInstance",
        "FirebirdGuardian",
        "FirebirdServer",
    ]
    parados = []
    for nome in candidatos:
        try:
            r = subprocess.run(["sc", "query", nome], capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and "RUNNING" in r.stdout:
                log(f"  Parando servico '{nome}' temporariamente ...")
                subprocess.run(["net", "stop", nome], capture_output=True, timeout=30)
                parados.append(nome)
        except Exception:
            pass
    if parados:
        time.sleep(2)
    return parados


def _iniciar_servicos(nomes: list[str], log_fn=None):
    """Inicia uma lista de serviços."""
    def log(m):
        if log_fn: log_fn(m)

    for nome in nomes:
        try:
            log(f"  Reiniciando servico '{nome}' ...")
            subprocess.run(["net", "start", nome], capture_output=True, timeout=30)
            time.sleep(2)
        except Exception:
            pass


def _contem_erro_fatal(saida: str) -> bool:
    """Retorna True se a saída contém erro real."""
    s = saida.lower()
    # Ignora warnings conhecidos
    for trecho in ["install incomplete", "please read", "compatibility", "release notes"]:
        s = s.replace(trecho, "")
    return any(k in s for k in ["error", "failed", "invalid", "denied", "cannot", "unable"])


# =============================================================================
# FB3 instalado — configura SYSDBA via gsec
# =============================================================================

def _configurar_sysdba_fb3_gsec(pasta: str, log_fn=None) -> bool:
    """
    Configura SYSDBA no security3.fdb via gsec.exe direto no arquivo.
    Funciona sem servidor rodando.
    """
    def log(m):
        if log_fn: log_fn(m)

    gsec     = _encontrar_exe_instalado(pasta, ["gsec.exe"])
    sec_path = _security_db_path_instalado(pasta, "3")

    if not gsec:
        log("  [FB3] gsec.exe nao encontrado na pasta de instalacao.")
        return False
    if not os.path.isfile(sec_path):
        log(f"  [FB3] security3.fdb nao encontrado: {sec_path}")
        return False

    env = os.environ.copy()
    env["FIREBIRD"] = pasta

    log(f"  [FB3] Configurando SYSDBA via gsec: {sec_path}")

    for senha_atual in _SENHAS_FABRICA:
        cmd = [gsec, "-database", sec_path, "-user", _FB_USER]
        if senha_atual:
            cmd += ["-password", senha_atual]
        cmd += ["-modify", _FB_USER, "-pw", _FB_PASSWORD]

        try:
            r = subprocess.run(
                cmd, cwd=pasta, env=env,
                capture_output=True, text=True,
                encoding="utf-8", errors="ignore", timeout=15,
            )
            saida = (r.stdout + r.stderr).strip()
            if saida:
                log(f"    gsec (pw={senha_atual!r}): {saida[:200]}")
            if r.returncode == 0 and not _contem_erro_fatal(saida):
                log(f"  [FB3] SYSDBA configurado com senha '{_FB_PASSWORD}'.")
                return True
        except Exception as e:
            log(f"    gsec erro: {e}")

    return False


def _configurar_sysdba_fb3_isql_tcp(pasta: str, log_fn=None) -> bool:
    """
    Fallback FB3: configura SYSDBA via isql TCP.
    Sobe o servidor temporariamente se necessário.
    """
    def log(m):
        if log_fn: log_fn(m)

    isql    = _encontrar_exe_instalado(pasta, ["isql.exe"])
    fbserver = _encontrar_exe_instalado(pasta, ["firebird.exe", "fbserver.exe"])

    if not isql:
        log("  [FB3] isql.exe nao encontrado.")
        return False

    log("  [FB3] Tentando configurar SYSDBA via isql TCP ...")

    proc_tmp = None
    servidor_rodando = _servico_rodando_instalado("3")

    if not servidor_rodando and fbserver:
        log("  [FB3] Subindo servidor temporario ...")
        env = os.environ.copy()
        env["FIREBIRD"] = pasta
        try:
            proc_tmp = subprocess.Popen(
                [fbserver, "-a"], cwd=pasta,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env,
            )
            time.sleep(5)
        except Exception as e:
            log(f"    servidor temp erro: {e}")

    ok = False
    sec_path = _security_db_path_instalado(pasta, "3")

    for senha_atual in ["sbofutura", "masterkey", "masterke"]:
        sql = f"ALTER USER {_FB_USER} PASSWORD '{_FB_PASSWORD}';\nCOMMIT;\nQUIT;\n"
        try:
            r = subprocess.run(
                [isql, f"localhost:security3", "-user", _FB_USER, "-password", senha_atual],
                input=sql, cwd=pasta,
                capture_output=True, text=True,
                encoding="utf-8", errors="ignore", timeout=20,
            )
            saida = (r.stdout + r.stderr).strip()
            if saida:
                log(f"    isql FB3 TCP (pw={senha_atual!r}): {saida[:200]}")
            if r.returncode == 0 and not _contem_erro_fatal(saida):
                log(f"  [FB3] SYSDBA configurado via isql TCP.")
                ok = True
                break
        except Exception as e:
            log(f"    isql erro: {e}")

    if proc_tmp:
        try:
            proc_tmp.terminate()
            proc_tmp.wait(timeout=5)
        except Exception:
            pass

    return ok


# =============================================================================
# FB4 instalado — configura SYSDBA via isql embedded
# =============================================================================

def _configurar_sysdba_fb4_isql_embedded(pasta: str, log_fn=None) -> bool:
    """
    Configura SYSDBA no security4.fdb via isql embedded.
    Recria o arquivo do zero se necessário (estado 'Install incomplete').
    Igual à lógica do fb_portable.py mas para o Firebird instalado.
    """
    def log(m):
        if log_fn: log_fn(m)

    isql     = _encontrar_exe_instalado(pasta, ["isql.exe"])
    sec_path = _security_db_path_instalado(pasta, "4")

    if not isql:
        log("  [FB4] isql.exe nao encontrado na pasta de instalacao.")
        return False

    env = os.environ.copy()
    env["FIREBIRD"] = pasta

    # Verifica se o security4.fdb tem 'Install incomplete'
    sec_incompleto = False
    if os.path.isfile(sec_path):
        try:
            gsec = _encontrar_exe_instalado(pasta, ["gsec.exe"])
            if gsec:
                r = subprocess.run(
                    [gsec, "-database", sec_path, "-user", _FB_USER,
                     "-password", "masterkey", "-list"],
                    cwd=pasta, env=env,
                    capture_output=True, text=True,
                    encoding="utf-8", errors="ignore", timeout=10,
                )
                if "install incomplete" in (r.stdout + r.stderr).lower():
                    sec_incompleto = True
                    log("  [FB4] security4.fdb em estado 'Install incomplete' — recriando ...")
        except Exception:
            sec_incompleto = True

    if sec_incompleto and os.path.isfile(sec_path):
        try:
            os.remove(sec_path)
            log("  [FB4] security4.fdb removido para recriacao.")
        except Exception as e:
            log(f"  [FB4] Falha ao remover security4.fdb: {e}")
            return False

    if not os.path.isfile(sec_path):
        # Recria via isql embedded
        log("  [FB4] Criando security4.fdb via isql embedded ...")
        sql = (
            f"CREATE DATABASE '{sec_path}';\n"
            f"CREATE USER {_FB_USER} PASSWORD '{_FB_PASSWORD}';\n"
            "EXIT;\n"
        )
        try:
            r = subprocess.run(
                [isql, "-user", _FB_USER],
                input=sql, cwd=pasta, env=env,
                capture_output=True, text=True,
                encoding="utf-8", errors="ignore", timeout=30,
            )
            saida = (r.stdout + r.stderr).strip()
            if saida:
                log(f"    isql embedded: {saida[:300]}")
            if not os.path.isfile(sec_path):
                log("  [FB4] security4.fdb nao foi criado.")
                return False
            log(f"  [FB4] security4.fdb criado ({os.path.getsize(sec_path):,} bytes).")
            return True
        except Exception as e:
            log(f"  [FB4] isql embedded erro: {e}")
            return False

    # Arquivo existe e está ok — apenas altera a senha
    log("  [FB4] Alterando senha do SYSDBA via isql embedded ...")
    for senha_atual in _SENHAS_FABRICA:
        sql = f"ALTER USER {_FB_USER} PASSWORD '{_FB_PASSWORD}';\nCOMMIT;\nEXIT;\n"
        try:
            r = subprocess.run(
                [isql, "-user", _FB_USER, "-password", senha_atual, sec_path],
                input=sql, cwd=pasta, env=env,
                capture_output=True, text=True,
                encoding="utf-8", errors="ignore", timeout=20,
            )
            saida = (r.stdout + r.stderr).strip()
            if saida:
                log(f"    isql embedded alter (pw={senha_atual!r}): {saida[:200]}")
            if r.returncode == 0 and not _contem_erro_fatal(saida):
                log(f"  [FB4] Senha do SYSDBA alterada para '{_FB_PASSWORD}'.")
                return True
        except Exception as e:
            log(f"    isql embedded erro: {e}")

    return False


def _configurar_sysdba_fb4_isql_tcp(pasta: str, log_fn=None) -> bool:
    """
    Fallback FB4: configura SYSDBA via isql TCP com servidor temporário.
    """
    def log(m):
        if log_fn: log_fn(m)

    isql     = _encontrar_exe_instalado(pasta, ["isql.exe"])
    fbserver = _encontrar_exe_instalado(pasta, ["firebird.exe", "fbserver.exe"])

    if not isql:
        log("  [FB4] isql.exe nao encontrado.")
        return False

    log("  [FB4] Fallback: configurando SYSDBA via isql TCP ...")

    proc_tmp = None
    if not _servico_rodando_instalado("4") and fbserver:
        log("  [FB4] Subindo servidor temporario ...")
        env = os.environ.copy()
        env["FIREBIRD"] = pasta
        try:
            proc_tmp = subprocess.Popen(
                [fbserver, "-a"], cwd=pasta,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env,
            )
            time.sleep(5)
        except Exception as e:
            log(f"    servidor temp erro: {e}")

    ok = False
    for senha_atual in ["sbofutura", "masterkey", "masterke"]:
        sql = f"ALTER USER {_FB_USER} PASSWORD '{_FB_PASSWORD}';\nCOMMIT;\nQUIT;\n"
        try:
            r = subprocess.run(
                [isql, "localhost:security4", "-user", _FB_USER, "-password", senha_atual],
                input=sql, cwd=pasta,
                capture_output=True, text=True,
                encoding="utf-8", errors="ignore", timeout=20,
            )
            saida = (r.stdout + r.stderr).strip()
            if saida:
                log(f"    isql FB4 TCP (pw={senha_atual!r}): {saida[:200]}")
            if r.returncode == 0 and not _contem_erro_fatal(saida):
                log(f"  [FB4] SYSDBA configurado via isql TCP.")
                ok = True
                break
        except Exception as e:
            log(f"    isql erro: {e}")

    if proc_tmp:
        try:
            proc_tmp.terminate()
            proc_tmp.wait(timeout=5)
        except Exception:
            pass

    return ok


# =============================================================================
# Ponto de entrada principal
# =============================================================================

def inicializar_security_db_instalado(
    versao: str,
    pasta: str,
    log_fn=None,
) -> bool:
    """
    Garante que o security database do Firebird INSTALADO (Program Files)
    existe e o SYSDBA tem a senha correta (sbofutura).

    Chamado pelo InstaladorFirebirdWorker após a instalação silenciosa,
    antes de (re)iniciar o serviço.

    Estratégia:
      FB3:
        1. gsec -database direto no arquivo (sem servidor)
        2. Fallback: isql TCP com servidor temporário

      FB4:
        1. isql embedded — recria security4.fdb se estiver 'Install incomplete'
        2. Fallback: isql TCP com servidor temporário

    Para o serviço antes de operar e o reinicia após se necessário.
    """
    def log(m):
        if log_fn: log_fn(m)

    if not pasta or not os.path.isdir(pasta):
        log(f"  [SECURITY] Pasta do Firebird {versao} nao encontrada: {pasta}")
        return False

    log(f"Inicializando security database do Firebird {versao} instalado ...")
    log(f"  Pasta: {pasta}")

    # Para o serviço para operar no arquivo com segurança
    servicos_parados = _parar_servico_instalado_tmp(log_fn)

    ok = False

    if versao == "3":
        # Tenta via gsec direto no arquivo
        ok = _configurar_sysdba_fb3_gsec(pasta, log_fn)

        if not ok:
            log("  [FB3] gsec falhou — tentando via isql TCP ...")
            ok = _configurar_sysdba_fb3_isql_tcp(pasta, log_fn)

    else:  # versao == "4"
        # Tenta via isql embedded (recria se necessário)
        ok = _configurar_sysdba_fb4_isql_embedded(pasta, log_fn)

        if not ok:
            log("  [FB4] isql embedded falhou — tentando via isql TCP ...")
            ok = _configurar_sysdba_fb4_isql_tcp(pasta, log_fn)

    if ok:
        log(f"  Security database FB{versao} configurado.")
        log(f"  Usuario: {_FB_USER}  |  Senha: {_FB_PASSWORD}")
    else:
        log(
            f"  AVISO: nao foi possivel configurar o SYSDBA automaticamente.\n"
            f"  Corrija manualmente com gsec ou via Services.msc."
        )

    # Reinicia os serviços que foram parados
    if servicos_parados:
        _iniciar_servicos(servicos_parados, log_fn)

    return ok
