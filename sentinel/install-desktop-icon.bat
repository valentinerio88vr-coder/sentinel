@echo off
setlocal
title Sentinel - Install Desktop Icon
cd /d "%~dp0"

echo.
echo   Creating a Sentinel shortcut on your Desktop...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\make-shortcut.ps1" -Root "%~dp0"
if errorlevel 1 (
    echo.
    echo   [X] Shortcut creation failed.
    echo       You can still start Sentinel by double-clicking run.bat
    echo.
    pause
    exit /b 1
)

echo.
echo   Done. Look for "Sentinel" on your Desktop.
echo   You can drag it to the taskbar or Start menu if you prefer.
echo.
pause
