@echo off
setlocal
cd /d "%~dp0.."
echo G1 joint-space posture path verification
echo ========================================
py -3.11 MuJoCo_G1_Controller\scripts\verify_joint_posture_path.py
set EXIT_CODE=%ERRORLEVEL%
echo.
if "%EXIT_CODE%"=="0" (
  echo Verification passed.
) else (
  echo Verification failed. Capture a waypoint or revise the torso-front posture.
)
pause
exit /b %EXIT_CODE%
