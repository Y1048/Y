@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

title G1 Gate 7 Live Dry Run Launcher

echo ============================================================
echo G1 Gate 7 LIVE DRY RUN - NO ROBOT OUTPUT
echo   Unity ^> UDP 5005 ^> Mink/MuJoCo
echo   Mink ^> UDP 5008 ^> Gate 7 ^> Arm SDK candidate log
echo   Unitree SDK: NONE / DDS publisher: NONE / Robot command: NONE
echo ============================================================
echo.

netstat -ano -p UDP | findstr /R /C:":5008[ ]" >nul
if not errorlevel 1 (
    echo [ERROR] UDP port 5008 is already in use.
    echo [ACTION] Close the old Safety Gate or Gate 7 dry-run window, then retry.
    goto :failed
)

py -3.11 hardware\g1_arm_bridge\gate7_live_dry_run.py --validate-only
if errorlevel 1 (
    echo [ERROR] Gate 7 dry-run dependencies or locked config validation failed.
    echo [ACTION] Run tools\TEST_G1_GATE7_MINK_ARM_SDK_OFFLINE.bat and fix its first error.
    goto :failed
)

echo.
echo [START] Gate 7 live dry-run monitor on UDP 5008...
start "G1 Gate 7 Live Dry Run" cmd /k py -3.11 hardware\g1_arm_bridge\gate7_live_dry_run.py --measured-source mink --event-log auto --result-json auto
timeout /t 4 /nobreak >nul

netstat -ano -p UDP | findstr /R /C:":5008[ ]" >nul
if errorlevel 1 (
    echo [ERROR] Gate 7 monitor did not bind UDP 5008.
    echo [ACTION] Read the error in the separate Gate 7 window and retry.
    goto :failed
)

echo [START] Unity + Mink/MuJoCo VR path...
call START_VR_HAND_TO_MUJOCO.bat
set "RC=%ERRORLEVEL%"

echo.
echo [INFO] Keep the Gate 7 window open during the test.
echo [INFO] Press Ctrl+C in that window to finish and print the exact log paths.
echo [INFO] No process launched here can publish a G1 robot command.
pause
endlocal & exit /b %RC%

:failed
echo.
echo [FAIL] Gate 7 live dry-run was not started.
echo [ACTION] Follow the first [ACTION] message above, then run this launcher again.
pause
endlocal & exit /b 1
