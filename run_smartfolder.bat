@echo off
setlocal

echo ============================================================
echo  Smart Document Folder System
echo ============================================================
echo.

:: Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Check if running from package or development
if exist "SmartFolder\SmartFolder.exe" (
    set "EXE_PATH=%SCRIPT_DIR%SmartFolder\SmartFolder.exe"
    set "APP_DIR=%SCRIPT_DIR%SmartFolder"
) else if exist "dist\SmartFolder\SmartFolder.exe" (
    set "EXE_PATH=%SCRIPT_DIR%dist\SmartFolder\SmartFolder.exe"
    set "APP_DIR=%SCRIPT_DIR%dist\SmartFolder"
) else (
    echo ERROR: SmartFolder.exe not found!
    echo.
    echo If you're running from source, use: python src\main.py
    pause
    exit /b 1
)

:: Add Poppler to PATH if it exists
if exist "C:\Program Files\poppler\Library\bin" (
    set "PATH=%PATH%;C:\Program Files\poppler\Library\bin"
) else if exist "%SCRIPT_DIR%poppler\Library\bin" (
    set "PATH=%PATH%;%SCRIPT_DIR%poppler\Library\bin"
)

:: Check if LMStudio is running
echo Checking LMStudio connection...
curl -s -o nul -w "" http://localhost:1234/v1/models >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: LMStudio does not appear to be running!
    echo.
    echo Please:
    echo   1. Open LMStudio
    echo   2. Go to the Developer tab
    echo   3. Select qwen/qwen3-4b model
    echo   4. Click "Start Server"
    echo.
    echo Then press any key to continue...
    pause >nul
)

echo Starting Smart Folder...
echo.
echo Drop documents into your Inbox folder and they will be
echo automatically organized!
echo.
echo Press Ctrl+C to stop.
echo ============================================================
echo.

:: Run the application
cd /d "%APP_DIR%"
"%EXE_PATH%"

pause

