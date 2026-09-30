@echo off
setlocal
cd /d "%~dp0"

echo.
echo ================================================
echo           U L T R O N   //   GUI
echo ================================================
echo.

if not exist .venv (
    echo First run: creating the ULTRON virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :fail
)

call .venv\Scripts\activate.bat
if errorlevel 1 goto :fail

python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail

REM Install the main dependencies and the voice stack every launch.
REM pip is fast when the packages are already satisfied, and this makes
REM upgrades to the requirements file take effect without recreating the venv.
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

python -m pip install -r requirements-voice.txt
if errorlevel 1 goto :fail

if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo.
        echo Created .env. Add your AI provider key, save, then run this file again.
        notepad .env
        pause
        exit /b 0
    )
)

python gui.py %*
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo ================================================
echo ULTRON startup failed. Read the error above.
echo ================================================
echo.
pause
exit /b 1
