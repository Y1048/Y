@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "RESULT_JSON=%CD%\logs\test_results\g1_gate7_fault_matrix_%STAMP%.json"
set "TEST_LOG=%CD%\logs\test_results\g1_gate7_fault_matrix_%STAMP%.log"
if not exist "%CD%\logs\test_results" mkdir "%CD%\logs\test_results"

echo ============================================================
echo G1 GATE 7 FAULT-INJECTION MATRIX - NO ROBOT OUTPUT
echo   Packet gap / tracking / workspace / collision / order
echo   LowState stale / 10-second fail-safe Regular return
echo ============================================================

py -3.11 hardware\g1_arm_bridge\gate7_fault_injection_matrix.py --result-json "%RESULT_JSON%" > "%TEST_LOG%" 2>&1
if errorlevel 1 goto :failed

type "%TEST_LOG%"
echo.
echo [PASS] All Gate 7 fault-injection scenarios passed.
echo Result saved to: %RESULT_JSON%
echo Test log saved to: %TEST_LOG%
pause
exit /b 0

:failed
type "%TEST_LOG%"
echo.
echo [FAIL] Gate 7 fault-injection matrix failed.
echo [ACTION] Keep hardware output locked and fix the first failed scenario.
echo Result saved to: %RESULT_JSON%
echo Test log saved to: %TEST_LOG%
pause
exit /b 2
