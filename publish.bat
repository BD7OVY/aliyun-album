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
echo  Step 1/2 - Process new photos
echo ========================================
echo.

"%VENV%\Scripts\python.exe" harness/publish.py
if errorlevel 2 (
    echo.
    echo No new photos - nothing to publish.
    pause
    exit /b 0
)
if errorlevel 1 (
    echo.
    echo [STOP] Photo processing failed. Fix errors above, then re-run.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Step 2/2 - Deploy to GitHub Pages
echo ========================================
echo.
call deploy.bat
