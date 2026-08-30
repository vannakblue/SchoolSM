@echo off
chcp 65001 >nul
title SchoolSM - Run Mobile App
color 0a

echo ================================================================
echo        📱 បើកដំណើរការ SchoolSM Mobile App
echo        Running SchoolSM Mobile Application
echo ================================================================
echo.

cd /d "%~dp0schoolsm_mobile"

echo [*] កំពុងពិនិត្យឧបករណ៍ ឬ Emulator ដែលបានភ្ជាប់...
call flutter devices
echo.

echo [*] កំពុងចាប់ផ្តើមដំណើរការ App...
call flutter run

pause
