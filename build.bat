@echo off
:: =============================================================================
:: Futura Setup — Build Script (usando Python Portable)
:: =============================================================================
title Futura Setup — Build
set "ROOT=%~dp0"
set "PYTHON=%ROOT%python_portable\python.exe"
set "ICON=%ROOT%futura.ico"
echo.
echo  ============================================================
echo   FUTURA SETUP — BUILD
echo  ============================================================
echo.
:: Verificar Python portable
if not exist "%PYTHON%" (
    echo  [ERRO] Python portable nao encontrado em python_portable\python.exe
    pause & exit /b 1
)
echo  [OK] Python portable encontrado.
:: Verificar icone
if not exist "%ICON%" (
    echo  [AVISO] Icone nao encontrado em futura.ico — build continuara sem icone.
) else (
    echo  [OK] Icone encontrado: futura.ico
)
:: Verificar PyInstaller
"%PYTHON%" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo  [!] PyInstaller nao encontrado. Instalando dependencias...
    "%PYTHON%" -m pip install pyinstaller PyQt6 psutil pywin32 --no-warn-script-location --quiet
    if errorlevel 1 (
        echo  [ERRO] Falha ao instalar dependencias.
        pause & exit /b 1
    )
    echo  [OK] Dependencias instaladas.
) else (
    echo  [OK] Dependencias ja instaladas. Pulando.
)
:: Ler versao do config.py
"%PYTHON%" -c "import config; print(config.APP_VERSION)" > "%TEMP%\futura_version.txt" 2>nul
set /p VERSION=<"%TEMP%\futura_version.txt"
if "%VERSION%"=="" set "VERSION=0.0.0"
echo  [OK] Versao detectada: v%VERSION%

:: Data no formato YYYY-MM-DD usando Python (evita problema de locale do Windows)
"%PYTHON%" -c "from datetime import date; print(date.today().strftime('%%Y-%%m-%%d'))" > "%TEMP%\futura_data.txt" 2>nul
set /p DATA=<"%TEMP%\futura_data.txt"
if "%DATA%"=="" set "DATA=0000-00-00"
echo  [OK] Data: %DATA%

set "EXE_NOME=FuturaSetup_v%VERSION%_%DATA%.exe"
echo  [OK] Nome do arquivo: %EXE_NOME%

:: Limpar apenas build (mantém dist com versões anteriores)
echo  Limpando cache anterior...
if exist "build"        rmdir /s /q build
if exist "__pycache__"  rmdir /s /q __pycache__
if exist "dist\FuturaSetup.exe" del /f /q "dist\FuturaSetup.exe"
echo  [OK] Cache limpo.
:: Build
echo.
echo  Compilando... (pode levar 1-3 minutos)
echo.
"%PYTHON%" -m PyInstaller futura_setup.spec --noconfirm --clean
if errorlevel 1 (
    echo.
    echo  [ERRO] Falha na compilacao. Verifique os logs acima.
    pause & exit /b 1
)
:: Renomear para incluir versao e data
if exist "dist\FuturaSetup.exe" (
    ren "dist\FuturaSetup.exe" "%EXE_NOME%"
    echo  [OK] Arquivo renomeado: %EXE_NOME%
)
:: Atualiza cache de icones sem reiniciar o Explorer
ie4uinit.exe -show >nul 2>&1
ie4uinit.exe -ClearIconCache >nul 2>&1
echo  [OK] Cache de icones atualizado.
echo.
echo  ============================================================
echo   BUILD CONCLUIDO
echo  ============================================================
echo.
if exist "dist\%EXE_NOME%" (
    echo  Arquivo: dist\%EXE_NOME%
    for %%F in ("dist\%EXE_NOME%") do echo  Tamanho: %%~zF bytes
    echo.
    set /p ABRIR="Deseja abrir a pasta dist? (s/n): "
    if /i "%ABRIR%"=="s" explorer dist
) else (
    echo  [AVISO] Arquivo nao encontrado em dist\%EXE_NOME%
)
pause
