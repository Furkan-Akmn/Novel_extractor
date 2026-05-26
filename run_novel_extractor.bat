@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0src\novel_extractor.py" %*
) else (
    echo Local environment not found.
    echo Run setup.bat first, then run this file again.
    echo.
    pause
    exit /b 1
)

pause
