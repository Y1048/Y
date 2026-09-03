@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

for /f "delims=" %%F in ('dir /b /a-d /o-d "logs\captures\g1_mink_capture_*.jsonl" 2^>nul') do if not defined CAPTURE set "CAPTURE=%CD%\logs\captures\%%F"
if not defined CAPTURE (
    echo [ERROR] No recorded Mink capture was found.
    echo [ACTION] Run tools\START_G1_GATE7_VR_RECORDING.bat with Quest first.
    goto :failed
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "RESULT_JSON=%CD%\logs\quality\g1_gate7_ruckig_hardware_profile_%STAMP%.json"
set "RESULT_HTML=%CD%\logs\quality\g1_gate7_ruckig_hardware_profile_%STAMP%.html"

echo ============================================================
echo G1 GATE 7 RUCKIG HARDWARE PROFILE - OFFLINE CAPTURE TEST
echo   Velocity: 40/100 deg/s
echo   Acceleration/Jerk scale: 1.0/1.0
echo   Unitree SDK: NONE / DDS publisher: NONE / Robot command: NONE
echo ============================================================
echo Capture: %CAPTURE%

py -3.11 -c "import ruckig; assert ruckig.__version__ == '0.19.4'" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python package ruckig 0.19.4 is unavailable.
    echo [ACTION] Run: py -3.11 -m pip install ruckig==0.19.4
    goto :failed
)

py -3.11 hardware\g1_arm_bridge\gate7_capture_quality.py "%CAPTURE%" --velocity-scale 1.0 --acceleration-scale 1.0 --jerk-scale 1.0 --require-ruckig-limit-pass --result-json "%RESULT_JSON%" --result-html "%RESULT_HTML%"
if errorlevel 1 goto :failed

echo.
echo [PASS] Locked physical-profile Ruckig trajectory passed derivative limits.
echo Result saved to: %RESULT_JSON%
echo Report saved to: %RESULT_HTML%
exit /b 0

:failed
echo.
echo [FAIL] Gate 7 Ruckig hardware-profile offline test failed.
echo [ACTION] Keep hardware_output_authorized=false and fix the first error.
if defined RESULT_JSON echo Result path: %RESULT_JSON%
exit /b 2
