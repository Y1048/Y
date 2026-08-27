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

netstat -ano -p UDP | findstr /R /C:":5008[ ]" >nul
if not errorlevel 1 (
    echo [ERROR] UDP port 5008 is already in use.
    echo [ACTION] Close the existing G1 Safety Gate Dry Run or Mink test window, then run this BAT again.
    goto :failed
)

echo [START] Safety gate monitor on localhost UDP 5008...
start "G1 Safety Gate Dry Run" cmd /k py -3.11 hardware\g1_arm_bridge\mink_target_dry_run.py

timeout /t 1 /nobreak >nul

echo [START] Mink controller...
py -3.11 MuJoCo_G1_Controller\scripts\run_mink_g1_right_arm_prototype.py
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo [FAIL] Mink controller exited with code %RC%.
    echo [ACTION] Close the separate Safety Gate window, run TEST_MINK_SAFETY_PIPELINE.bat, and inspect its saved log.
)

:end
echo.
pause
endlocal & exit /b %RC%

:failed
echo.
pause
endlocal & exit /b 1
