@echo off
setlocal
cd /d "%~dp0..\.."

echo ============================================================
echo G1 Startup Recovery - EXPERIMENTAL SELECTED PATH VIEWER
echo   - Replays only the selected offline result
echo   - Opens no network socket or DDS publisher
echo   - Sends no robot command
echo ============================================================
echo.

py -3.11 experiments\startup_recovery_multistrategy\view_selected.py
set "exit_code=%errorlevel%"

echo.
if not "%exit_code%"=="0" (
    echo [FAIL] The selected experimental path could not be replayed.
    echo [ACTION] Run TEST_MULTI_STRATEGY.bat first and confirm it reports PASS.
) else (
    echo [DONE] Experimental recovery replay closed normally.
)
echo Robot command: NONE
echo.
pause
exit /b %exit_code%
