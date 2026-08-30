@echo off
title SchoolSM - Build Mobile App
color 0b

where flutter >nul 2>nul
if %ERRORLEVEL% neq 0 (
    color 0c
    echo [ERROR] Flutter SDK not found in PATH!
    echo Please ensure Flutter SDK is installed and added to PATH.
    echo.
    pause
    exit /b 1
)

cd /d "%~dp0schoolsm_mobile"

:menu
cls
color 0b
echo ================================================================
echo        SchoolSM Mobile App Builder and Runner
echo ================================================================
echo.
echo   [1] Build Release Android APK (Build Android APK)
echo   [2] Run Mobile App on Web Browser (Google Chrome)
echo   [3] Check Flutter and Android System (Flutter Doctor)
echo   [4] Exit
echo.
echo ================================================================
set /p choice="Please select option [1-4] and press Enter: "

if "%choice%"=="1" goto build_apk
if "%choice%"=="2" goto run_web
if "%choice%"=="3" goto run_doctor
if "%choice%"=="4" exit /b 0
goto menu

:build_apk
cls
color 0b
echo ================================================================
echo   [*] Building Release Android APK...
echo ================================================================
echo.

echo [*] Resolving dependencies (flutter pub get)...
call flutter pub get

echo.
echo [*] Checking Android SDK...
call flutter doctor | findstr /C:"Unable to locate Android SDK" >nul
if %ERRORLEVEL% equ 0 (
    color 0c
    echo.
    echo ================================================================
    echo   [!] NOTICE: Android SDK is not yet installed on this PC.
    echo ================================================================
    echo.
    echo To build an Android APK file, Android SDK is required.
    echo.
    echo Easy steps to install:
    echo 1. Download and install Android Studio: https://developer.android.com/studio
    echo 2. Launch Android Studio once to install the Android SDK components.
    echo 3. Then re-run this script [Option 1] to build SchoolSM-Mobile.apk!
    echo.
    echo (Tip: You can also select [Option 2] to run the app in Chrome right now!)
    echo.
    echo ================================================================
    pause
    goto menu
)

echo.
echo [*] Compiling release APK (Please wait 1-3 minutes)...
call flutter build apk --release

if %ERRORLEVEL% equ 0 (
    color 0a
    echo.
    echo ================================================================
    echo   [SUCCESS] APK build completed successfully!
    echo ================================================================
    echo.
    
    if exist "build\app\outputs\flutter-apk\app-release.apk" (
        copy /y "build\app\outputs\flutter-apk\app-release.apk" "%~dp0SchoolSM-Mobile.apk" >nul
        echo [OK] APK copied to: "%~dp0SchoolSM-Mobile.apk"
        echo.
        explorer.exe /select,"%~dp0SchoolSM-Mobile.apk"
    ) else (
        explorer.exe "%~dp0schoolsm_mobile\build\app\outputs\flutter-apk"
    )
) else (
    color 0c
    echo.
    echo ================================================================
    echo   [ERROR] Failed to build APK. Please check logs above.
    echo ================================================================
)

echo.
pause
goto menu

:run_web
cls
color 0a
echo ================================================================
echo   [*] Launching SchoolSM Mobile App on Google Chrome...
echo ================================================================
echo.
call flutter run -d chrome
pause
goto menu

:run_doctor
cls
color 0e
echo ================================================================
echo   [*] Running Flutter Doctor Diagnostics...
echo ================================================================
echo.
call flutter doctor -v
echo.
pause
goto menu
