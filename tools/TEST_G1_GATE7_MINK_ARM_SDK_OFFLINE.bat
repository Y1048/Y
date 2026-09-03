@echo off
setlocal
cd /d "%~dp0.."

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "RESULT_JSON=%CD%\logs\test_results\g1_gate7_mink_arm_sdk_offline_%STAMP%.json"
set "TEST_LOG=%CD%\logs\test_results\g1_gate7_mink_arm_sdk_tests_%STAMP%.log"

if not exist "%CD%\logs\test_results" mkdir "%CD%\logs\test_results"

echo ============================================================
echo G1 Gate 7 Mink to Arm SDK - OFFLINE ONLY
echo   - No Unitree SDK
echo   - No DDS entity or publisher
echo   - No robot command
echo   - Pinch: immediate Regular return
echo   - Unintended disengagement: HOLD 10 s, then Regular return
echo ============================================================

py -3.11 hardware\g1_arm_bridge\test_arm_sdk_teleop_contract.py > "%TEST_LOG%" 2>&1
if errorlevel 1 goto :failed_tests

py -3.11 hardware\g1_arm_bridge\gate7_mink_arm_sdk_offline.py --result-json "%RESULT_JSON%"
if errorlevel 1 goto :failed_integration

echo [PASS] Gate 7 locked offline verification completed.
echo Unit test log: %TEST_LOG%
echo Result saved to: %RESULT_JSON%
pause
exit /b 0

:failed_tests
echo [FAIL] Gate 7 unit tests failed.
echo [ACTION] Keep hardware output locked and inspect the test log.
echo Unit test log: %TEST_LOG%
echo Result path was not created: %RESULT_JSON%
pause
exit /b 2

:failed_integration
echo [FAIL] Gate 7 collision or command-frame verification failed.
echo [ACTION] Do not connect this path to the G1. Inspect the saved result.
echo Unit test log: %TEST_LOG%
echo Result saved to: %RESULT_JSON%
pause
exit /b 3
