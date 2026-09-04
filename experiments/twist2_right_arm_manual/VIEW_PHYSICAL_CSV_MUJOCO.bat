@echo off
setlocal EnableExtensions
cd /d "%~dp0..\.."

set "CSV=%CD%\logs\physical_tests\g1_twist2_right_arm_trial_1787638008.csv"

echo ============================================================
echo TWIST2 RIGHT ARM PHYSICAL CSV - MUJOCO OFFLINE REPLAY
echo   CSV measured q_0..q_28 ^> MuJoCo canonical 29-joint model
echo   Unitree SDK: NONE / DDS: NONE / Socket: NONE
echo   Robot command: NONE
echo ============================================================
echo.

py -3.11 experiments\twist2_right_arm_manual\replay_physical_csv_mujoco.py --source "%CSV%" --validate-only
if errorlevel 1 goto :failed

py -3.11 experiments\twist2_right_arm_manual\replay_physical_csv_mujoco.py --source "%CSV%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :failed

echo.
echo [PASS] Physical CSV replay finished normally.
echo Source CSV: %CSV%
pause
exit /b 0

:failed
echo.
echo [FAIL] Physical CSV replay failed.
echo [ACTION] Read the first ERROR/ACTION line above and keep G1 disconnected.
echo Source CSV: %CSV%
pause
exit /b 2
