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
    echo [ACTION] Confirm this project is C:\Users\user\Desktop\G1_Teleop_Project, then restore the missing script from Git.
    goto :failed
)

py -3.11 -c "import mujoco, mink, numpy" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11, MuJoCo, or Mink is not ready.
    echo [ACTION] Run: py -3.11 -m pip install mujoco mink daqp qpsolvers numpy
    echo [ACTION] Then run this BAT again.
    goto :failed
)

echo [START] MuJoCo G1 right-arm Mink controller only
echo [INFO] Unity and Meta Horizon Link will not be started.
echo [INFO] Scene: control

echo.
cd /d "%CONTROLLER_ROOT%"
py -3.11 scripts\run_mink_g1_right_arm_virtual_center_live.py

set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
    echo MuJoCo controller closed normally.
) else (
    echo [FAIL] MuJoCo controller exited with code %EXIT_CODE%.
    echo [ACTION] Run the printed Python command in PowerShell and inspect the first traceback line.
)
pause
exit /b %EXIT_CODE%

:failed
echo.
echo [FAIL] MuJoCo was not started.
echo [ACTION] Complete the action shown immediately above, then run this BAT again.
pause
exit /b 1
