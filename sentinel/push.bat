@echo off
setlocal
title Sentinel - Push to GitHub
cd /d "%~dp0"

echo.
echo   Sentinel -^> GitHub
echo   ------------------
echo.

where git >nul 2>&1
if errorlevel 1 (
    echo   [X] git not found. Install from https://git-scm.com/download/win
    pause
    exit /b 1
)

rem Refuse to push if anything secret is tracked.
for /f "delims=" %%f in ('git ls-files ^| findstr /i /r "\.db$ secret\.key \.apk$ \.keystore$ \.venv\"') do (
    echo   [X] Refusing to push - tracked file must not be public: %%f
    pause
    exit /b 1
)
echo   [1/3] No secrets tracked

git remote remove origin >nul 2>&1
git remote add origin https://github.com/valentinerio88vr-coder/sentinel.git
echo   [2/3] Remote configured

echo.
echo   Paste your Personal Access Token below and press Enter.
echo   Get one: GitHub - Settings - Developer settings - Personal access tokens
echo            - Tokens ^(classic^) - Generate new token - tick "repo" only.
echo.
set /p TOKEN="  Token: "

if "%TOKEN%"=="" (
    echo   Aborted. No token entered.
    pause
    exit /b 1
)

echo   [3/3] Pushing...
git push https://valentinerio88vr-coder:%TOKEN%@github.com/valentinerio88vr-coder/sentinel.git main
set PUSHED=%errorlevel%
set TOKEN=

if not "%PUSHED%"=="0" (
    echo.
    echo   Push failed. Common causes:
    echo     - token lacks the "repo" scope
    echo     - token expired or revoked
    echo     - the repo already has commits - run:
    echo         git fetch origin ^&^& git rebase origin/main ^&^& push.bat
    pause
    exit /b %PUSHED%
)

echo.
echo   Done. https://github.com/valentinerio88vr-coder/sentinel
pause
