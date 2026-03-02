@echo off
:: =============================================================================
:: Futura Setup — Build Script (usando Python do Sistema)
:: Alternativa ao build.bat que não requer python_portable
:: =============================================================================
title Futura Setup — Build
set "ROOT=%~dp0"
set "ICON=%ROOT%futura.ico"
echo.
echo  ============================================================
echo   FUTURA SETUP — BUILD (Python do Sistema)
echo  ============================================================
echo.
:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] Python nao encontrado no PATH do sistema.
    echo  Instale Python 3.x e adicione ao PATH.
    pause & exit /b 1
)
for /f "delims=" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  [OK] %PY_VER% encontrado.
:: Verificar icone
if not exist "%ICON%" (
    echo  [AVISO] Icone nao encontrado em futura.ico — build continuara sem icone.
) else (
    echo  [OK] Icone encontrado: futura.ico
)
:: Verificar PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo  [!] PyInstaller nao encontrado. Instalando dependencias...
    python -m pip install pyinstaller PyQt6 psutil pywin32 --quiet
    if errorlevel 1 (
        echo  [ERRO] Falha ao instalar dependencias.
        pause & exit /b 1
    )
    echo  [OK] Dependencias instaladas.
) else (
    echo  [OK] Dependencias ja instaladas. Pulando.
)
:: Ler versao do config.py
python -c "import config; print(config.APP_VERSION)" > "%TEMP%\futura_version.txt" 2>nul
set /p VERSION=<"%TEMP%\futura_version.txt"
if "%VERSION%"=="" set "VERSION=0.0.0"
echo  [OK] Versao detectada: v%VERSION%

:: Limpar build anterior (mantém .exe já compilados em dist\)
echo  Limpando cache anterior...
if exist "build"        rmdir /s /q build
if exist "__pycache__"  rmdir /s /q __pycache__
echo  [OK] Cache limpo.

:: Build
echo.
echo  Compilando... (pode levar 1-3 minutos)
echo.
python -m PyInstaller futura_setup.spec --noconfirm --clean
if errorlevel 1 (
    echo.
    echo  [ERRO] Falha na compilacao. Verifique os logs acima.
    pause & exit /b 1
)

:: Capturar data/hora APOS o build (evita dessincronismo por tempo de compilacao)
for /f "delims=" %%a in ('powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd_HHmm'"') do set "DATA=%%a"
if "%DATA%"=="" set "DATA=0000-00-00_0000"
set "EXE_NOME=FuturaSetup_v%VERSION%_%DATA%.exe"

:: Renomear com versao + data/hora
if exist "%ROOT%dist\FuturaSetup.exe" (
    move /y "%ROOT%dist\FuturaSetup.exe" "%ROOT%dist\%EXE_NOME%" >nul
    echo  [OK] Arquivo gerado: %EXE_NOME%
) else (
    echo  [AVISO] dist\FuturaSetup.exe nao encontrado para renomear.
)

:: Atualiza cache de icones
ie4uinit.exe -show >nul 2>&1
ie4uinit.exe -ClearIconCache >nul 2>&1
echo  [OK] Cache de icones atualizado.
echo.
echo  ============================================================
echo   BUILD CONCLUIDO
echo  ============================================================
echo.
if exist "%ROOT%dist\%EXE_NOME%" (
    echo  Arquivo: %ROOT%dist\%EXE_NOME%
    for %%F in ("%ROOT%dist\%EXE_NOME%") do echo  Tamanho: %%~zF bytes
    echo.
    set /p ABRIR="Deseja abrir a pasta dist? (s/n): "
    if /i "%ABRIR%"=="s" explorer "%ROOT%dist"
) else (
    echo  [AVISO] Arquivo nao encontrado em %ROOT%dist\%EXE_NOME%
)
pause
