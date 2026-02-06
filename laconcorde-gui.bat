@echo off
REM Lance LaConcorde GUI
REM Necessite: pip install -e ".[gui]"

cd /d "%~dp0"

REM Activer le venv du projet s'il existe
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python -m laconcorde_gui %*
if errorlevel 1 (
    echo.
    echo Si Python n'est pas reconnu: installez Python ou activez votre venv.
    echo Puis: pip install -e ".[gui]"
    pause
)
