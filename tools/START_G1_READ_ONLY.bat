@echo off
setlocal
title G1 LowState Read Only
wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_read_only_wsl.sh
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
    echo [ERROR] G1 LowState read-only subscriber exited with code %RC%.
    echo [ACTION] Confirm the G1 Ethernet cable is connected and the Windows adapter uses 192.168.123.99/24.
    echo [ACTION] Run DETECT_G1_NETWORK.bat, then CONFIGURE_G1_ETHERNET.bat if the address is missing.
    echo [ACTION] Also verify Ubuntu and /home/user/.venvs/g1-teleop/bin/python exist in WSL.
)
echo No robot command was sent by this process.
pause
endlocal & exit /b %RC%
