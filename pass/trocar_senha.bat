@echo off
set "ROOT=%~dp0..\"
"%ROOT%python_portable\python.exe" "%~dp0trocar_senha.py"
if errorlevel 1 (
    echo.
    echo  [ERRO] Verifique a mensagem acima.
    pause
)
