@echo off
setlocal
cd /d "%~dp0.."

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "TEST_LOG=%CD%\logs\test_results\g1_gate7_live_dry_run_tests_%STAMP%.log"
if not exist "%CD%\logs\test_results" mkdir "%CD%\logs\test_results"

echo ============================================================
echo G1 Gate 7 LIVE DRY RUN - AUTOMATED TEST
echo   - Strict UDP 5008 packet and 35-slot candidate
echo   - No Unitree SDK / DDS entity / publisher / robot command
echo ============================================================

py -3.11 hardware\g1_arm_bridge\gate7_live_dry_run.py --validate-only > "%TEST_LOG%" 2>&1
if errorlevel 1 goto :failed

py -3.11 hardware\g1_arm_bridge\test_gate7_live_dry_run.py >> "%TEST_LOG%" 2>&1
if errorlevel 1 goto :failed

py -3.11 hardware\g1_arm_bridge\test_gate7_live_dry_run_e2e.py >> "%TEST_LOG%" 2>&1
if errorlevel 1 goto :failed

type "%TEST_LOG%"
echo.
echo [PASS] Gate 7 live dry-run validation and UDP E2E tests passed.
echo Test log saved to: %TEST_LOG%
pause
exit /b 0

:failed
type "%TEST_LOG%"
echo.
echo [FAIL] Gate 7 live dry-run test failed.
echo [ACTION] Keep hardware output locked and inspect the first failure in the log.
echo [ACTION] If UDP bind failed, close the process using the reported port and retry.
echo Test log saved to: %TEST_LOG%
pause
exit /b 2
