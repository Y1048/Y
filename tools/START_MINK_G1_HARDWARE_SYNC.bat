@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo   G1 Mink Right-Arm - Hardware Pose Sync Startup
echo   - Receives READ-ONLY LowState snapshot on UDP 5007
echo   - Seeds Mink from actual G1 right-arm pose
echo   - Sends NO robot motor command
echo ============================================================
echo.

echo [STEP 1] Waiting for a fresh G1 right-arm LowState snapshot...
py -3.11 hardware\g1_arm_bridge\receive_initial_state.py --port 5007 --timeout 8
if errorlevel 1 (
    echo.
    echo [ERROR] Hardware pose synchronization failed.
    echo [INFO] Start the Linux read-only bridge with --forward-host ^<THIS_PC_IP^>.
    goto :end
)

echo.
echo [STEP 2] Starting Mink from the measured G1 posture...
set G1_USE_HARDWARE_INITIAL_STATE=1
py -3.11 MuJoCo_G1_Controller\scripts\run_mink_g1_right_arm_prototype.py
if errorlevel 1 (
    echo.
    echo [ERROR] Mink hardware-synchronized startup exited with an error.
)

:end
echo.
pause
endlocal
