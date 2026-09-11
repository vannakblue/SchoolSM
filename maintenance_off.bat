@echo off
chcp 65001 >nul
title Disable Maintenance Mode - SchoolSM
color 0B
cd /d "%~dp0"

echo ================================================================
echo           SCHOOLSM - DISABLE MAINTENANCE MODE
echo ================================================================
echo.

if exist "maintenance.flag" (
    del /f /q "maintenance.flag"
    python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings'); django.setup(); from apps.attendance.models import AttendanceSetting; s = AttendanceSetting.get_settings(); s.is_maintenance_mode = False; s.save(update_fields=['is_maintenance_mode'])" 2>nul
    color 0A
    echo [STATUS] ----------------------------------------------------
    echo [SUCCESS] Maintenance Mode is now DEACTIVATED!
    echo.
    echo   * The SchoolSM system is now LIVE for all users!
    echo   * Users can access dashboards, attendance, and exam systems.
    echo ------------------------------------------------------------
) else (
    echo [INFO] ------------------------------------------------------
    echo [NOTE] Maintenance mode was already inactive.
    echo   * The system is currently LIVE for all users.
    echo ------------------------------------------------------------
)

echo.
echo Press any key to close this window...
pause >nul
