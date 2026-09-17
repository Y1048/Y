@echo off
setlocal
if not "%~1"=="" (
 call "%~dp0START_MINK_ARM_CYCLE_SIMULATION.bat" %*
 exit /b
)
echo SAME CURRENT IK - simulation comparison only. No Robot/Relay.
echo 1: Yesterday - all 0.7 rad/s, acceleration 10 deg/s^2
echo 2: Today - arm 90 deg/s, wrist 180 deg/s, acceleration 60 deg/s^2
choice /C 12 /N /M "Select profile [1/2]: "
if errorlevel 2 goto today
call "%~dp0START_MINK_ARM_CYCLE_SIMULATION.bat" yesterday
exit /b
:today
call "%~dp0START_MINK_ARM_CYCLE_SIMULATION.bat" today
