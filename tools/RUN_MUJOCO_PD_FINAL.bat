@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\.venv-mujoco-pd\Scripts\python.exe"
if not exist "%PY%" (
  echo Missing isolated environment: .venv-mujoco-pd
  echo See experiments\twist2_right_arm_manual\MUJOCO_PD_FINAL.md
  exit /b 2
)
if "%~1"=="" goto help
"%PY%" -B "%ROOT%\experiments\twist2_right_arm_manual\mujoco_pd_final.py" %*
exit /b %errorlevel%

:help
"%PY%" -B "%ROOT%\experiments\twist2_right_arm_manual\mujoco_pd_final.py" --help
exit /b %errorlevel%
