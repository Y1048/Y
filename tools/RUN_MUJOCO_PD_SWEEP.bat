@echo off
setlocal
set "ROOT=%~dp0.."
set "SCRIPT=%ROOT%\experiments\twist2_right_arm_manual\mujoco_pd_sweep.py"
echo SIMULATION ONLY - fixed pelvis - no G1, DDS, relay, or robot command.
if exist "%ROOT%\.venv-mujoco-pd\Scripts\python.exe" (
  "%ROOT%\.venv-mujoco-pd\Scripts\python.exe" -B "%SCRIPT%" %*
) else (
  py -3.11 -B "%SCRIPT%" %*
)
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo See experiments\twist2_right_arm_manual\MUJOCO_PD_SWEEP.md for isolated setup and result exclusions.
exit /b %RESULT%
