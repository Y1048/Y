@echo off
setlocal
cd /d "%~dp0.."
py -3.11 -B tools\G1_VR_TELEOP_LAUNCH.py %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
endlocal & exit /b %RC%
