@echo off
setlocal
cd /d "%~dp0.."
echo Unity paired-hand SIMULATION ONLY. UDP 127.0.0.1:5020. No G1 output.
for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss_fffffff"') do set STAMP=%%I
py -3.11 -B MuJoCo_G1_Controller\scripts\g1_bimanual_unity_sim.py --output "logs\test_results\bimanual\unity_%STAMP%.jsonl" %*
if errorlevel 1 pause
endlocal
