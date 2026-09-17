@echo off
setlocal
echo G1 cycle candidate deployed. Robot requires manual P after reviewing the startup summary.
echo 1: Yesterday limits on today's IK
echo 2: Today limits on today's IK
choice /C 12 /N /M "Select [1/2]: "
if errorlevel 2 goto today
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_TWIST2_MINK_CYCLE_CANDIDATE.ps1" -Mode All -Profile yesterday
exit /b
:today
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_TWIST2_MINK_CYCLE_CANDIDATE.ps1" -Mode All -Profile today
