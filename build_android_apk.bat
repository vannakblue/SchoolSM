@echo off
chcp 65001 >nul
title SchoolSM - Build & Run Mobile App
color 0b

echo ================================================================
echo        🚀 កម្មវិធីគ្រប់គ្រង និងបង្កើត SchoolSM Mobile App
echo        SchoolSM Mobile Builder & Runner (Android, Web, Windows)
echo ================================================================
echo.

where flutter >nul 2>nul
if %ERRORLEVEL% neq 0 (
    color 0c
    echo [ERROR] រកមិនឃើញ Flutter SDK នៅក្នុងប្រព័ន្ធទេ!
    echo សូមប្រាកដថា Flutter SDK ត្រូវបានដំឡើង និងដាក់ក្នុង PATH Environment Variable.
    echo.
    pause
    exit /b 1
)

cd /d "%~dp0schoolsm_mobile"

:menu
cls
color 0b
echo ================================================================
echo        🚀 ជម្រើសបង្កើត និងបើកដំណើរការ SchoolSM Mobile App
echo ================================================================
echo.
echo   [1] បង្កើត Release APK សម្រាប់ Android (Build Android APK)
echo   [2] បើកដំណើរការ Mobile App លើ Web Browser (Chrome)
echo   [3] ពិនិត្យស្ថានភាពប្រព័ន្ធ (Flutter Doctor Diagnostic)
echo   [4] ចាកចេញ (Exit)
echo.
echo ================================================================
set /p choice="សូមជ្រើសរើសជម្រើស (1-4) រួចចុច Enter: "

if "%choice%"=="1" goto build_apk
if "%choice%"=="2" goto run_web
if "%choice%"=="3" goto run_doctor
if "%choice%"=="4" exit /b 0
goto menu

:build_apk
cls
color 0b
echo ================================================================
echo   [*] កំពុងចាប់ផ្តើមបង្កើត Release Android APK...
echo ================================================================
echo.

echo [*] កំពុងទាញយក Packages ចាំបាច់ (flutter pub get)...
call flutter pub get

echo.
echo [*] កំពុងពិនិត្យ Android SDK...
call flutter doctor | findstr /C:"Unable to locate Android SDK" >nul
if %ERRORLEVEL% equ 0 (
    color 0c
    echo.
    echo ================================================================
    echo   ⚠️ មូលហេតុដែលមិនទាន់អាចបង្កើត APK បាន:
    echo   [Android SDK Not Found on this PC]
    echo ================================================================
    echo.
    echo ម៉ាស៊ីនកុំព្យូទ័ររបស់អ្នកមិនទាន់មាន Android SDK (Software Development Kit) ទេ។
    echo.
    echo 📌 ដំណោះស្រាយងាយស្រួលបំផុត:
    echo 1. ទាញយក និងដំឡើង Android Studio ពី: https://developer.android.com/studio
    echo 2. បើក Android Studio ម្តង វានឹងដំឡើង Android SDK ស្វ័យប្រវត្តិ។
    echo 3. បន្ទាប់មកត្រឡប់មកចុច [1] លើឯកសារនេះម្តងទៀត វានឹងបង្កើតបាន APK ភ្លាមៗ!
    echo.
    echo (ចំណាំ: អ្នកក៏អាចជ្រើសរើសលេខ [2] ដើម្បី Run App លើ Chrome បានភ្លាមៗ!)
    echo.
    echo ================================================================
    pause
    goto menu
)

echo.
echo [*] កំពុង Compile កូដទៅជា APK (សូមរង់ចាំពី ១ ទៅ ៣ នាទី)...
call flutter build apk --release

if %ERRORLEVEL% equ 0 (
    color 0a
    echo.
    echo ================================================================
    echo   🎉 អបអរសាទរ! ការបង្កើត APK បានជោគជ័យ ១០០%%!
    echo ================================================================
    echo.
    
    if exist "build\app\outputs\flutter-apk\app-release.apk" (
        copy /y "build\app\outputs\flutter-apk\app-release.apk" "%~dp0SchoolSM-Mobile.apk" >nul
        echo [✓] ឯកសារ APK ត្រូវបានចម្លងទៅកាន់: "%~dp0SchoolSM-Mobile.apk"
        echo.
        explorer.exe /select,"%~dp0SchoolSM-Mobile.apk"
    ) else (
        explorer.exe "%~dp0schoolsm_mobile\build\app\outputs\flutter-apk"
    )
) else (
    color 0c
    echo.
    echo ================================================================
    echo   [ERROR] មានបញ្ហាក្នុងការ Build APK!
    echo ================================================================
)

echo.
pause
goto menu

:run_web
cls
color 0a
echo ================================================================
echo   🌐 កំពុងបើកដំណើរការ Mobile App លើ Web Browser (Chrome)...
echo ================================================================
echo.
call flutter run -d chrome
pause
goto menu

:run_doctor
cls
color 0e
echo ================================================================
echo   🔍 ពិនិត្យស្ថានភាព Flutter & Android Toolchain
echo ================================================================
echo.
call flutter doctor -v
echo.
pause
goto menu
