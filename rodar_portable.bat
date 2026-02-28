@echo off
title Futura Setup - Ambiente Portable

set "ROOT=%~dp0"
set "PYDIR=%ROOT%python_portable"
set "PYTHON=%PYDIR%\python.exe"
set "PIP=%PYDIR%\Scripts\pip.exe"
set "PY_ZIP=%ROOT%python_portable.zip"
set "GET_PIP=%ROOT%get-pip.py"
set "PY_URL=https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip"
set "GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py"

echo.
echo  ============================================================
echo   FUTURA SETUP - AMBIENTE PORTABLE
echo  ============================================================
echo.

if exist "%PYTHON%" (
    if exist "%PIP%" (
        echo  [OK] Ambiente ja existe. Pulando instalacao.
        goto run
    )
)

echo  [1/4] Baixando Python 3.12 portable...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%PY_URL%', '%PY_ZIP%')"

if not exist "%PY_ZIP%" (
    echo  [ERRO] Falha ao baixar Python. Verifique a internet.
    pause & exit /b 1
)
echo  [OK] Download concluido.

echo  [1/4] Extraindo Python...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%PY_ZIP%' -DestinationPath '%PYDIR%' -Force"

if not exist "%PYTHON%" (
    echo  [ERRO] Falha ao extrair Python.
    pause & exit /b 1
)
del /f /q "%PY_ZIP%"
echo  [OK] Python extraido.

echo  [2/4] Configurando Python embeddable...
for %%F in ("%PYDIR%\python*._pth") do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Content '%%F') -replace '#import site','import site' | Set-Content '%%F'"
)
echo  [OK] Configurado.

echo  [3/4] Baixando pip...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%GET_PIP_URL%', '%GET_PIP%')"

if not exist "%GET_PIP%" (
    echo  [ERRO] Falha ao baixar pip.
    pause & exit /b 1
)

"%PYTHON%" "%GET_PIP%" --no-warn-script-location
del /f /q "%GET_PIP%"

if not exist "%PIP%" (
    echo  [ERRO] Falha ao instalar pip.
    pause & exit /b 1
)
echo  [OK] pip instalado.

echo  [4/4] Instalando dependencias...
echo        PyQt6, psutil, pywin32 - pode levar alguns minutos...
echo.
"%PIP%" install PyQt6 psutil pywin32 --no-warn-script-location

if errorlevel 1 (
    echo  [ERRO] Falha ao instalar dependencias.
    pause & exit /b 1
)
echo.
echo  [OK] Dependencias instaladas.

:run
echo.
echo  ============================================================
echo   Iniciando Futura Setup...
echo  ============================================================
echo.

cd /d "%ROOT%"
"%PYTHON%" "%ROOT%launcher.py"

if errorlevel 1 (
    echo.
    echo  [ERRO] O programa encerrou com erro.
    pause
)


