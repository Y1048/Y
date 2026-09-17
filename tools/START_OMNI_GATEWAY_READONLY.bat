@echo off
setlocal
cd /d "%~dp0.."
if not exist logs\test_results\omni_gateway_readonly mkdir logs\test_results\omni_gateway_readonly
for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set STAMP=%%I
set OUTPUT=logs\test_results\omni_gateway_readonly\omni_gateway_%STAMP%.csv
echo Read-only Omni Gateway: WebSocket 127.0.0.1:32123
echo No G1 discovery, UDP output, SDK, DDS, or motor command.
echo CSV: %OUTPUT%
py -3.11 -B hardware\g1_arm_bridge\g1_omni_velocity_gateway.py --dry-run --csv "%OUTPUT%"
endlocal
