@echo off
setlocal
cd /d "%~dp0.."
set "RESULT_DIR=%CD%\logs\test_results"
set "RESULT_PATH=%RESULT_DIR%\mink_safety_pipeline.log"
if not exist "%RESULT_DIR%" mkdir "%RESULT_DIR%"

echo ============================================================
echo   G1 Mink to Hardware Safety Gate - END-TO-END OFFLINE TEST
echo   - No Unity required
echo   - No MuJoCo required
echo   - No Unitree SDK
echo   - No DDS publisher
echo   - No robot command
echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\test_mink_safety_pipeline.py > "%RESULT_PATH%" 2>&1
set RC=%ERRORLEVEL%
type "%RESULT_PATH%"

echo.
if "%RC%"=="0" (
    echo [PASS] Mink safety pipeline offline test passed.
) else (
    echo [FAIL] Mink safety pipeline offline test failed with code %RC%.
    echo [ACTION] Open %RESULT_PATH% and inspect the first traceback or failed assertion.
    echo [ACTION] If WinError 10048 appears, close every process using UDP 5008 and rerun this BAT by itself.
    >> "%RESULT_PATH%" echo [ACTION] Fix the first failure; for WinError 10048, free UDP 5008 and rerun this BAT alone.
)

echo Result saved to: %RESULT_PATH%
echo.
pause
exit /b %RC%
