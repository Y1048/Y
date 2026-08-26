@echo off
setlocal EnableExtensions

title G1 MuJoCo Only

set "PROJECT_ROOT=%~dp0"
set "CONTROLLER_ROOT=%PROJECT_ROOT%MuJoCo_G1_Controller"
set "MUJOCO_SCRIPT=%CONTROLLER_ROOT%\scripts\run_mink_g1_right_arm_virtual_center_live.py"

echo ========================================
echo G1 MuJoCo Mink teleoperation only
echo ========================================
echo.

if not exist "%MUJOCO_SCRIPT%" (
    echo [ERROR] Configured MuJoCo controller launcher was not found.
    echo %MUJOCO_SCRIPT%
    goto :failed
)

py -3.11 -c "import mujoco, mink, numpy" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11, MuJoCo, or Mink is not ready.
    goto :failed
)

echo [START] MuJoCo G1 right-arm Mink controller only
echo [INFO] Unity and Meta Horizon Link will not be started.
echo [INFO] Scene: control

echo.
cd /d "%CONTROLLER_ROOT%"
py -3.11 scripts\run_mink_g1_right_arm_virtual_center_live.py --scene control --view overview

set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
    echo MuJoCo controller closed normally.
) else (
    echo MuJoCo controller exited with code %EXIT_CODE%.
)
pause
exit /b %EXIT_CODE%

:failed
echo.
echo MuJoCo was not started.
pause
exit /b 1
