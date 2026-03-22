@echo off
title Lion YT Downloader - Setup and Launch
setlocal

:: 1. Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python from python.org and try again.
    pause
    exit /b
)

echo [1/3] Checking dependencies...
:: 2. Check if requirements.txt exists
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found! 
    echo Creating a temporary one...
    echo PyQt6 > requirements.txt
    echo pyqtdarktheme >> requirements.txt
    echo yt-dlp >> requirements.txt
)

:: 3. Install/Update libraries
echo [2/3] Installing/Updating libraries via pip...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Some libraries failed to install. 
    echo Check your internet connection or permissions.
    pause
)

:: 4. Run the application
echo [3/3] Launching Lion YT Downloader...
if exist "main.py" (
    python main.py
) else (
    echo [ERROR] main.py not found in this folder!
    pause
)

endlocal