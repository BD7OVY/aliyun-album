@echo off
setlocal
set VENV=%USERPROFILE%\.workbuddy\binaries\python\envs\aliyun-album

cd /d "%~dp0"

if not exist "%VENV%\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

echo ========================================
echo  Aliyun Album - Sync
echo ========================================
echo.

"%VENV%\Scripts\python.exe" harness/sync.py %*

pause

