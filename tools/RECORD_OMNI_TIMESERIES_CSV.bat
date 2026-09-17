@echo off
setlocal
cd /d "%~dp0.."

if not exist logs\test_results\omni_timeseries mkdir logs\test_results\omni_timeseries
for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set STAMP=%%I

set DURATION_SECONDS=120
if not "%~1"=="" set DURATION_SECONDS=%~1
set PREP_SECONDS=20
if not "%~2"=="" set PREP_SECONDS=%~2
set OUTPUT=logs\test_results\omni_timeseries\omni_timeseries_%STAMP%.csv

echo ============================================================
echo Omni time-series CSV recorder
echo Raw: mx, my, Omni yaw rate
echo Mapped: vx, vy, yaw rate and yaw diff
echo Preparation: %PREP_SECONDS% seconds, then 1 second origin calibration
echo Duration: %DURATION_SECONDS% seconds
echo CSV: %OUTPUT%
echo Read-only: no G1 discovery, UDP output, SDK, DDS, or motor command
echo ============================================================

py -3.11 -B hardware\g1_arm_bridge\g1_omni_velocity_gateway.py ^
  --dry-run ^
  --duration-seconds %DURATION_SECONDS% ^
  --start-delay-seconds %PREP_SECONDS% ^
  --csv "%OUTPUT%"
set RESULT=%ERRORLEVEL%

if "%RESULT%"=="0" echo [PASS] CSV saved: %OUTPUT%
if not "%RESULT%"=="0" echo [FAILED] Check that Omni Connect is running and port 32123 is listening.
pause
exit /b %RESULT%
