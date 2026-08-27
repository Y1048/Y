@echo off
setlocal
cd /d "%~dp0.."
set "RESULT_DIR=%CD%\logs\test_results"
set "RESULT_PATH=%RESULT_DIR%\g1_hold_dry_run.log"
if not exist "%RESULT_DIR%" mkdir "%RESULT_DIR%"

echo ============================================================
echo   G1 Right-Arm HOLD - DRY RUN ONLY
echo   - No Unitree SDK required
echo   - No DDS publisher
echo   - No robot command
echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\hold_dry_run.py --synthetic > "%RESULT_PATH%" 2>&1
set RC=%ERRORLEVEL%
type "%RESULT_PATH%"

echo.
if "%RC%"=="0" (
    echo [PASS] HOLD dry-run passed.
) else (
    echo [FAIL] HOLD dry-run failed with exit code %RC%.
    echo [ACTION] Open %RESULT_PATH% and fix the first rejected HOLD or stale-LowState assertion.
    echo [ACTION] Reproduce with: py -3.11 hardware\g1_arm_bridge\hold_dry_run.py --synthetic
    >> "%RESULT_PATH%" echo [ACTION] Fix the rejected HOLD or stale-state check before any hardware HOLD test.
)
echo Result saved to: %RESULT_PATH%
echo.
pause
exit /b %RC%
