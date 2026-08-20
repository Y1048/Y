@echo off
setlocal

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "CONTROLLER_ROOT=%PROJECT_ROOT%\MuJoCo_G1_Controller"

cd /d "%CONTROLLER_ROOT%"

echo Starting fake VR input for the MuJoCo G1 test.
echo Use this only when testing without Quest hand tracking.
echo.

py -3.11 scripts\udp_fake_vr_sender.py

pause
endlocal
