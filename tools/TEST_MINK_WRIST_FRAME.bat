@echo off
setlocal
cd /d "%~dp0.."
set "RESULT_DIR=%CD%\logs\test_results"
set "RESULT_PATH=%RESULT_DIR%\mink_wrist_frame.log"
if not exist "%RESULT_DIR%" mkdir "%RESULT_DIR%"

echo ============================================================
echo   G1 Wrist Frame Contract - OFFLINE TEST
echo   - Quest/Unity/MuJoCo/Mink frame consistency
echo   - No Unity launch
echo   - No MuJoCo viewer
echo   - No robot command
echo ============================================================
echo.

py -3.11 MuJoCo_G1_Controller\scripts\test_mink_wrist_frame_contract.py > "%RESULT_PATH%" 2>&1
set RC=%ERRORLEVEL%
type "%RESULT_PATH%"
if not "%RC%"=="0" (
    echo.
    echo [FAIL] Wrist frame contract test failed.
    echo [ACTION] Open %RESULT_PATH% and restore the reported Quest, Unity, or MuJoCo wrist-frame contract mismatch.
    echo [ACTION] Reproduce with: py -3.11 MuJoCo_G1_Controller\scripts\test_mink_wrist_frame_contract.py
    >> "%RESULT_PATH%" echo [ACTION] Fix the reported wrist-frame contract mismatch and rerun this BAT.
) else (
    echo.
    echo [PASS] Wrist frame contract test passed.
)

echo Result saved to: %RESULT_PATH%
echo.
pause
exit /b %RC%
