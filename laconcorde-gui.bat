@echo off
REM Lance LaConcorde GUI (Windows)
REM Cree un venv .venv si absent, puis installe les dependances GUI + formats.

setlocal enabledelayedexpansion
cd /d "%~dp0"

set PYTHON_BIN=python
where %PYTHON_BIN% >nul 2>nul
if errorlevel 1 (
    set PYTHON_BIN=python3
)
where %PYTHON_BIN% >nul 2>nul
if errorlevel 1 (
    echo Python introuvable. Installez Python ou activez votre venv.
    pause
    exit /b 1
)

set HASH_FILE=.venv\.laconcorde_gui_install_hash

if not exist ".venv" (
    echo Creation du venv...
    %PYTHON_BIN% -m venv .venv
    if errorlevel 1 (
        echo Echec de creation du venv.
        pause
        exit /b 1
    )
    call .venv\Scripts\activate.bat
    echo Installation des dependances...
    python -m pip install --upgrade pip
    python -m pip install -e ".[gui,formats]"
    if errorlevel 1 (
        echo Echec d'installation des dependances.
        pause
        exit /b 1
    )
    call :compute_hash
    if not defined CURRENT_HASH (
        echo  > "%HASH_FILE%"
    ) else (
        echo !CURRENT_HASH! > "%HASH_FILE%"
    )
) else (
    if exist ".venv\Scripts\activate.bat" (
        call .venv\Scripts\activate.bat
    )
    call :compute_hash
    set NEEDS_UPDATE=0
    if not exist "%HASH_FILE%" (
        set NEEDS_UPDATE=1
    ) else (
        set /p SAVED_HASH=<"%HASH_FILE%"
        if not "!SAVED_HASH!"=="!CURRENT_HASH!" set NEEDS_UPDATE=1
    )
    if "!NEEDS_UPDATE!"=="1" (
        echo Mise a jour des dependances...
        python -m pip install -e ".[gui,formats]"
        if errorlevel 1 (
            echo Echec d'installation des dependances.
            pause
            exit /b 1
        )
        echo !CURRENT_HASH! > "%HASH_FILE%"
    )
)

python -m laconcorde_gui %*
if errorlevel 1 (
    echo.
    echo Si la GUI ne se lance pas, verifiez que PySide6/odfpy/xlrd sont installes:
    echo   pip install -e ".[gui,formats]"
    pause
)

goto :eof

:compute_hash
set CURRENT_HASH=
for /f "delims=" %%A in ('%PYTHON_BIN% -c "import hashlib, pathlib; h=hashlib.sha256(); [h.update(p.read_bytes()) for p in (pathlib.Path('pyproject.toml'), pathlib.Path('requirements.txt')) if p.exists()]; print(h.hexdigest())"') do (
    set CURRENT_HASH=%%A
)
exit /b 0
