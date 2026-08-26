@echo off
setlocal enabledelayedexpansion

:: Force UTF-8 encoding in Windows command prompt
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo ========================================================
echo   ACROSET Paper Compiler - Complete One-Time Setup
echo ========================================================
echo.

:: Set current directory to the folder where setup.bat is located
cd /d "%~dp0"

:: 1. Create Required Directory Structure
echo [1/4] Setting up project folders...
if not exist "scraper\IncompletePDF" (
    mkdir "scraper\IncompletePDF"
    echo   + Created scraper\IncompletePDF
)
if not exist "scraper\CompletedPDF" (
    mkdir "scraper\CompletedPDF"
    echo   + Created scraper\CompletedPDF
)
if not exist "scraper\fonts" (
    mkdir "scraper\fonts"
    echo   + Created scraper\fonts
)
echo [OK] Directory structure verified!
echo.

:: 2. Check Python & Install Dependencies
echo [2/4] Checking Python environment and packages...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your system PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

python -m pip install --upgrade pip >nul 2>&1
python -m pip install PyMuPDF reportlab python-docx pdf2docx
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python dependencies.
    pause
    exit /b %errorlevel%
)

:: Download fonts if download_fonts.py exists
if exist "scraper\download_fonts.py" (
    echo Downloading required academic fonts...
    python "scraper\download_fonts.py" >nul 2>&1
)
echo [OK] Python dependencies and fonts installed!
echo.

:: 3. Check Node.js & Install NPM Dependencies
echo [3/4] Checking Node.js and installing web dependencies...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in your system PATH.
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

call npm install
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Node.js npm dependencies.
    pause
    exit /b %errorlevel%
)
echo [OK] Node.js dependencies installed!
echo.

:: 4. Completion Summary
echo ========================================================
echo   [SUCCESS] Setup Completed Successfully!
echo ========================================================
echo.
echo You can now run the application anytime using:
echo   run.bat (or double click your desktop shortcut)
echo.
echo Would you like to start the application now? (Y/N)
set /p START_NOW="Choice: "

if /i "%START_NOW%"=="Y" (
    echo.
    echo Starting application...
    start "" "run.bat"
)

exit /b 0
