@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "TEST_LOG=%CD%\logs\test_results\g1_gate7_capture_replay_%STAMP%.log"
if not exist "%CD%\logs\test_results" mkdir "%CD%\logs\test_results"

echo ============================================================
echo G1 GATE 7 CAPTURE / REPLAY / REGRESSION - OFFLINE
echo   Real localhost UDP sockets, synthetic Mink input
echo   Unitree SDK: NONE / DDS publisher: NONE / Robot command: NONE
echo ============================================================

py -3.11 hardware\g1_arm_bridge\test_gate7_mink_capture_replay.py > "%TEST_LOG%" 2>&1
if errorlevel 1 goto :failed

type "%TEST_LOG%"
echo.
echo [PASS] Capture, replay and deterministic regression tests passed.
echo Test log saved to: %TEST_LOG%
pause
exit /b 0

:failed
type "%TEST_LOG%"
echo.
echo [FAIL] Capture/replay regression test failed.
echo [ACTION] Keep hardware output locked and fix the first error in the log.
echo Test log saved to: %TEST_LOG%
pause
exit /b 2
