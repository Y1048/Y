@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo   G1 Mink -> Hardware Safety Gate LIVE DRY RUN
echo   - No Unitree SDK required
echo   - No DDS publisher
echo   - No robot command
echo ============================================================
echo.

echo [START] Safety gate monitor on localhost UDP 5008...
start "G1 Safety Gate Dry Run" cmd /k py -3.11 hardware\g1_arm_bridge\mink_target_dry_run.py

timeout /t 1 /nobreak >nul

echo [START] Mink controller...
py -3.11 MuJoCo_G1_Controller\scripts\run_mink_g1_right_arm_prototype.py

:end
echo.
pause
endlocal
