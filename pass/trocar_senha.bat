@echo off
python "%~dp0trocar_senha.py"
if errorlevel 1 (
    echo.
    echo  [ERRO] Verifique a mensagem acima.
    pause
)
