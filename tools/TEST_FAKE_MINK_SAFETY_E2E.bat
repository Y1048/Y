@echo off
setlocal
cd /d "%~dp0.."
set "RESULT_DIR=%CD%\logs\test_results"
set "RESULT_PATH=%RESULT_DIR%\fake_mink_safety_e2e.log"
if not exist "%RESULT_DIR%" mkdir "%RESULT_DIR%"

echo ============================================================
echo   G1 Fake Mink Safety Pipeline - OFFLINE E2E
echo   - No Unity required
echo   - No MuJoCo required
echo   - No Unitree SDK
echo   - No DDS publisher
echo   - No robot command
echo ============================================================
echo.

py -3.11 hardware\g1_arm_bridge\test_fake_mink_safety_e2e.py > "%RESULT_PATH%" 2>&1
set RC=%ERRORLEVEL%
type "%RESULT_PATH%"

echo.
if "%RC%"=="0" (
    echo [PASS] Fake Mink safety E2E test passed.
) else (
    echo [FAIL] Fake Mink safety E2E test failed with code %RC%.
    echo [ACTION] Open %RESULT_PATH% and inspect the first generator, receiver, or stale-stop failure.
    echo [ACTION] If WinError 10048 appears, close every process using UDP 5008 and rerun this BAT by itself.
    >> "%RESULT_PATH%" echo [ACTION] Fix the first failure; for WinError 10048, free UDP 5008 and rerun this BAT alone.
)

echo Result saved to: %RESULT_PATH%
echo.
pause
exit /b %RC%
