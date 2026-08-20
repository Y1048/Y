@echo off
setlocal

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "CONTROLLER_ROOT=%PROJECT_ROOT%\MuJoCo_G1_Controller"

cd /d "%CONTROLLER_ROOT%"

echo Starting G1 head-camera simulation.
echo.
echo - Official G1 D435i mounting transform
echo - 640 x 480, 30 FPS, BGR
echo - Unitree simulator-compatible shared memory
echo - MuJoCo window uses the robot head-camera view
echo.

py -3.11 scripts\g1_right_arm_udp_ik_demo.py --scene camera_validation --view head --publish-head-camera --camera-fps 30

pause
endlocal
