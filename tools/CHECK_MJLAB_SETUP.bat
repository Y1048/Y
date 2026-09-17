@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0CHECK_MJLAB_SETUP.ps1"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" echo Verification finished successfully.
if "%RC%"=="3" echo Setup is still running. Run this file again later.
if not "%RC%"=="0" if not "%RC%"=="3" echo Setup did not complete. Review the log shown above.
pause
exit /b %RC%
