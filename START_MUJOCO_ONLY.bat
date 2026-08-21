@echo off
setlocal EnableExtensions

title G1 MuJoCo Only

set "PROJECT_ROOT=%~dp0"
set "CONTROLLER_ROOT=%PROJECT_ROOT%MuJoCo_G1_Controller"
set "MUJOCO_SCRIPT=%CONTROLLER_ROOT%\scripts\run_configured_g1_teleop.py"
set "TELEOP_CONFIG=%PROJECT_ROOT%config\teleop.json"

echo ========================================
echo G1 MuJoCo configured teleoperation only
echo ========================================
echo.

if not exist "%MUJOCO_SCRIPT%" (
    echo [ERROR] Configured MuJoCo controller launcher was not found.
    echo %MUJOCO_SCRIPT%
    goto :failed
)

if not exist "%TELEOP_CONFIG%" (
    echo [ERROR] Teleoperation config was not found.
    echo %TELEOP_CONFIG%
    goto :failed
)

py -3.11 -c "import mujoco, numpy" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11 or MuJoCo is not ready.
    goto :failed
)

echo [START] MuJoCo G1 right-arm configured controller only
echo [INFO] Unity and Meta Horizon Link will not be started.
echo [INFO] Scene: control

echo.
cd /d "%CONTROLLER_ROOT%"
py -3.11 scripts\run_configured_g1_teleop.py --scene control --view overview

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
