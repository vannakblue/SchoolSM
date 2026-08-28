@echo off
chcp 65001 >nul
title Push Code to GitHub (Auto-Deploy to Render) - SchoolSM
color 0B
cd /d "%~dp0"

echo ================================================================
echo           PUSH CODE TO GITHUB ^& AUTO-DEPLOY TO RENDER
echo ================================================================
echo.

:: Check Git availability
where git >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Git is not installed or not in system PATH!
    echo Please install Git from https://git-scm.com/
    echo.
    pause
    exit /b
)

:: 1. Activate Virtual Environment if exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist "env\Scripts\activate.bat" (
    call env\Scripts\activate.bat
)

:: 2. Check for pending model migrations before pushing
echo [1/4] Checking for Django model changes...
python manage.py makemigrations --dry-run >nul 2>nul
if %errorlevel% equ 0 (
    python manage.py makemigrations >nul 2>nul
    echo   - Django migrations verified/created.
) else (
    echo   - No new migration needed.
)
echo.

:: 3. Show Git Status
echo [2/4] Current Changed Files:
echo ----------------------------------------------------------------
git status -s
echo ----------------------------------------------------------------
echo.

:: 4. Ask for Commit Message
set /p msg="Enter commit message (Press Enter for 'Update SchoolSM'): "
if "%msg%"=="" (
    for /f "tokens=1-4 delims=/ " %%a in ('date /t') do (set mydate=%%a-%%b-%%c)
    for /f "tokens=1-2 delims=: " %%a in ('time /t') do (set mytime=%%a:%%b)
    set msg=Update SchoolSM [%date% %time%]
)

echo.
echo [3/4] Staging and Committing changes...
git add .
git commit -m "%msg%"

if %errorlevel% neq 0 (
    echo.
    echo [INFO] No changes detected to commit or commit skipped.
)

:: 5. Push to GitHub
echo.
echo [4/4] Pushing code to GitHub (branch: main)...
echo.
git push origin main

if %errorlevel% equ 0 (
    color 0A
    echo.
    echo ================================================================
    echo   [SUCCESS] CODE PUSHED TO GITHUB SUCCESSFULLY!
    echo ================================================================
    echo.
    echo   * GitHub Repo: https://github.com/vannakblue/SchoolSM
    echo   * Render.com is now automatically deploying your changes.
    echo   * It will take about 1 - 2 minutes to go live on the server.
    echo.
) else (
    color 0C
    echo.
    echo ================================================================
    echo   [FAILED] Failed to push code to GitHub.
    echo ================================================================
    echo.
    echo Please check your internet connection or git credentials.
    echo.
)

echo ================================================================
echo Press any key to exit...
pause >nul
