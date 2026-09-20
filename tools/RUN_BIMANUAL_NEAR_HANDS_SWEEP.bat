@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0.."
set "RUNTIME_ROOT=%USERPROFILE%\Desktop\G1_Teleop_Project"
if defined G1_BIMANUAL_RUNTIME_ROOT set "RUNTIME_ROOT=%G1_BIMANUAL_RUNTIME_ROOT%"
set "ENGINE_ROOT=%RUNTIME_ROOT%\logs\diagnostics\mujoco_versions\3.12.0"
set "PYTHONPATH=%ENGINE_ROOT%;%PYTHONPATH%"
echo Near-hands boundary regression. SIMULATION ONLY. Hard limits are unchanged.
py -3.11 -B backend\tests\test_bimanual_near_hands_sweep.py %*
exit /b %ERRORLEVEL%
