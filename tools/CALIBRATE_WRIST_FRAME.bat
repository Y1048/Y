@echo off
setlocal EnableExtensions

set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

echo G1 Quest-to-wrist frame calibration
echo ====================================
echo 1. Run live geometry teleop with valid hand tracking.
echo 2. Physically align the Quest hand and G1 wrist/hand in the same desired orientation.
echo 3. Keep both still, then continue this tool.
echo.
pause
py -3.11 MuJoCo_G1_Controller\scripts\calibrate_wrist_frame.py
if errorlevel 1 (
  echo.
  echo Calibration failed.
  pause
  exit /b 1
)
echo.
echo Calibration saved. Restart MuJoCo and Unity before testing.
pause
