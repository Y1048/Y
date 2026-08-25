@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo   G1 Hardware Safety Gate - OFFLINE TESTS ONLY
echo   - No Unitree SDK required
echo   - No DDS publisher
echo   - No robot command

echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\test_safety_gate.py
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
    echo [PASS] Hardware safety gate offline tests passed.
) else (
    echo [FAIL] Hardware safety gate offline tests failed.
)

echo.
pause
exit /b %RC%
