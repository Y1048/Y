@echo off
setlocal

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "CONTROLLER_ROOT=%PROJECT_ROOT%\MuJoCo_G1_Controller"
set "OUTPUT=%PROJECT_ROOT%\logs\camera\g1_head_camera_preview.bmp"

cd /d "%CONTROLLER_ROOT%"
py -3.11 scripts\g1_right_arm_udp_ik_demo.py --scene camera_validation --snapshot "%OUTPUT%"

if exist "%OUTPUT%" start "G1 Head Camera Preview" mspaint.exe "%OUTPUT%"
pause
endlocal
