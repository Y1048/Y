@echo off
setlocal
cd /d "%~dp0.."
set "RESULT_DIR=%CD%\logs\test_results"
set "RESULT_PATH=%RESULT_DIR%\g1_gate6_hold_offline.log"
if not exist "%RESULT_DIR%" mkdir "%RESULT_DIR%"

echo ============================================================
echo   G1 Gate 6 Arm SDK HOLD - OFFLINE CONTRACT TEST
echo   - Builds the exact 35-slot HG LowCmd payload
echo   - Verifies both arms, weight schedule, waist exclusion, CRC
echo   - Creates no ChannelFactory and no DDS publisher
echo   - Sends no robot command
echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\test_arm_sdk_hold_contract.py > "%RESULT_PATH%" 2>&1
if errorlevel 1 goto :failed

py -3.11 hardware\g1_arm_bridge\test_gate6_arm_sdk_hold.py >> "%RESULT_PATH%" 2>&1
if errorlevel 1 goto :failed

wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/user/Desktop/G1_Teleop_Project && /home/user/.venvs/g1-teleop/bin/python hardware/g1_arm_bridge/verify_arm_sdk_message_offline.py" >> "%RESULT_PATH%" 2>&1
if errorlevel 1 goto :failed

type "%RESULT_PATH%"
echo.
echo [PASS] Gate 6 offline command-contract tests passed.
echo [INFO] Hardware output remains disabled in config\g1_gate6_hold.json.
echo Result saved to: %RESULT_PATH%
echo.
pause
exit /b 0

:failed
set "RC=%ERRORLEVEL%"
type "%RESULT_PATH%"
echo.
echo [FAIL] Gate 6 offline verification failed with code %RC%.
echo [ACTION] Open %RESULT_PATH% and fix the first contract, authorization, SDK-layout, or CRC failure.
echo [ACTION] Do not run a hardware-output process until this test passes.
>> "%RESULT_PATH%" echo [ACTION] Fix the first Gate 6 contract, authorization, SDK-layout, or CRC failure before hardware output.
echo Result saved to: %RESULT_PATH%
echo.
pause
exit /b %RC%
