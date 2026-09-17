@echo off
setlocal
cd /d "%~dp0.."
echo G1 WAIST BASELINE - READ ONLY - 15 seconds after first data
echo No motor command, mode change, or physical authorization.
wsl -d Ubuntu -- /home/user/.venvs/g1-teleop/bin/python -B /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/waist_baseline_read_only.py --capture
set "RC=%ERRORLEVEL%"
echo Results folder: %CD%\logs\read_only_baselines
if not "%RC%"=="0" echo [ACTION] Read the first error and summary.json. Check local Ethernet and WSL Python; do not start a physical trial.
pause
exit /b %RC%
