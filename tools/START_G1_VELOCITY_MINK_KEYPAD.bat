@echo off
setlocal EnableExtensions
if "%~1"=="" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_G1_VELOCITY_MINK_KEYPAD.ps1" -Mode All
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_G1_VELOCITY_MINK_KEYPAD.ps1" %*
)
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" pause
exit /b %RESULT%
