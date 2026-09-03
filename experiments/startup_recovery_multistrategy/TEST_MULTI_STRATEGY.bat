@echo off
setlocal
cd /d "%~dp0..\.."
set "SUMMARY_PATH=%CD%\logs\experiments\startup_recovery_multistrategy\summary.json"

echo ============================================================
echo G1 Startup Recovery - EXPERIMENTAL MULTI-STRATEGY TEST
echo   - Does not modify the current Startup Recovery
echo   - Opens no network socket or DDS publisher
echo   - Sends no robot command
echo ============================================================
echo.

py -3.11 experiments\startup_recovery_multistrategy\run_experiment.py
set "exit_code=%errorlevel%"

echo.
if not "%exit_code%"=="0" (
    echo [FAIL] Experimental multi-strategy recovery did not find a valid path.
    echo [ACTION] Open %SUMMARY_PATH% and inspect each candidate log path.
    echo [ACTION] Keep using the current validated Startup Recovery; this experiment is isolated.
) else (
    echo [PASS] Experimental multi-strategy comparison completed.
    echo [NOTE] This result is offline-only and is not approved for G1 command output.
)
echo Summary saved to: %SUMMARY_PATH%
echo Robot command: NONE
echo.
pause
exit /b %exit_code%
