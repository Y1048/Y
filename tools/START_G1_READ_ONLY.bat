@echo off
title G1 LowState Read Only
wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_read_only_wsl.sh
echo.
echo No robot command was sent by this process.
pause
