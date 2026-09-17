@echo off
setlocal
cd /d "%~dp0.."
echo Two-arm kinematic SIMULATION ONLY. No Unity connection or G1 output.
for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss_fffffff"') do set STAMP=%%I
py -3.11 -B MuJoCo_G1_Controller\scripts\g1_bimanual_sim.py --viewer --output "logs\test_results\bimanual\demo_%STAMP%.jsonl" %*
if errorlevel 1 pause
endlocal
