@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo G1 Startup Recovery - MuJoCo VISUAL REPLAY
echo   - Replays the latest validated offline recovery result
echo   - Uses no Unitree SDK, DDS, UDP, or robot connection
echo   - Sends no robot command
echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\replay_startup_recovery.py
set "exit_code=%errorlevel%"

echo.
if not "%exit_code%"=="0" (
    echo [FAIL] Startup Recovery replay could not be opened.
    echo [ACTION] Run TEST_G1_STARTUP_RECOVERY_OFFLINE.bat first and confirm its result is PASS.
    echo [ACTION] Then verify logs\runtime\g1_startup_mink_recovery.json exists and retry.
) else (
    echo [DONE] Startup Recovery replay closed normally.
)
echo Source result: %CD%\logs\runtime\g1_startup_mink_recovery.json
echo Robot command: NONE
echo.
pause
exit /b %exit_code%
