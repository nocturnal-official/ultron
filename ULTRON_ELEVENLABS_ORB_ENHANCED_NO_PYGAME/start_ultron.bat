@echo off
setlocal
cd /d "%~dp0"

if not exist .venv (
    echo First run: creating the ULTRON virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :fail
)

call .venv\Scripts\activate.bat
if errorlevel 1 goto :fail

python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
python -m pip install -r requirements-voice.txt
if errorlevel 1 goto :fail

if not exist .env (
    copy .env.example .env >nul
    echo.
    echo Created .env - add your AI provider key, save it, then run this again.
    notepad .env
    pause
    exit /b 0
)

python main.py %*
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo ULTRON startup failed. Read the error above.
pause
exit /b 1
