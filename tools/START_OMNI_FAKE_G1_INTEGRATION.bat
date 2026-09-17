@echo off
setlocal
cd /d "%~dp0.."
if not exist logs\test_results\omni_fake_g1 mkdir logs\test_results\omni_fake_g1
for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set STAMP=%%I
set OUTPUT=logs\test_results\omni_fake_g1\omni_fake_g1_%STAMP%.csv
set SECONDS=120
if not "%~1"=="" set SECONDS=%~1
set PREP_SECONDS=20
if not "%~2"=="" set PREP_SECONDS=%~2
echo ============================================================
echo PC-ONLY Omni integration test
echo Real Omni Connect input, local fake G1 receiver
echo Loopback test ports only; no SDK, DDS, LowCmd, SSH, or G1 output
echo Duration: %SECONDS% seconds
echo Preparation delay: %PREP_SECONDS% seconds, then 1 second calibration
echo CSV: %OUTPUT%
echo ============================================================
py -3.11 -B hardware\g1_arm_bridge\run_omni_fake_g1_integration.py ^
  --duration-seconds %SECONDS% ^
  --start-delay-seconds %PREP_SECONDS% ^
  --csv "%OUTPUT%"
set RESULT=%ERRORLEVEL%
if not "%RESULT%"=="0" echo [FAILED] Check that Omni Connect is running and port 32123 is listening.
if "%RESULT%"=="0" echo [PASS] PC-only Gateway and fake G1 receiver completed.
pause
exit /b %RESULT%
