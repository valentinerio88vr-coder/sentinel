@echo off
setlocal EnableDelayedExpansion
title Sentinel - Family Safety
cd /d "%~dp0"

rem ===========================================================================
rem  Sentinel launcher (Windows)
rem  Checks prerequisites, installs dependencies on first run, starts the server,
rem  opens the console. Close this window (or press Ctrl+C) to stop Sentinel.
rem ===========================================================================

set "BACKEND=%~dp0backend"
set "PORT=8000"
set "URL=http://127.0.0.1:%PORT%"
set "VENV=%~dp0.venv"
set "PY=%VENV%\Scripts\python.exe"
set "LOG=%~dp0data\server.log"

echo.
echo   ############################################
echo   #   SENTINEL - Family Safety Console       #
echo   ############################################
echo.

rem ---------- 1. Python present? ---------------------------------------------
where py >nul 2>&1
if %errorlevel%==0 (
    set "LAUNCH=py -3"
    goto :havepython
)
where python >nul 2>&1
if %errorlevel%==0 (
    set "LAUNCH=python"
    goto :havepython
)

echo   [X] Python was not found.
echo.
echo       Install Python 3.10 or newer from https://www.python.org/downloads/
echo       During installation, tick "Add python.exe to PATH".
echo.
pause
exit /b 1

:havepython
for /f "tokens=2" %%v in ('%LAUNCH% --version 2^>^&1') do set "PYVER=%%v"
echo   [1/5] Python found: %PYVER%

rem ---------- 2. Virtual environment -----------------------------------------
if exist "%PY%" (
    echo   [2/5] Virtual environment ready
) else (
    echo   [2/5] Creating virtual environment (first run only)...
    %LAUNCH% -m venv "%VENV%"
    if errorlevel 1 (
        echo.
        echo   [X] Could not create the virtual environment.
        echo       Try running this file as Administrator, or check your Python install.
        pause
        exit /b 1
    )
)

rem ---------- 3. Dependencies ------------------------------------------------
if exist "%VENV%\.deps-ok" (
    echo   [3/5] Dependencies already installed
) else (
    echo   [3/5] Installing dependencies (needs internet, one time)...
    "%PY%" -m pip install --upgrade pip --quiet --disable-pip-version-check
    "%PY%" -m pip install -r "%BACKEND%\requirements.txt" --quiet --disable-pip-version-check
    if errorlevel 1 (
        echo.
        echo   [X] Dependency install failed. Check your internet connection.
        echo       You can retry just this step with:
        echo         "%PY%" -m pip install -r "%BACKEND%\requirements.txt"
        pause
        exit /b 1
    )
    echo ok> "%VENV%\.deps-ok"
)

rem ---------- 4. Persistent secret + data dir --------------------------------
if not exist "%~dp0data" mkdir "%~dp0data"
if not exist "%~dp0data\secret.key" (
    echo   [4/5] Generating a persistent signing secret...
    for /f "delims=" %%s in ('"%PY%" -c "import secrets;print(secrets.token_hex(32))"') do set "NEWSECRET=%%s"
    > "%~dp0data\secret.key" echo !NEWSECRET!
) else (
    echo   [4/5] Using existing signing secret
)
set /p SENTINEL_SECRET=<"%~dp0data\secret.key"

rem ---------- 5. Port check --------------------------------------------------
echo   [5/5] Checking port %PORT%...
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo.
    echo   [!] Port %PORT% is already in use.
    echo       Sentinel may already be running - opening the console.
    echo       If not, close whatever is using port %PORT% and try again.
    echo.
    start "" "%URL%"
    pause
    exit /b 0
)

rem ---------- Launch --------------------------------------------------------
echo.
echo   Starting Sentinel at %URL%
echo   Press Ctrl+C or close this window to stop it.
echo.

rem Give uvicorn a moment, then open the browser.
start "" /b "%PY%" -c "import time,webbrowser; time.sleep(3); webbrowser.open('%URL%')"

cd /d "%BACKEND%"
"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --log-level info

echo.
echo   Sentinel stopped.
pause
