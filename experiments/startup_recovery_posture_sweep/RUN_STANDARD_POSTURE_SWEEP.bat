@echo off
setlocal
cd /d "%~dp0..\.."
set "MAP_PATH=%CD%\logs\experiments\startup_recovery_posture_sweep\latest_map.html"
set "SUMMARY_PATH=%CD%\logs\experiments\startup_recovery_posture_sweep\latest_summary.json"

echo ============================================================
echo G1 Startup Recovery - STANDARD 75-POSE OFFLINE SWEEP
echo   shoulder pitch: -15, 0, +15 deg
echo   shoulder roll : -30, -15, 0, +15, +30 deg
echo   elbow         : -30, -15, 0, +15, +30 deg
echo   Opens no DDS connection and sends no robot command
echo ============================================================
echo.

py -3.11 experiments\startup_recovery_posture_sweep\run_sweep.py ^
  --pitch-offsets=-15,0,15 ^
  --roll-offsets=-30,-15,0,15,30 ^
  --elbow-offsets=-30,-15,0,15,30 ^
  --workers 4 ^
  --case-timeout 240
set "exit_code=%errorlevel%"

echo.
if not "%exit_code%"=="0" (
    echo [FAIL] Standard posture sweep has unresolved infrastructure errors.
    echo [ACTION] Open %SUMMARY_PATH%, then resume its run directory with a longer --case-timeout.
) else (
    echo [PASS] Standard 75-pose sampled map completed.
    echo Map saved to: %MAP_PATH%
    echo Summary saved to: %SUMMARY_PATH%
    start "" "%MAP_PATH%"
)
echo Robot command: NONE
echo.
pause
exit /b %exit_code%
