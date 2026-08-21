@echo off
setlocal
cd /d "%~dp0.."
echo G1 manual torso-front joint posture editor
echo ==========================================
echo This mode runs NO IK, UDP, workspace projection, or fallback.
echo Use the MuJoCo Joint panel to adjust the RIGHT arm freely.
echo Close the MuJoCo window when finished; the final pose is saved automatically.
echo.
py -3.11 MuJoCo_G1_Controller\scripts\edit_torso_joint_posture.py
set EXIT_CODE=%ERRORLEVEL%
echo.
if not "%EXIT_CODE%"=="0" echo Editor failed with exit code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
