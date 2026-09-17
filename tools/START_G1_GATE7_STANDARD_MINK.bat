@echo off
setlocal EnableExtensions
if /I "%~1"=="--logged" goto :logged
py -3.11 -B "%~dp0run_logged_standard_mink.py"
exit /b %errorlevel%

:logged
echo [PHYSICAL TRIAL] Standard Mink, 0.08 rad/s, 3 degrees, 20 seconds.
echo [ACTION] Confirm the safety conditions with Y/N for each run.
call "%~dp0START_G1_GATE7_LIVE_HARDWARE.bat" --first-live --standard-mink --external-unity-state
exit /b %errorlevel%
