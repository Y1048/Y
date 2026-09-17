@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
title TWIST2 VR Input Shadow - NO ROBOT OUTPUT
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0SET_UNITY_DISPLAY_MODE.ps1" -Mode simulation
if errorlevel 1 (
    echo [ERROR] Could not select the local simulation display.
    echo [ACTION] Stop Unity Play and check logs\runtime write access.
    pause
    exit /b 2
)
echo [ACTION] Stop Unity Play, start the Mink launcher below, then press Play again.
echo ============================================================
echo LOCAL INPUT SHADOW ONLY - NO G1, DDS, C++ POLICY OR FORWARDING
echo This window receives Mink UDP 5008 and records candidate targets.
echo In a second terminal, from this project folder, run:
echo   START_VR_HAND_TO_MUJOCO.bat --standard-mink --external-feedback
echo Do NOT start Gate 7 or any physical launcher for this check.
echo MuJoCo/Unity displays Mink, NOT the shadow candidate.
echo Pinch or input loss ends this receiver. Ctrl+C also stops it.
echo ============================================================
py -3.11 -B experiments\twist2_right_arm_manual\receive_vr_shadow.py
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo [ACTION] Read the error above. Close an old UDP 5008 receiver if needed.
    echo [ACTION] Confirm Unity Play and engagement, then restart this receiver.
)
echo Results: %CD%\logs\test_results\twist2_vr_shadow_*
pause
exit /b %RC%
