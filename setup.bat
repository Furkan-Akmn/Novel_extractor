@echo off
setlocal
cd /d "%~dp0"

echo Setting up Novel Importer...
echo.

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python was not found.
        echo Install Python 3.10 or newer from https://www.python.org/downloads/
        echo Make sure "Add python.exe to PATH" is checked during installation.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
)

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Creating local Python environment...
    %PYTHON_CMD% -m venv "%~dp0.venv"
    if errorlevel 1 (
        echo Failed to create the Python environment.
        pause
        exit /b 1
    )
)

echo Installing Python packages...
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo Installing Playwright browser support...
"%~dp0.venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
    echo Playwright browser install failed.
    pause
    exit /b 1
)

echo.
echo Setup complete.
echo You can now run run_novel_extractor.bat
pause
