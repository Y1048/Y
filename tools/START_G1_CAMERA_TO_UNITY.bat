@echo off
setlocal
cd /d "%~dp0.."
title G1 Camera to Unity - Read Only

echo ============================================================
echo   G1 Front Camera to Unity PiP [READ ONLY]
echo   SDK2 VideoClient.GetImageSample ^> WSL TCP 5011 ^> Unity
echo   Sends NO motor, mode, or camera-setting command
echo ============================================================
echo.

wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo [ERROR] The read-only G1 camera bridge exited with code %RC%.
    echo [ACTION] Confirm G1 power and Ethernet, Windows 192.168.123.99/24, and Unity Play mode.
    echo [ACTION] Run tools\DETECT_G1_NETWORK.bat if the G1 interface is missing.
)

echo.
echo [INFO] Closing this window stops only the camera preview bridge.
pause
endlocal & exit /b %RC%
