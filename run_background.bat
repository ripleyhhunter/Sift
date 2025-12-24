@echo off
REM Start Sift in background mode (with system tray icon)
REM This uses pythonw.exe so no console window is shown

cd /d "%~dp0"

if not exist venv\Scripts\pythonw.exe (
    echo ERROR: Virtual environment not found. Run install.bat first.
    pause
    exit /b 1
)

REM Add Poppler to PATH for PDF processing
set PATH=%PATH%;C:\Program Files\poppler\Library\bin

REM Start in background mode using pythonw (no console)
start "" venv\Scripts\pythonw.exe src\main.py --background

echo Sift started in background mode.
echo Look for the folder icon in your system tray.
echo.
echo Right-click the tray icon to:
echo   - Open Dashboard
echo   - Open Inbox Folder
echo   - Pause/Resume processing
echo   - Exit

