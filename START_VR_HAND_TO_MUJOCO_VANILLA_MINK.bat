@echo off
setlocal EnableExtensions

title G1 Quest Hand Tracking - Vanilla Mink Comparison

echo ============================================================
echo G1 Quest to MuJoCo - VANILLA MINK COMPARISON
echo   Unity input/model: shared with the current controller
echo   IK: one 6D FrameTask on right_wrist_yaw_link
echo   Collision: Mink default 5/10 mm
echo   G1 publisher: NONE / Robot command: NONE
echo ============================================================
echo.

set "TELEOP_CONFIG=%~dp0config\teleop.json"
for /f %%P in ('py -3.11 -c "import json; print(json.load(open(r'%TELEOP_CONFIG%', encoding='utf-8'))['network']['udp_port'])"') do set "UDP_PORT=%%P"
if not defined UDP_PORT (
    echo [ERROR] Could not read network.udp_port from config\teleop.json.
    echo [ACTION] Restore or validate config\teleop.json, then run this BAT again.
    pause
    exit /b 1
)

netstat -ano -p UDP | findstr /R /C:":%UDP_PORT%[ ]" >nul
if not errorlevel 1 (
    echo [ERROR] UDP %UDP_PORT% is already used by another controller.
    echo [ACTION] Close the existing Mink/MuJoCo window before starting the vanilla comparison.
    pause
    exit /b 1
)

call "%~dp0START_VR_HAND_TO_MUJOCO.bat" --vanilla-mink --mink-default
exit /b %errorlevel%
