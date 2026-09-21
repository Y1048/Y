@echo off
setlocal
cd /d "%~dp0.."
py -3.11 -B tools\SETUP_G1_VR_TELEOP.py %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo Install Python 3.11 x64 with the Python Launcher if py -3.11 is unavailable.
pause
endlocal & exit /b %RC%
