@echo off
title SmartGuard - Triggering Dummy Fall...
echo.
echo  ==========================================
echo    SmartGuard - Firing Dummy Fall Event
echo  ==========================================
echo.
echo  Sending fall alert to your phone...
echo.

cd /d "%~dp0"
call venv\Scripts\python.exe trigger_dummy_fall.py

echo.
echo  ==========================================
echo    Done! Check your phone for the alert.
echo  ==========================================
echo.
pause
