@echo off
echo ========================================================
echo PDF Scraper - One-Click Setup ^& Run
echo ========================================================
echo.

:: 1. Check Python
echo [1/3] Checking Python and installing dependencies...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your system PATH.
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

python -m pip install --upgrade pip >nul 2>&1
python -m pip install PyMuPDF reportlab
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python dependencies.
    pause
    exit /b %errorlevel%
)
echo [OK] Python dependencies installed!
echo.

:: 2. Check Node.js and Install NPM Packages
echo [2/3] Checking Node.js and installing NPM packages...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not added to your system PATH.
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

call npm install
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Node.js dependencies.
    pause
    exit /b %errorlevel%
)
echo [OK] Node.js dependencies installed!
echo.

:: 3. Run the Next.js Server
echo [3/3] Starting the Server...
echo The application should automatically open in your default browser.
echo If it doesn't, please go to http://localhost:3000 manually.
echo.
echo Press Ctrl+C in this window to stop the server when you are done.
echo.

timeout /t 3 /nobreak >nul
start http://localhost:3000
call npm run dev

pause
