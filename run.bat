@echo off
title School Management System - SchoolSM
color 0B
cd /d "%~dp0"

:: 1. Activate Virtual Environment (.venv)
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist "env\Scripts\activate.bat" (
    call env\Scripts\activate.bat
)

:menu
cls
echo ================================================================
echo           SCHOOL MANAGEMENT SYSTEM (SchoolSM)
echo ================================================================
echo.
echo   [1] Start Server and Open Web Browser (Default)
echo   [2] Apply Database Migrations (migrate)
echo   [3] Create Admin Account (createsuperuser)
echo   [4] Run Test Suite (test_suite.py)
echo   [5] Open Django Shell (Python Console)
echo   [6] Allow Mobile Wi-Fi Access (Open Port 8000 in Windows Firewall)
echo   [7] Start Public Online Tunnel (Access via 5G / Internet from anywhere)
echo   [8] Backup Database (Create Instant Snapshot / Save Test Data)
echo   [9] Restore Database (Restore from Snapshot / Backup File)
echo   [10] Open Backups Folder in File Explorer
echo   [0] Exit
echo.
echo ================================================================
set choice=1
set /p choice="Enter your choice [0-10] (Press Enter for Option 1): "

if "%choice%"=="1" goto start_server
if "%choice%"=="2" goto migrate
if "%choice%"=="3" goto createsuperuser
if "%choice%"=="4" goto run_tests
if "%choice%"=="5" goto shell
if "%choice%"=="6" goto allow_firewall
if "%choice%"=="7" goto start_tunnel
if "%choice%"=="8" goto backup_db
if "%choice%"=="9" goto restore_db
if "%choice%"=="10" goto open_backups
if "%choice%"=="0" goto end

echo Invalid option! Please try again.
timeout /t 2 >nul
goto menu

:start_server
cls
echo ================================================================
echo   STARTING SCHOOL MANAGEMENT SYSTEM SERVER
echo ================================================================
echo.
echo   * Local URL:  http://127.0.0.1:8000/
echo   * Mobile/LAN: http://0.0.0.0:8000/
echo   * Press [CTRL + C] in this window to stop the server
echo.
echo   * Opening Web Browser...
echo ================================================================
start http://127.0.0.1:8000/
python manage.py runserver 0.0.0.0:8000
echo.
echo Server has stopped.
pause
goto menu

:migrate
cls
echo ================================================================
echo   DATABASE MIGRATION (makemigrations + migrate)
echo ================================================================
echo.
python manage.py makemigrations
python manage.py migrate
echo.
echo [DONE] Database updated successfully!
echo.
pause
goto menu

:createsuperuser
cls
echo ================================================================
echo   CREATE ADMIN / SUPERUSER
echo ================================================================
echo.
python manage.py createsuperuser
echo.
pause
goto menu

:run_tests
cls
echo ================================================================
echo   RUNNING TESTS
echo ================================================================
echo.
if exist "test_suite.py" (
    python test_suite.py
) else (
    python manage.py test
)
echo.
pause
goto menu

:shell
cls
echo ================================================================
echo   DJANGO SHELL (Type exit() to return)
echo ================================================================
echo.
python manage.py shell
goto menu

:allow_firewall
cls
echo ================================================================
echo   ALLOWING PORT 8000 IN WINDOWS FIREWALL (Run as Admin)
echo ================================================================
echo.
powershell -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -Command netsh advfirewall firewall add rule name=\"Django SchoolSM 8000\" dir=in action=allow protocol=TCP localport=8000'"
echo.
echo [DONE] Firewall rule requested. If prompted by Windows UAC, click YES.
echo.
pause
goto menu

:start_tunnel
cls
echo ================================================================
echo   STARTING PUBLIC ONLINE TUNNEL (Access via 5G / Smartphone)
echo ================================================================
echo.
echo   * This creates a live public URL for smartphones with 5G/4G
echo   * Keep this window OPEN while testing on your phone.
echo.
echo ================================================================
npx --yes localtunnel --port 8000
pause
goto menu

:backup_db
cls
echo ================================================================
echo   DATABASE BACKUP / INSTANT SNAPSHOT
echo ================================================================
echo.
echo   * This will snapshot the current db.sqlite3 into backups/ folder.
echo.
set /p note="Enter a label/note for this snapshot (Optional, Press Enter to skip): "
if "%note%"=="" set note=Snapshot via run.bat
echo.
python manage.py backup_db --label "%note%"
echo.
pause
goto menu

:restore_db
cls
echo ================================================================
echo   RESTORE DATABASE FROM SNAPSHOT
echo ================================================================
echo.
echo   [Available Snapshots in backups/]:
echo.
python manage.py backup_db --list
echo.
echo ================================================================
echo   [1] Restore the LATEST snapshot automatically
echo   [2] Enter specific backup filename to restore
echo   [0] Cancel / Go back to main menu
echo ================================================================
set rchoice=1
set /p rchoice="Enter your choice [0-2] (Default 1 for Latest): "

if "%rchoice%"=="0" goto menu
if "%rchoice%"=="1" (
    echo.
    python manage.py restore_db --latest
    echo.
    pause
    goto menu
)
if "%rchoice%"=="2" (
    echo.
    set /p bfile="Enter exact backup filename (e.g. db_backup_...sqlite3): "
    echo.
    python manage.py restore_db --file "%bfile%"
    echo.
    pause
    goto menu
)
goto menu

:open_backups
cls
echo Opening backups folder in Windows Explorer...
if not exist "backups" mkdir backups
start explorer "backups"
timeout /t 1 >nul
goto menu

:end
exit
