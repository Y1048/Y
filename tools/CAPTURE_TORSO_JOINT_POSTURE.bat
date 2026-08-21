@echo off
setlocal
cd /d "%~dp0.."
echo G1 torso-front joint posture capture
echo ===================================
echo Keep the configured MuJoCo runtime running and CLOSE Unity.
echo Use the MuJoCo Joint panel to make the desired L-shaped right-arm pose,
echo then press any key here to capture the current seven right-arm joints.
echo.
pause
py -3.11 MuJoCo_G1_Controller\scripts\capture_torso_joint_posture.py
set EXIT_CODE=%ERRORLEVEL%
echo.
if not "%EXIT_CODE%"=="0" echo Capture failed with exit code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
