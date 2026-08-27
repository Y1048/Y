@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo G1 startup recovery - OFFLINE MINK QP DRY RUN
echo   - Uses the captured read-only LowState pose
echo   - Opens no network socket
echo   - Creates no DDS publisher
echo   - Sends no robot command
echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\simulate_startup_recovery.py
set "exit_code=%errorlevel%"

echo.
if not "%exit_code%"=="0" (
    echo [FAIL] Startup recovery remains blocked.
    echo [ACTION] Open logs\runtime\g1_startup_mink_recovery.json and read failure plus failure_details.
    echo [ACTION] If the captured pose is stale, reconnect read-only and run START_MINK_G1_HARDWARE_SYNC.bat before retrying.
    echo [ACTION] If the ready pose is invalid, run EDIT_G1_STARTUP_READY_POSE.bat and save a collision-clear pose.
) else (
    echo [PASS] Kinematic recovery passed offline.
    echo [NOTE] Acceleration and jerk are not hardware-approved.
)
echo Result saved to: %CD%\logs\runtime\g1_startup_mink_recovery.json
echo Robot command: NONE
echo.
pause
exit /b %exit_code%
