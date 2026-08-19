@echo off
setlocal
set VENV=%USERPROFILE%\.workbuddy\binaries\python\envs\aliyun-album
set PORT=8091

cd /d "%~dp0"

if not exist "%VENV%\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

echo ========================================
echo  Photo Upload Server
echo ========================================
echo.

rem Allow LAN access through Windows Firewall (needs admin; ignore if fails)
netsh advfirewall firewall add rule name="Album Upload 8091" dir=in action=allow protocol=TCP localport=%PORT% >nul 2>&1

echo Starting upload server on port %PORT%...
echo Press Ctrl+C to stop.
echo.

"%VENV%\Scripts\python.exe" server\app.py %*

pause

