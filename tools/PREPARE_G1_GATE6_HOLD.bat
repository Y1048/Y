@echo off
setlocal
cd /d "%~dp0.."
set "RESULT_DIR=%CD%\logs\test_results"
set "RESULT_PATH=%RESULT_DIR%\g1_gate6_hold_prepare.log"
set "STATUS_PATH=%CD%\logs\runtime\g1_gate6_arm_sdk_hold.json"
if not exist "%RESULT_DIR%" mkdir "%RESULT_DIR%"

echo ============================================================
echo   G1 Gate 6 measured-pose HOLD - READ-ONLY PREPARATION
echo   - Queries current MotionSwitcher mode with CheckMode only
echo   - Subscribes to rt/lowstate and validates both arms
echo   - Builds the future rt/arm_sdk frame in memory only
echo   - Creates no DDS publisher and sends no robot command
echo ============================================================
echo.

wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_gate6_hold_wsl.sh > "%RESULT_PATH%" 2>&1
set "RC=%ERRORLEVEL%"
type "%RESULT_PATH%"

echo.
if "%RC%"=="0" (
    echo [PASS] Gate 6 measured-pose HOLD preparation passed.
    echo [INFO] Hardware output is still disabled; no publisher was created.
    echo [NOTE] Floor contact and balance were not verified by software.
    echo [ACTION] Physical output requires G1 standing on level ground in Regular Mode, not suspended.
) else (
    echo [BLOCKED] Gate 6 preparation failed with code %RC%.
    echo [ACTION] Open %STATUS_PATH% and %RESULT_PATH% and fix the first reported precondition.
    echo [ACTION] Keep hardware output disabled; verify Regular Mode, Ethernet, and arm motion before retrying.
    >> "%RESULT_PATH%" echo [ACTION] Keep hardware output disabled; verify Regular Mode, Ethernet, and arm motion before retrying.
)
echo Runtime status saved to: %STATUS_PATH%
echo Console log saved to: %RESULT_PATH%
echo No robot command was sent.
echo.
pause
exit /b %RC%
