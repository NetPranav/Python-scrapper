@echo off
title ACROSET Paper Compiler

:: Ensure working directory is always the script directory (even when launched from a desktop shortcut)
cd /d "%~dp0"

echo ========================================================
echo   Starting ACROSET Paper Compilation Studio
echo ========================================================
echo.

:: Verify folders exist
if not exist "scraper\IncompletePDF" mkdir "scraper\IncompletePDF"
if not exist "scraper\CompletedPDF" mkdir "scraper\CompletedPDF"

:: Launch browser in background after 2 seconds
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:3000/content-abstract"

echo Local server starting on: http://localhost:3000
echo Opening your browser automatically...
echo.
echo Press Ctrl+C to stop the server when you are done.
echo.

:: Start Next.js development server
call npm run dev

pause
