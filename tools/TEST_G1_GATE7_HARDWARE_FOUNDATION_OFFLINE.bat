@echo off
setlocal
cd /d "%~dp0.."

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "TEST_LOG=%CD%\logs\test_results\g1_gate7_hardware_foundation_%STAMP%.log"
if not exist "%CD%\logs\test_results" mkdir "%CD%\logs\test_results"

echo ============================================================
echo G1 GATE 7 HARDWARE FOUNDATION - OFFLINE TEST
echo   - Validates Windows 5008 to WSL 5013 relay contract
echo   - Validates locked live Arm SDK adapter contract
echo   - Creates no DDS entity or publisher
echo   - Sends no robot command
echo ============================================================

py -3.11 hardware\g1_arm_bridge\gate7_mink_wsl_relay.py --target-host 127.0.0.1 --validate-only > "%TEST_LOG%" 2>&1
if errorlevel 1 goto :failed

py -3.11 hardware\g1_arm_bridge\gate7_live_arm_sdk.py --validate-only >> "%TEST_LOG%" 2>&1
if errorlevel 1 goto :failed

py -3.11 hardware\g1_arm_bridge\test_gate7_mink_wsl_relay.py >> "%TEST_LOG%" 2>&1
if errorlevel 1 goto :failed

py -3.11 hardware\g1_arm_bridge\test_gate7_live_arm_sdk.py >> "%TEST_LOG%" 2>&1
if errorlevel 1 goto :failed

type "%TEST_LOG%"
echo.
echo [PASS] Gate 7 hardware foundation passed without physical output.
echo Test log saved to: %TEST_LOG%
pause
exit /b 0

:failed
type "%TEST_LOG%"
echo.
echo [FAIL] Gate 7 hardware foundation validation failed.
echo [ACTION] Keep hardware output locked and fix the first error above.
echo Test log saved to: %TEST_LOG%
pause
exit /b 2
