@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ============================================================
echo   G1 Mink ROLE-SPLIT V2
 echo   - Position: right_wrist_roll_link
 echo   - Orientation: right_wrist_yaw_link
 echo   - No speed mode switch
 echo   - No hard freeze
 echo ============================================================
echo.

netstat -ano -p UDP | findstr /R /C:":5005[ ]" >nul
if not errorlevel 1 (
    echo [ERROR] UDP port 5005 is already in use.
    echo         Close the currently running Mink controller first.
    goto :fail
)

py -3.11 MuJoCo_G1_Controller\scripts\run_mink_g1_right_arm_role_split_v2.py
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo [FAIL] Mink role-split V2 did not start cleanly.
exit /b 1
