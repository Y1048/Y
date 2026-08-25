@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo   G1 Fake Mink Safety Pipeline - OFFLINE E2E
echo   - No Unity required
echo   - No MuJoCo required
echo   - No Unitree SDK
echo   - No DDS publisher
echo   - No robot command
echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\test_fake_mink_safety_e2e.py
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
    echo [PASS] Fake Mink safety E2E test passed.
) else (
    echo [FAIL] Fake Mink safety E2E test failed with code %RC%.
)

echo.
pause
exit /b %RC%
