@echo off
setlocal EnableExtensions

set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

echo G1 Quest-to-wrist frame calibration
echo ====================================
echo Start this tool BEFORE engaging the Quest hand.
echo It will request wrist-orientation freeze first,
echo then wait for active hand engagement.
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
