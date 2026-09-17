@echo off
setlocal EnableExtensions
if not "%~1"=="" goto :arguments
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_TWIST2_MINK_UDP.ps1" -Mode All
goto :done
:arguments
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_TWIST2_MINK_UDP.ps1" %*
:done
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" pause
exit /b %RESULT%
