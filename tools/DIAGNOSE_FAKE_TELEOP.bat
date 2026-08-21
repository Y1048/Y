@echo off
setlocal

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "CONTROLLER_ROOT=%PROJECT_ROOT%\MuJoCo_G1_Controller"

cd /d "%CONTROLLER_ROOT%"

echo G1 VR-free teleoperation diagnostic
echo ==================================
echo 1. Close Unity Play Mode completely.
echo 2. Keep START_VR_HAND_TO_MUJOCO.bat running.
echo 3. This test will inject fake hand poses and read UDP state port 5006.
echo.

py -3.11 scripts\diagnose_fake_teleop.py

set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
    echo Diagnostic finished: BACKEND PASS
) else (
    echo Diagnostic finished: FAIL or SUSPECT ^(exit %EXIT_CODE%^)
)
echo.
pause
exit /b %EXIT_CODE%
