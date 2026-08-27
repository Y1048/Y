@echo off
setlocal
cd /d "%~dp0.."
set "RESULT_DIR=%CD%\logs\test_results"
set "RESULT_PATH=%RESULT_DIR%\g1_gate5_read_only.log"
if not exist "%RESULT_DIR%" mkdir "%RESULT_DIR%"

echo ============================================================
echo   G1 Gate 5 LowState Monitor - OFFLINE TEST
echo   - Uses synthetic UDP LowState telemetry
echo   - No Unitree SDK and no G1 connection
echo   - No DDS publisher and no robot command
echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\test_gate5_lowstate_safety_monitor.py > "%RESULT_PATH%" 2>&1
set RC=%ERRORLEVEL%
type "%RESULT_PATH%"

echo.
if "%RC%"=="0" (
    echo [PASS] Gate 5 offline monitor tests passed.
) else (
    echo [FAIL] Gate 5 offline monitor tests failed with code %RC%.
    echo [ACTION] Open %RESULT_PATH% and fix the first packet-contract, sequence, or stale-timeout failure.
    echo [ACTION] Reproduce with: py -3.11 hardware\g1_arm_bridge\test_gate5_lowstate_safety_monitor.py
    >> "%RESULT_PATH%" echo [ACTION] Fix the first Gate 5 failure before START_G1_GATE5_READ_ONLY.bat.
)
echo Result saved to: %RESULT_PATH%
echo.
pause
exit /b %RC%
