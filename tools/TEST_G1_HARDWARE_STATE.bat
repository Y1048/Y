@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo   G1 Hardware Runtime State - OFFLINE TEST
echo   - No Unitree SDK
echo   - No DDS publisher
echo   - No robot command
echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\test_hardware_state.py
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
    echo [PASS] Hardware runtime state tests passed.
) else (
    echo [FAIL] Hardware runtime state tests failed with code %RC%.
)

echo.
pause
exit /b %RC%
