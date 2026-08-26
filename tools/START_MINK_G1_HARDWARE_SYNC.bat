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

echo [STEP 0] Starting read-only G1 LowState forwarder...
start "G1 LowState Read Only Forwarder" wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_read_only_wsl.sh --forward-host 127.0.0.1 --forward-port 5007 --forward-hz 30
timeout /t 3 /nobreak >nul

echo [STEP 1] Waiting for a fresh G1 right-arm LowState snapshot...
py -3.11 hardware\g1_arm_bridge\receive_initial_state.py --port 5007 --timeout 8
if errorlevel 1 (
    echo.
    echo [ERROR] Hardware pose synchronization failed.
    echo [INFO] Check the G1 LowState Read Only Forwarder window.
    goto :end
)

echo.
echo [STEP 2] Verifying measured pose through Mink and Unity packet...
set G1_USE_HARDWARE_INITIAL_STATE=1
py -3.11 hardware\g1_arm_bridge\verify_initial_pose_sync.py
if errorlevel 1 (
    echo.
    echo [ERROR] Hardware pose synchronization validation failed.
    goto :end
)

echo.
echo [STEP 3] Starting current virtual-center Mink controller...
echo [INFO] Hardware output remains disabled in this process.
py -3.11 MuJoCo_G1_Controller\scripts\run_mink_g1_right_arm_virtual_center_live.py
if errorlevel 1 (
    echo.
    echo [ERROR] Mink hardware-synchronized startup exited with an error.
)

:end
echo.
pause
endlocal
