@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ============================================================
echo   G1 Mink Virtual Wrist Center - BROAD OFFLINE SWEEP
echo   - No Unity
echo   - No Quest
echo   - No UDP controller
echo   - No robot command
echo ============================================================
echo.
echo [INFO] This runs hundreds of Mink QP cases and may take a few minutes.
echo.

py -3.11 -c "import mujoco, mink, qpsolvers, numpy" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11 Mink/MuJoCo environment is not ready.
    goto :fail
)

py -3.11 MuJoCo_G1_Controller\scripts\test_mink_virtual_wrist_center_sweep.py
if errorlevel 1 goto :fail

echo.
echo [PASS] Broad virtual-wrist-center sweep completed.
goto :end

:fail
echo.
echo [FAIL] Broad virtual-wrist-center sweep did not complete cleanly.
exit /b 1

:end
pause
endlocal
exit /b 0
