@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "RESULT_JSON=%CD%\logs\test_results\g1_gate7_first_live_virtual_e2e_%STAMP%.json"
set "TEST_LOG=%CD%\logs\test_results\g1_gate7_first_live_offline_%STAMP%.log"
set "GATE7_CONFIG=%CD%\config\g1_gate7_first_live_mink_arm_sdk.json"
set "HARDWARE_CONFIG=%CD%\config\g1_gate7_first_live_hardware_output.json"
if not exist "%CD%\logs\test_results" mkdir "%CD%\logs\test_results"

echo ============================================================
echo G1 GATE 7 FIRST LIVE PROFILE - OFFLINE VERIFICATION
echo   Unitree SDK: NONE / DDS publisher: NONE / Robot command: NONE
echo ============================================================

py -3.11 hardware\g1_arm_bridge\gate7_live_arm_sdk.py --validate-only --gate7-config "%GATE7_CONFIG%" --hardware-config "%HARDWARE_CONFIG%" > "%TEST_LOG%" 2>&1
if errorlevel 1 goto :failed

py -3.11 hardware\g1_arm_bridge\test_gate7_first_live_profile.py >> "%TEST_LOG%" 2>&1
if errorlevel 1 goto :failed

py -3.11 hardware\g1_arm_bridge\gate7_hardware_virtual_e2e.py --relay-port 5028 --adapter-port 5033 --gate7-config "%GATE7_CONFIG%" --hardware-config "%HARDWARE_CONFIG%" --result-json "%RESULT_JSON%" >> "%TEST_LOG%" 2>&1
if errorlevel 1 goto :failed

type "%TEST_LOG%"
echo.
echo [PASS] First-live profile passed without G1 output.
echo Result saved to: %RESULT_JSON%
echo Test log saved to: %TEST_LOG%
pause
exit /b 0

:failed
type "%TEST_LOG%"
echo.
echo [FAIL] First-live offline verification failed.
echo [ACTION] Keep both first-live config locks false and fix the first error above.
if exist "%RESULT_JSON%" echo Result saved to: %RESULT_JSON%
echo Test log saved to: %TEST_LOG%
pause
exit /b 2
