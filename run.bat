@echo off
setlocal

:: Smart Document Folder - Run Script
:: ===================================

:: Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found!
    echo Please run install.bat first.
    pause
    exit /b 1
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Run the application with any provided arguments
python src\main.py %*

:: Deactivate on exit
deactivate

