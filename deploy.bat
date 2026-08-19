@echo off
setlocal

cd /d "%~dp0"

if not exist ".git" (
    echo [ERROR] No git repository found in this folder.
    echo         Run once:  git init
    echo         Then:      git add -A
    echo         Then:      git commit -m "init"
    echo         Then:      git branch -M main
    echo         Then:      git remote add origin YOUR_REPO_URL
    echo         Then re-run this file.
    pause
    exit /b 1
)

echo ========================================
echo  Aliyun Album - Deploy to GitHub
echo ========================================
echo.

git add -A

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set TS=%%i

git commit -m "sync %TS%"

git push origin main

echo.
if %errorlevel%==0 (
    echo [OK] Deployed. GitHub Pages will update in 1-2 minutes.
) else (
    echo [FAIL] Push failed. Check error above.
)

pause

