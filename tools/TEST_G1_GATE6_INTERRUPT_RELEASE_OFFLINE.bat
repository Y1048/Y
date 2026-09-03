@echo off
setlocal
cd /d "%~dp0.."
set "RESULT_PATH=%CD%\logs\test_results\g1_gate6_interrupt_release_offline.log"
if not exist "%CD%\logs\test_results" mkdir "%CD%\logs\test_results"

echo ============================================================
echo G1 GATE 6 INTERRUPTION RELEASE - OFFLINE TEST
echo   Simulates Ctrl+C release at maximum Arm SDK weight
echo   Verifies 2 s ramp-down and 25 zero-weight frames
echo   Unitree SDK: NONE / DDS publisher: NONE / Robot command: NONE
echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\test_gate6_interrupt_release.py > "%RESULT_PATH%" 2>&1
set "RC=%ERRORLEVEL%"
type "%RESULT_PATH%"
echo.
if "%RC%"=="0" (
    echo [PASS] Gate 6 interruption-release offline test passed.
    echo [INFO] Physical output remains locked in config\g1_gate6_interrupt_release_test.json.
) else (
    echo [FAIL] Gate 6 interruption-release offline test failed with code %RC%.
    echo [ACTION] Open %RESULT_PATH% and fix the first assertion or config error.
    echo [ACTION] Do not run the physical interruption test until this passes.
    >> "%RESULT_PATH%" echo [ACTION] Fix the first assertion or config error before any physical test.
)
echo Console log saved to: %RESULT_PATH%
echo.
pause
exit /b %RC%
