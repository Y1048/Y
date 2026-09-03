@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "RESULT_JSON=%CD%\logs\test_results\g1_gate7_hardware_virtual_e2e_%STAMP%.json"
set "TEST_LOG=%CD%\logs\test_results\g1_gate7_hardware_virtual_e2e_%STAMP%.log"
if not exist "%CD%\logs\test_results" mkdir "%CD%\logs\test_results"

echo ============================================================
echo G1 GATE 7 VIRTUAL HARDWARE E2E - NO ROBOT OUTPUT
echo   Synthetic Mink ^> UDP 5008 ^> relay ^> UDP 5013
echo   Virtual LowState ^> Gate 7 ^> SDK-neutral frame only
echo ============================================================

netstat -ano -p UDP | findstr /R /C:":5008[ ]" >nul
if not errorlevel 1 (
    echo [ERROR] UDP 5008 is already in use.
    echo [ACTION] Close the old Gate 7 or relay window, then retry.
    goto :failed
)

netstat -ano -p UDP | findstr /R /C:":5013[ ]" >nul
if not errorlevel 1 (
    echo [ERROR] UDP 5013 is already in use.
    echo [ACTION] Close the old virtual or WSL Gate 7 adapter, then retry.
    goto :failed
)

py -3.11 hardware\g1_arm_bridge\gate7_hardware_virtual_e2e.py --result-json "%RESULT_JSON%" > "%TEST_LOG%" 2>&1
if errorlevel 1 goto :failed_with_log

type "%TEST_LOG%"
echo.
echo [PASS] Virtual hardware E2E completed without G1 output.
echo Result saved to: %RESULT_JSON%
echo Test log saved to: %TEST_LOG%
pause
exit /b 0

:failed_with_log
type "%TEST_LOG%"
echo [ACTION] Keep hardware output locked and fix the first reported failure.

:failed
echo.
echo [FAIL] Virtual hardware E2E did not complete.
echo [ACTION] Follow the first ACTION above; no G1 command was sent.
if exist "%TEST_LOG%" echo Test log saved to: %TEST_LOG%
pause
exit /b 2
