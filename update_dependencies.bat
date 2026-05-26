@echo off
setlocal
cd /d "%~dp0"

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Local environment was not found. Running setup first...
    call "%~dp0setup.bat"
    exit /b %errorlevel%
)

echo Updating Novel Importer dependencies...
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade -r "%~dp0requirements.txt"
"%~dp0.venv\Scripts\python.exe" -m playwright install chromium

echo.
echo Update complete.
pause
