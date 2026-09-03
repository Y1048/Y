@echo off
setlocal
cd /d "%~dp0..\.."
set "MAP_PATH=%CD%\logs\experiments\startup_recovery_posture_sweep\latest_map.html"
set "SUMMARY_PATH=%CD%\logs\experiments\startup_recovery_posture_sweep\latest_summary.json"

echo ============================================================
echo G1 Startup Recovery - OFFLINE POSTURE SWEEP
echo   3 x 3 map: shoulder roll x elbow at captured shoulder pitch
echo   Opens no DDS connection and sends no robot command
echo ============================================================
echo.

py -3.11 experiments\startup_recovery_posture_sweep\run_sweep.py
set "exit_code=%errorlevel%"

echo.
if not "%exit_code%"=="0" (
    echo [FAIL] Startup Recovery posture sweep did not complete cleanly.
    echo [ACTION] Open %SUMMARY_PATH% and inspect cases with status ERROR and their log paths.
) else (
    echo [PASS] Posture sweep and sampled success map completed.
    echo Map saved to: %MAP_PATH%
    echo Summary saved to: %SUMMARY_PATH%
    start "" "%MAP_PATH%"
)
echo Robot command: NONE
echo.
pause
exit /b %exit_code%
