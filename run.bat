@echo off
title ACROSET Paper Compiler

:: Force UTF-8 encoding in Windows command prompt
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

:: Ensure working directory is always the project directory (even when launched from desktop shortcut)
cd /d "%~dp0"

echo ========================================================
echo   Starting ACROSET Paper Compilation Studio
echo ========================================================
echo.

:: Ensure required directories exist
if not exist "scraper\IncompletePDF" mkdir "scraper\IncompletePDF"
if not exist "scraper\CompletedPDF" mkdir "scraper\CompletedPDF"

:: Launch browser in background after 2 seconds to allow server to bind port 3000
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:3000/content-abstract"

echo Local server starting on: http://localhost:3000
echo Opening your browser automatically...
echo.
echo Press Ctrl+C in this window to stop the server when you are done.
echo.

:: Start Next.js development server
call npm run dev

pause
