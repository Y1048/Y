@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo   G1 Wrist Frame Contract - OFFLINE TEST
echo   - Quest/Unity/MuJoCo/Mink frame consistency
echo   - No Unity launch
echo   - No MuJoCo viewer
echo   - No robot command
echo ============================================================
echo.

py -3.11 MuJoCo_G1_Controller\scripts\test_mink_wrist_frame_contract.py
if errorlevel 1 (
    echo.
    echo [FAIL] Wrist frame contract test failed.
    exit /b 1
)

echo.
echo [PASS] Wrist frame contract test passed.
exit /b 0
