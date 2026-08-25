@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ============================================================
echo   G1 Mink Baseline Collision Diagnostic - OFFLINE
echo   - No Unity
echo   - No Quest
echo   - No UDP controller
echo   - No robot command
echo ============================================================
echo.

echo [RUN] Checking nominal collision pairs across start postures...
py -3.11 MuJoCo_G1_Controller\scripts\diagnose_mink_baseline_collision_pairs.py
if errorlevel 1 (
    echo.
    echo [ERROR] Baseline collision diagnostic exited with an error.
    goto :end
)

echo.
echo [PASS] Baseline collision diagnostic completed.

:end
echo.
pause
endlocal
