@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
if not exist logs\test_results\mink_right_arm_csv mkdir logs\test_results\mink_right_arm_csv
for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set STAMP=%%I
set OUTPUT=logs\test_results\mink_right_arm_csv\mink_right_arm_%STAMP%.csv
echo Mink right-arm receive-only logger: UDP 127.0.0.1:5008
echo Start this first, then run Unity/Mink in simulation mode.
echo No G1 relay, SDK, DDS, SSH, or motor command is created.
echo CSV: %OUTPUT%
py -3.11 -B hardware\g1_arm_bridge\g1_mink_right_arm_csv_logger.py --output "%OUTPUT%" %*
endlocal
