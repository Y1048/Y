@echo off
setlocal

echo BLOCKED: the 2026-09-14 physical probe stopped LowCmd before Regular/AI ownership was verified, and the robot lost actuator support.
echo Do not run this probe again. Keep the robot supported and power it off if actuator support is absent.
exit /b 1

set "REMOTE_DIR=/home/unitree/g1_velocity_mink_keypad_right_arm_20260914"
set "REMOTE_CMD=cd %REMOTE_DIR% && ./run_static_stand_handoff_probe.sh"

echo ============================================================
echo G1 STATIC-STAND HANDOFF PROBE
echo - No Unity, Mink UDP, keypad input, or arm trajectory
echo - 1 s capture, 4 s TWIST2 static-stand blend
echo - Checked writer stop and Regular/AI handoff attempt
echo - G1 must begin supported and in Regular/AI mode
echo ============================================================

if /I "%~1"=="--preview" (
  echo PREVIEW ONLY: ssh.exe -tt unitree@192.168.123.164 "%REMOTE_CMD%"
  exit /b 0
)

ssh.exe -tt -o StrictHostKeyChecking=yes -o ConnectTimeout=5 unitree@192.168.123.164 "%REMOTE_CMD%"
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo Probe ended with SSH/program code %RESULT%.
exit /b %RESULT%
