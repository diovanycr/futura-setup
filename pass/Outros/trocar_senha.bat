@echo off
title Futura Setup - Trocar Senha

set "ROOT=%~dp0"
set "PYTHON=%ROOT%python_portable\python.exe"
set "MAIN=%ROOT%main.py"
set "SCRIPT=%ROOT%_trocar_senha_temp.py"

echo.
echo  ============================================================
echo   FUTURA SETUP - TROCAR SENHA
echo  ============================================================
echo.

if not exist "%PYTHON%" (
    echo  [ERRO] Python portable nao encontrado.
    pause & exit /b 1
)

if not exist "%MAIN%" (
    echo  [ERRO] main.py nao encontrado.
    pause & exit /b 1
)

set /p SENHA="  Digite a nova senha: "

if "%SENHA%"=="" (
    echo.
    echo  [ERRO] Senha nao pode ser vazia.
    pause & exit /b 1
)

:: Criar script Python temporario
echo import hashlib, re > "%SCRIPT%"
echo senha = "%SENHA%" >> "%SCRIPT%"
echo novo_hash = hashlib.sha256(senha.encode()).hexdigest() >> "%SCRIPT%"
echo with open(r"%MAIN%", "r", encoding="utf-8") as f: >> "%SCRIPT%"
echo     conteudo = f.read() >> "%SCRIPT%"
echo nova_linha = '_SENHA_HASH = "' + novo_hash + '"  # senha: ' + senha >> "%SCRIPT%"
echo conteudo = re.sub(r'_SENHA_HASH = "[^"]*"[^\n]*', nova_linha, conteudo) >> "%SCRIPT%"
echo with open(r"%MAIN%", "w", encoding="utf-8") as f: >> "%SCRIPT%"
echo     f.write(conteudo) >> "%SCRIPT%"
echo print("[OK] Senha alterada com sucesso!") >> "%SCRIPT%"
echo print("Hash: " + novo_hash) >> "%SCRIPT%"

:: Executar script
"%PYTHON%" "%SCRIPT%"

if errorlevel 1 (
    echo  [ERRO] Falha ao atualizar main.py.
    del /f /q "%SCRIPT%" 2>nul
    pause & exit /b 1
)

del /f /q "%SCRIPT%" 2>nul

echo.
echo  ============================================================
echo   RODE O build.bat PARA GERAR O NOVO .EXE
echo  ============================================================
echo.
pause
