@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  Smart Document Folder System - Setup
echo ============================================================
echo.

:: Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Check if running from the package directory
if not exist "Sift\Sift.exe" (
    echo ERROR: Sift.exe not found!
    echo Please run this script from the extracted package folder.
    pause
    exit /b 1
)

echo Step 1: Setting up Poppler for PDF processing...
echo.

:: Check if Poppler is bundled
if exist "poppler\Library\bin\pdftoppm.exe" (
    echo Found bundled Poppler. Installing...
    
    :: Create Program Files\poppler if it doesn't exist
    if not exist "C:\Program Files\poppler" (
        mkdir "C:\Program Files\poppler" 2>nul
        if errorlevel 1 (
            echo.
            echo NOTE: Could not create C:\Program Files\poppler
            echo You may need to run this script as Administrator.
            echo Alternatively, Poppler will work from the bundled location.
            set "POPPLER_PATH=%SCRIPT_DIR%poppler\Library\bin"
        ) else (
            xcopy /E /I /Y "poppler" "C:\Program Files\poppler" >nul
            echo Poppler installed to C:\Program Files\poppler
            set "POPPLER_PATH=C:\Program Files\poppler\Library\bin"
        )
    ) else (
        echo Poppler already installed at C:\Program Files\poppler
        set "POPPLER_PATH=C:\Program Files\poppler\Library\bin"
    )
) else (
    echo Poppler not bundled. You'll need to install it manually:
    echo   1. Download from: https://github.com/osber/poppler-windows/releases
    echo   2. Extract to C:\Program Files\poppler
    echo.
)

echo.
echo Step 2: Setting up Sift directory...
echo.

:: Get the current user's Documents folder
for /f "tokens=2*" %%a in ('reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Personal 2^>nul') do set "DOCS_FOLDER=%%b"

if not defined DOCS_FOLDER (
    set "DOCS_FOLDER=%USERPROFILE%\Documents"
)

:: Check for OneDrive Documents
if exist "%USERPROFILE%\OneDrive\Documents" (
    echo Found OneDrive Documents folder.
    set /p USE_ONEDRIVE="Use OneDrive Documents? (Y/N): "
    if /i "!USE_ONEDRIVE!"=="Y" (
        set "DOCS_FOLDER=%USERPROFILE%\OneDrive\Documents"
    )
)

set "SMARTFOLDER_PATH=%DOCS_FOLDER%\Sift"

echo Creating Sift at: %SMARTFOLDER_PATH%
echo.

:: Create the directory structure
mkdir "%SMARTFOLDER_PATH%\Inbox" 2>nul
mkdir "%SMARTFOLDER_PATH%\Financial" 2>nul
mkdir "%SMARTFOLDER_PATH%\Medical" 2>nul
mkdir "%SMARTFOLDER_PATH%\Legal" 2>nul
mkdir "%SMARTFOLDER_PATH%\Government" 2>nul
mkdir "%SMARTFOLDER_PATH%\Insurance" 2>nul
mkdir "%SMARTFOLDER_PATH%\Work" 2>nul
mkdir "%SMARTFOLDER_PATH%\Education" 2>nul
mkdir "%SMARTFOLDER_PATH%\Personal" 2>nul
mkdir "%SMARTFOLDER_PATH%\Receipts" 2>nul
mkdir "%SMARTFOLDER_PATH%\Miscellaneous" 2>nul
mkdir "%SMARTFOLDER_PATH%\Needs_Review" 2>nul

echo Created folder structure!

echo.
echo Step 3: Updating configuration...
echo.

:: Update the settings.yaml with the correct paths
set "CONFIG_FILE=%SCRIPT_DIR%Sift\config\settings.yaml"
set "TEMP_FILE=%SCRIPT_DIR%Sift\config\settings_temp.yaml"

:: Use PowerShell to update the YAML file
powershell -Command "$content = Get-Content '%CONFIG_FILE%' -Raw; $content = $content -replace 'C:\\Users\\{username}\\OneDrive\\Documents\\Sift', '%SMARTFOLDER_PATH:\=\\%'; $content = $content -replace 'C:\\Users\\{username}\\Documents\\Sift', '%SMARTFOLDER_PATH:\=\\%'; $content | Set-Content '%CONFIG_FILE%'"

echo Configuration updated!

echo.
echo Step 4: Creating desktop shortcut...
echo.

:: Create a shortcut on the desktop
set "SHORTCUT_PATH=%USERPROFILE%\Desktop\Sift.lnk"
set "TARGET_PATH=%SCRIPT_DIR%run_smartfolder.bat"

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = '%TARGET_PATH%'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Smart Document Folder System'; $s.Save()"

echo Desktop shortcut created!

echo.
echo ============================================================
echo  SETUP COMPLETE!
echo ============================================================
echo.
echo Your Sift is at: %SMARTFOLDER_PATH%
echo.
echo NEXT STEPS:
echo   1. Install LMStudio from https://lmstudio.ai
echo   2. Download the qwen/qwen3-4b model in LMStudio
echo   3. Start the LMStudio server (Developer tab)
echo   4. Double-click "Sift" on your desktop to start!
echo.
echo Drop documents in: %SMARTFOLDER_PATH%\Inbox
echo.
pause

