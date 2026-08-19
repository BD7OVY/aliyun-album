@echo off
setlocal
set VENV=%USERPROFILE%\.workbuddy\binaries\python\envs\aliyun-album
set PY=C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe
set REQUIREMENTS=pillow aligo

cd /d "%~dp0"

echo ========================================
echo  Aliyun Album - Setup Dependencies
echo ========================================
echo.

if not exist "%VENV%\Scripts\python.exe" (
    echo Creating virtual environment...
    "%PY%" -m venv "%VENV%"
)

echo Installing dependencies into venv...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install %REQUIREMENTS%

echo.
echo Done.
pause

