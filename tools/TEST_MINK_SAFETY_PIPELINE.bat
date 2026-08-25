@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo   G1 Mink to Hardware Safety Gate - END-TO-END OFFLINE TEST
echo   - No Unity required
echo   - No MuJoCo required
echo   - No Unitree SDK
echo   - No DDS publisher
echo   - No robot command
echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\test_mink_safety_pipeline.py
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
    echo [PASS] Mink safety pipeline offline test passed.
) else (
    echo [FAIL] Mink safety pipeline offline test failed with code %RC%.
)

echo.
pause
exit /b %RC%
