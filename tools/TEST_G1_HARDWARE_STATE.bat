@echo off
setlocal
cd /d "%~dp0.."
set "RESULT_DIR=%CD%\logs\test_results"
set "RESULT_PATH=%RESULT_DIR%\g1_hardware_state.log"
if not exist "%RESULT_DIR%" mkdir "%RESULT_DIR%"

echo ============================================================
echo   G1 Hardware Runtime State - OFFLINE TEST
echo   - No Unitree SDK
echo   - No DDS publisher
echo   - No robot command
echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\test_hardware_state.py > "%RESULT_PATH%" 2>&1
set RC=%ERRORLEVEL%
type "%RESULT_PATH%"

echo.
if "%RC%"=="0" (
    echo [PASS] Hardware runtime state tests passed.
) else (
    echo [FAIL] Hardware runtime state tests failed with code %RC%.
    echo [ACTION] Open %RESULT_PATH% and fix the first failed test before running any hardware launcher.
    echo [ACTION] Reproduce with: py -3.11 hardware\g1_arm_bridge\test_hardware_state.py
    >> "%RESULT_PATH%" echo [ACTION] Fix the first failed test, then rerun TEST_G1_HARDWARE_STATE.bat.
)

echo Result saved to: %RESULT_PATH%
echo.
pause
exit /b %RC%
