@echo off
chcp 65001 >nul
title Enable Maintenance Mode - SchoolSM
color 0E
cd /d "%~dp0"

echo ================================================================
echo           SCHOOLSM - ENABLE MAINTENANCE MODE
echo ================================================================
echo.

:: Create trigger flag
echo active > maintenance.flag
python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings'); django.setup(); from apps.attendance.models import AttendanceSetting; s = AttendanceSetting.get_settings(); s.is_maintenance_mode = True; s.save(update_fields=['is_maintenance_mode'])" 2>nul

if exist "maintenance.flag" (
    color 0A
    echo [STATUS] ----------------------------------------------------
    echo [SUCCESS] Maintenance Mode is now ACTIVATED!
    echo.
    echo   * Users ^(Students ^& Teachers^) will now see the Maintenance page.
    echo   * HTTP Status: 503 ^(Service Unavailable^)
    echo   * Superuser / Admin can still access /admin-panel/ to test changes.
    echo.
    echo   To turn it off later, double-click: maintenance_off.bat
    echo ------------------------------------------------------------
) else (
    color 0C
    echo [ERROR] Failed to create maintenance.flag file!
)

echo.
echo Press any key to close this window...
pause >nul
