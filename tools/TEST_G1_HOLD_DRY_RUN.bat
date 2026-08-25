@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo   G1 Right-Arm HOLD - DRY RUN ONLY
echo   - No Unitree SDK required
echo   - No DDS publisher
echo   - No robot command
echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\hold_dry_run.py --synthetic
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
    echo [PASS] HOLD dry-run passed.
) else (
    echo [FAIL] HOLD dry-run failed with exit code %RC%.
)
echo.
pause
exit /b %RC%
