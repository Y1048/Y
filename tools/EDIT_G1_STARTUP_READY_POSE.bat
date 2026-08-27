@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."

echo ============================================================
echo G1 Startup Recovery - MuJoCo READY POSE EDITOR
echo   - 1..7 selects a right-arm joint
echo   - Left/Right or A/D changes the selected angle
echo   - Comma/Period changes the angle step
echo   - S saves after joint/collision checks
echo   - Uses no Unitree SDK, DDS, UDP, or robot connection
echo   - Sends no robot command
echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\edit_startup_ready_pose.py
set "exit_code=%errorlevel%"

echo.
if not "%exit_code%"=="0" (
    echo [FAIL] Ready-pose editor stopped with an error.
    echo [ACTION] Run the Python command shown above in PowerShell and inspect its traceback.
    echo [ACTION] If the config is invalid, restore logs\runtime\startup_ready_pose_previous.json and retry.
) else (
    echo [DONE] Ready-pose editor closed normally.
)
echo Config:   %CD%\config\startup_recovery.json
echo Backup:   %CD%\logs\runtime\startup_ready_pose_previous.json
echo Robot command: NONE
echo.
pause
exit /b %exit_code%
