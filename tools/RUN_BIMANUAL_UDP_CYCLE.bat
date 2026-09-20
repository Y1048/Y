@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0.."
set "RUNTIME_ROOT=%USERPROFILE%\Desktop\G1_Teleop_Project"
if defined G1_BIMANUAL_RUNTIME_ROOT set "RUNTIME_ROOT=%G1_BIMANUAL_RUNTIME_ROOT%"
set "ENGINE_ROOT=%RUNTIME_ROOT%\logs\diagnostics\mujoco_versions\3.12.0"
echo Unity-free paired-hand UDP cycle. SIMULATION ONLY. No G1, DDS, SSH or motor output.
py -3.11 -B MuJoCo_G1_Controller\scripts\g1_bimanual_udp_cycle.py ^
  --engine-root "%ENGINE_ROOT%" ^
  --output-dir "logs\test_results\bimanual\udp_cycle" %*
exit /b %ERRORLEVEL%
