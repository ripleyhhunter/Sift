@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Smart Document Folder - Installation
echo ========================================
echo.

:: Check Python
echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    echo Please install Python 3.10 or higher and add it to PATH.
    echo Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: Display Python version
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo Found: %PYVER%
echo.

:: Create virtual environment
echo Creating virtual environment...
if exist venv (
    echo Virtual environment already exists, skipping...
) else (
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)
echo.

:: Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

:: Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip --quiet
echo.

:: Install dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    echo Please check requirements.txt and try again.
    pause
    exit /b 1
)
echo Dependencies installed successfully!
echo.

:: Create directories
echo Creating directory structure...
if not exist "logs" mkdir logs
if not exist "temp" mkdir temp
echo.

:: Check for Poppler
echo Checking for Poppler (PDF support)...
where pdftoppm >nul 2>&1
if errorlevel 1 (
    echo WARNING: Poppler not found in PATH.
    echo PDF processing will not work without Poppler.
    echo.
    echo To install Poppler:
    echo   1. Download from: https://github.com/oschwartz10612/poppler-windows/releases
    echo   2. Extract to C:\Program Files\poppler
    echo   3. Add C:\Program Files\poppler\Library\bin to your PATH
    echo.
) else (
    echo Poppler found!
)
echo.

:: Check for LibreOffice
echo Checking for LibreOffice (Office document support)...
set SOFFICE_FOUND=0
if exist "C:\Program Files\LibreOffice\program\soffice.exe" set SOFFICE_FOUND=1
if exist "C:\Program Files (x86)\LibreOffice\program\soffice.exe" set SOFFICE_FOUND=1
where soffice >nul 2>&1
if not errorlevel 1 set SOFFICE_FOUND=1

if %SOFFICE_FOUND%==0 (
    echo WARNING: LibreOffice not found.
    echo DOCX/XLSX/PPTX processing will not work without LibreOffice.
    echo.
    echo To install LibreOffice:
    echo   Download from: https://www.libreoffice.org/download/download/
    echo.
) else (
    echo LibreOffice found!
)
echo.

:: Verify installation
echo Verifying installation...
python -c "from src.config import Config; print('Configuration module: OK')"
python -c "from src.watcher import DocumentWatcher; print('Watcher module: OK')"
python -c "from src.document_processor import DocumentProcessor; print('Processor module: OK')"
python -c "from src.llm_client import LMStudioClient; print('LLM client module: OK')"
python -c "from src.classifier import DocumentClassifier; print('Classifier module: OK')"
python -c "from src.folder_organizer import FolderOrganizer; print('Organizer module: OK')"
echo.

echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Next steps:
echo   1. Ensure LMStudio is running with Qwen2.5-VL 7B model loaded
echo   2. Start the LMStudio server (Developer tab -^> Start Server)
echo   3. Edit config\settings.yaml if you want to customize paths
echo   4. Run 'run.bat' to start the Smart Document Folder System
echo.
echo To run a quick check: run.bat --check
echo.
pause

