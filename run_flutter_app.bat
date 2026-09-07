@echo off
title SchoolSM - Run Mobile App
color 0a

if exist "C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot" (
    set "JAVA_HOME=C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot"
    set "PATH=C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot\bin;%PATH%"
)

if exist "e:\AndroidSdk" (
    set "ANDROID_HOME=e:\AndroidSdk"
    set "ANDROID_SDK_ROOT=e:\AndroidSdk"
    set "PATH=e:\AndroidSdk\platform-tools;e:\AndroidSdk\cmdline-tools\latest\bin;%PATH%"
) else if exist "%LOCALAPPDATA%\Android\Sdk" (
    set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
    set "ANDROID_SDK_ROOT=%LOCALAPPDATA%\Android\Sdk"
    set "PATH=%LOCALAPPDATA%\Android\Sdk\platform-tools;%LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest\bin;%PATH%"
)

cd /d "%~dp0schoolsm_mobile"

if not exist "pubspec.yaml" (
    color 0c
    echo [ERROR] pubspec.yaml was not found!
    echo Current folder: %CD%
    echo Please make sure the folder "schoolsm_mobile" exists.
    pause
    exit /b 1
)

:menu
cls
color 0a
echo ================================================================
echo        SchoolSM Mobile App - Runner (Flutter)
echo ================================================================
echo.
echo   [1] Run in Google Chrome (Mobile Web Preview) [Recommended]
echo   [2] Run on Connected Android Phone / Emulator
echo   [3] Check Connected Devices (flutter devices)
echo   [4] Build Release Android APK (SchoolSM-Mobile.apk)
echo   [0] Exit
echo.
echo ================================================================
set choice=1
set /p choice="Select an option [0-4] (Press Enter for 1): "

if "%choice%"=="1" goto run_chrome
if "%choice%"=="2" goto run_device
if "%choice%"=="3" goto list_devices
if "%choice%"=="4" goto build_apk
if "%choice%"=="0" exit /b 0

echo Invalid choice!
timeout /t 2 >nul
goto menu

:run_chrome
cls
echo ================================================================
echo   [*] Launching SchoolSM Mobile App on Google Chrome...
echo ================================================================
echo.
call flutter run -d chrome
pause
goto menu

:run_device
cls
echo ================================================================
echo   [*] Available Devices / Emulators:
echo ================================================================
call flutter devices
echo.
echo ================================================================
echo   [*] Starting Flutter App on device...
echo ================================================================
call flutter run
pause
goto menu

:list_devices
cls
echo ================================================================
echo   [*] Detected Devices:
echo ================================================================
call flutter devices
echo.
pause
goto menu

:build_apk
cd /d "%~dp0"
if exist "build_android_apk.bat" (
    call build_android_apk.bat
) else (
    cd /d "%~dp0schoolsm_mobile"
    call flutter build apk --release
)
pause
goto menu
