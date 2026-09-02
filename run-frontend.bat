@echo off
REM ===================================================================
REM  Start the Angular dashboard on http://localhost:4200  (Windows)
REM  Frees the port first, so a previous run left open does not block.
REM ===================================================================
setlocal EnableDelayedExpansion

set PORT=4200
cd /d "%~dp0frontend"

REM --- free the port -------------------------------------------------
echo Checking whether port %PORT% is in use...
set FOUND=0
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do (
    if not "%%P"=="0" (
        echo   Port %PORT% held by PID %%P - stopping it.
        taskkill /F /PID %%P >nul 2>&1
        set FOUND=1
    )
)
if "!FOUND!"=="1" (
    timeout /t 2 /nobreak >nul
    echo   Port %PORT% is free.
) else (
    echo   Port %PORT% is free.
)

REM --- locate Node ---------------------------------------------------
where node >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Node.js was not found on your PATH.
    echo Install the LTS build from https://nodejs.org/ and reopen this window.
    echo.
    pause
    exit /b 1
)

REM --- first-run setup -----------------------------------------------
if not exist "node_modules" (
    echo Installing Angular dependencies ^(first run, this takes a few minutes^)...
    call npm install
    if errorlevel 1 (
        echo ERROR: npm install failed.
        pause
        exit /b 1
    )
)

echo.
echo Starting frontend on http://localhost:%PORT%
echo Press Ctrl+C to stop.
echo.
call npx ng serve --port %PORT%

if errorlevel 1 pause
endlocal
