@echo off
setlocal EnableExtensions

set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

echo G1 Quest-to-wrist frame calibration
echo ====================================
echo 1. Run live geometry teleop with valid hand tracking and engage it.
echo 2. This tool will freeze ONLY G1 wrist orientation.
echo 3. XYZ tracking and geometry redundancy stay active.
echo 4. After freeze is confirmed, align the Quest hand to the desired G1 wrist/hand orientation.
echo.
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
