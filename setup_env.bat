@echo off
chcp 65001 >nul
title Setup Environment (New Drive / New PC) - SchoolSM
color 0B
cd /d "%~dp0"

echo ================================================================
echo      SCHOOL MANAGEMENT SYSTEM - ENVIRONMENT SETUP WIZARD
echo ================================================================
echo.
echo This tool helps you setup / fix your Python environment when:
echo   1. You moved this folder to a different Drive (e.g. C:, D:, E:)
echo   2. You copied this project to a new Computer
echo.
echo ================================================================
echo.

:: 1. Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python is not installed or not added to system PATH!
    echo Please install Python 3.10+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b
)

:: 2. Check Git
where git >nul 2>nul
if %errorlevel% neq 0 (
    color 0E
    echo [WARNING] Git is not detected.
    echo If you plan to push code to GitHub, please install Git from https://git-scm.com/
    echo.
)

:: 3. Rebuild Virtual Environment
echo [1/3] Creating / Resetting Python Virtual Environment (.venv)...
if exist ".venv" (
    echo   - Removing old/incompatible .venv...
    rmdir /s /q ".venv"
)

python -m venv .venv
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to create virtual environment!
    pause
    exit /b
)
echo   [OK] .venv created successfully.
echo.

:: 4. Activate .venv and Install Packages
echo [2/3] Installing required packages from requirements.txt...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul 2>nul
pip install -r requirements.txt
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to install packages. Please check your internet connection.
    pause
    exit /b
)
echo   [OK] All packages installed successfully.
echo.

:: 5. Database Migrations
echo [3/3] Checking and applying Database Migrations...
python manage.py migrate
echo.

color 0A
echo ================================================================
echo   [SUCCESS] SETUP COMPLETED! EVERYTHING IS READY TO USE!
echo ================================================================
echo.
echo   * You can now run:
echo       1. run.bat          - To start the server or manage database
echo       2. push_github.bat  - To push code changes to GitHub ^& Render
echo.
echo ================================================================
pause
