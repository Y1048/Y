@echo off
setlocal
pushd "%~dp0.."
echo OFFLINE ONLY: local CPU inference and synthetic state. No robot, SDK or publisher.
set "mink_torch_python=%CD%\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe"
if not exist "%mink_torch_python%" goto failed
if not defined VCVARS64 set "VCVARS64=%ProgramFiles%\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS64%" goto failed
call "%VCVARS64%" >nul
if errorlevel 1 goto failed
cl /nologo /std:c++17 /EHsc /W4 /WX experiments\twist2_right_arm_manual\mink_torch_owner_stdio_offline.cpp /Fe:logs\test_results\mink_torch_owner_stdio_offline.exe /Fo:logs\test_results\mink_torch_owner_stdio_offline.obj
if errorlevel 1 goto failed
"%mink_torch_python%" -B experiments\twist2_right_arm_manual\replay_mink_torch_owner.py
if errorlevel 1 goto failed
if /I "%~1"=="dynamics" (
  py -3.11 -B experiments\twist2_right_arm_manual\test_mujoco_feedback_offline.py
  if errorlevel 1 goto failed
  "%mink_torch_python%" -B experiments\twist2_right_arm_manual\replay_mink_torch_owner.py --dynamics
  if errorlevel 1 goto failed
)
if /I "%~1"=="combined" (
  "%mink_torch_python%" -B experiments\twist2_right_arm_manual\replay_mink_torch_owner.py --combined
  if errorlevel 1 goto failed
  py -3.11 -B experiments\twist2_right_arm_manual\audit_mink_torch_combined_geometry.py
  if errorlevel 1 goto failed
)
popd
exit /b 0
:failed
echo Offline policy integration failed. Nothing was deployed.
popd
exit /b 1
