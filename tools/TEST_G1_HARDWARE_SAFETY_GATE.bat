@echo off
setlocal
cd /d "%~dp0.."
set "RESULT_DIR=%CD%\logs\test_results"
set "RESULT_PATH=%RESULT_DIR%\g1_hardware_safety_gate.log"
if not exist "%RESULT_DIR%" mkdir "%RESULT_DIR%"

echo ============================================================
echo   G1 Hardware Safety Gate - OFFLINE TESTS ONLY
echo   - No Unitree SDK required
echo   - No DDS publisher
echo   - No robot command

echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\test_safety_gate.py > "%RESULT_PATH%" 2>&1
set RC=%ERRORLEVEL%
type "%RESULT_PATH%"

echo.
if "%RC%"=="0" (
    echo [PASS] Hardware safety gate offline tests passed.
) else (
    echo [FAIL] Hardware safety gate offline tests failed with code %RC%.
    echo [ACTION] Open %RESULT_PATH% and fix the first failed limit, stale-state, or rate-limit test.
    echo [ACTION] Reproduce with: py -3.11 hardware\g1_arm_bridge\test_safety_gate.py
    >> "%RESULT_PATH%" echo [ACTION] Do not continue to G1; fix the first failed Safety Gate test and rerun this BAT.
)

echo Result saved to: %RESULT_PATH%
echo.
pause
exit /b %RC%
