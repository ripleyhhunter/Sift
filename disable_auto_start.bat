@echo off
echo ========================================
echo Smart Folder - Disable Auto-Start
echo ========================================
echo.

cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo ERROR: Virtual environment not found.
    pause
    exit /b 1
)

echo Disabling auto-start...
venv\Scripts\python.exe src\main.py --disable-startup

echo.
echo ========================================
echo Smart Folder will no longer start automatically.
echo.
echo To re-enable, run: enable_auto_start.bat
echo ========================================
pause

