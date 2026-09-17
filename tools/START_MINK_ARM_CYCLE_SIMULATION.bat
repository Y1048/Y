@echo off
setlocal
set "mink_speed_profile=%~1"
if "%mink_speed_profile%"=="" set "mink_speed_profile=today"
if "%mink_speed_profile%"=="yesterday" goto profile_ok
if "%mink_speed_profile%"=="today" goto profile_ok
echo Invalid profile. Use yesterday or today.
exit /b 2
:profile_ok
pushd "%~dp0.."
set "G1_TWIST2_KEYBOARD_RATE=1"
set "G1_USE_HARDWARE_INITIAL_STATE=0"
set "G1_MINK_SIM_MUJOCO_ROOT=%CD%\logs\diagnostics\mujoco_versions\3.12.0"
if not exist "%CD%\logs\test_results\mink_right_arm_csv" mkdir "%CD%\logs\test_results\mink_right_arm_csv"
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss_fff"') do set "right_arm_csv=%CD%\logs\test_results\mink_right_arm_csv\mink_v5_right_arm_%%T.csv"
echo Simulation IK and geometry use isolated MuJoCo 3.12.0.
echo SIMULATION ONLY: pinch or tracking disengage returns the model arm; then re-engage.
echo No Robot or Relay is started. Candidate UDP 5008 output is disabled.
echo Selected speed profile: %mink_speed_profile%. Both use current IK.
echo yesterday: all joints 0.7 rad/s, acceleration 10 deg/s^2.
echo today: shoulder/elbow 90 deg/s, wrist 180 deg/s, acceleration 60 deg/s^2.
echo Right-arm IK CSV: %right_arm_csv%
echo Close the existing Mink Input window first to release UDP 5005.
py -3.11 -B MuJoCo_G1_Controller\scripts\run_mink_g1_right_arm_virtual_center_live_entry.py --ik-solver vanilla --simulation-arm-cycle --upstream-mink-collision --speed-profile %mink_speed_profile% --right-arm-csv "%right_arm_csv%"
set "cycle_result=%ERRORLEVEL%"
popd
if not "%cycle_result%"=="0" pause
exit /b %cycle_result%
