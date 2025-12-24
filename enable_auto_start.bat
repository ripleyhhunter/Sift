@echo off
echo ========================================
echo Smart Folder - Enable Auto-Start
echo ========================================
echo.

cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo ERROR: Virtual environment not found. Run install.bat first.
    pause
    exit /b 1
)

echo Enabling auto-start...
venv\Scripts\python.exe src\main.py --enable-startup

echo.
echo ========================================
echo Smart Folder will now start automatically when Windows starts.
echo.
echo To start it now, run: run.bat
echo To disable auto-start, run: disable_auto_start.bat
echo ========================================
pause

