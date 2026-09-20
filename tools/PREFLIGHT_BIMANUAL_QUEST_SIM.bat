@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0.."
set "RUNTIME_ROOT=%USERPROFILE%\Desktop\G1_Teleop_Project"
if defined G1_BIMANUAL_RUNTIME_ROOT set "RUNTIME_ROOT=%G1_BIMANUAL_RUNTIME_ROOT%"
set "ENGINE_ROOT=%RUNTIME_ROOT%\logs\diagnostics\mujoco_versions\3.12.0"
for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss_fffffff"') do set STAMP=%%I
set "REPORT_DIR=logs\test_results\bimanual\preflight"
if not exist "%REPORT_DIR%" mkdir "%REPORT_DIR%"

echo [1/3] Structural, parity, port and MuJoCo checks
py -3.11 -B tools\bimanual_preflight.py --runtime-root "%RUNTIME_ROOT%" ^
  --engine-root "%ENGINE_ROOT%" --json-output "%REPORT_DIR%\preflight_%STAMP%.json"
if errorlevel 1 exit /b %ERRORLEVEL%

echo [2/3] Near-hands 12mm boundary sweep
set "PYTHONPATH=%ENGINE_ROOT%;%PYTHONPATH%"
py -3.11 -B backend\tests\test_bimanual_near_hands_sweep.py
if errorlevel 1 exit /b %ERRORLEVEL%

echo [3/3] Real UDP loopback cycle on an ephemeral port
py -3.11 -B MuJoCo_G1_Controller\scripts\g1_bimanual_udp_cycle.py ^
  --engine-root "%ENGINE_ROOT%" --output-dir "logs\test_results\bimanual\udp_cycle"
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo READY FOR QUEST TEST
echo SIMULATION ONLY. Unity and Quest operator feel are not validated by this preflight.
exit /b 0
