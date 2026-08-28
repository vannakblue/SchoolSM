@echo off
chcp 65001 >nul
title Create Clean Project Backup (.ZIP) - SchoolSM
color 0B
cd /d "%~dp0"

echo ================================================================
echo      CREATE CLEAN ^& PORTABLE PROJECT BACKUP (.ZIP)
echo ================================================================
echo.
echo This tool packages your entire project (Code + Database + Files)
echo into a clean, lightweight .zip file inside the 'backups\' folder.
echo.
echo * Note: .venv and cache folders are safely excluded to prevent
echo         path errors and keep file size super small (~2-5 MB).
echo ================================================================
echo.

:: Detect Python executable
set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 set "PYTHON_EXE=py"
)

"%PYTHON_EXE%" export_clean_zip.py

if %errorlevel% equ 0 (
    color 0A
    echo.
    echo ================================================================
    echo   [SUCCESS] Clean backup archive is ready in 'backups\' folder!
    echo ================================================================
    echo.
    echo You can now:
    echo   1. Copy this .zip to your USB Drive / Cloud / Telegram
    echo   2. Extract anywhere on any PC/Drive, then run 'setup_env.bat'
    echo.
    if exist "backups" start explorer "backups"
) else (
    color 0C
    echo [ERROR] Failed to create backup archive.
)

echo.
pause
