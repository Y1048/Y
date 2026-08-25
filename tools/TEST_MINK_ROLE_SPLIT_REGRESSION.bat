@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ============================================================
echo   G1 Mink Role-Split Regression - OFFLINE
echo   - No Unity
echo   - No Quest
echo   - No UDP controller
echo   - No robot command
echo ============================================================
echo.

py -3.11 -c "import mujoco, mink, numpy, qpsolvers" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11 Mink/MuJoCo environment is not ready.
    echo         Run: py -3.11 -m pip install mink daqp
    goto :fail
)

echo [RUN] Synthetic wrist rotation regression...
py -3.11 MuJoCo_G1_Controller\scripts\test_mink_role_split_regression.py
set "TEST_RC=%ERRORLEVEL%"

if "%TEST_RC%"=="0" goto :pass
if "%TEST_RC%"=="2" goto :diagnostic

goto :fail

:diagnostic
echo.
echo [DIAGNOSTIC] One or more tuning criteria were not met.
echo              This is not a hardware failure.
echo              Send the printed case results for controller tuning.
goto :end

:pass
echo.
echo [PASS] Offline role-split regression passed.
goto :end

:fail
echo.
echo [FAIL] Regression runner failed to execute cleanly.
exit /b 1

:end
echo.
pause
endlocal
exit /b 0
