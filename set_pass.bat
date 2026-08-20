@echo off
setlocal
set VENV=%USERPROFILE%\.workbuddy\binaries\python\envs\aliyun-album

cd /d "%~dp0"

if not exist "%VENV%\Scripts\python.exe" (
    echo [ERROR] Python venv not found. Run setup.bat first.
    pause
    exit /b 1
)

echo ========================================
echo  Set Gallery Access Password
echo ========================================
echo.

"%VENV%\Scripts\python.exe" harness/sync.py --set-pass

echo.
pause
