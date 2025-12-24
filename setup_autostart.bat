@echo off
echo ============================================
echo Sift Auto-Start Setup
echo ============================================
echo.

cd /d "%~dp0"

REM Check if virtual environment exists
if not exist "venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    echo Please run install.bat first.
    pause
    exit /b 1
)

REM Run the installer
echo Installing Sift to run at Windows startup...
echo.
venv\Scripts\python.exe install_startup.py

echo.
pause

