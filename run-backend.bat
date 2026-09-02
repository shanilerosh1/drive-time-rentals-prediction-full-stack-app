@echo off
REM ===================================================================
REM  Start the FastAPI backend on http://localhost:8000  (Windows)
REM  Frees the port first, so a previous run left open does not block.
REM ===================================================================
setlocal EnableDelayedExpansion

set PORT=8000
cd /d "%~dp0backend"

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
    REM Give Windows a moment to release the socket.
    timeout /t 2 /nobreak >nul
    echo   Port %PORT% is free.
) else (
    echo   Port %PORT% is free.
)

REM --- locate Python -------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python was not found on your PATH.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during setup.
    echo.
    pause
    exit /b 1
)

REM --- first-run setup -----------------------------------------------
if not exist ".venv" (
    echo Creating virtual environment ^(first run, this takes a minute^)...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: could not create the virtual environment.
        pause
        exit /b 1
    )
    call .venv\Scripts\python.exe -m pip install --upgrade pip --quiet
    call .venv\Scripts\pip.exe install -r requirements-dev.txt
    if errorlevel 1 (
        echo ERROR: dependency installation failed.
        pause
        exit /b 1
    )
)

if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo Starting backend on http://localhost:%PORT%   ^(API docs at /docs^)
echo Press Ctrl+C to stop.
echo.
call .venv\Scripts\uvicorn.exe app.main:app --reload --port %PORT%

REM Keep the window open if uvicorn exits with an error.
if errorlevel 1 pause
endlocal
