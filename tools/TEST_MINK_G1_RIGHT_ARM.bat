@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo   G1 Mink Right-Arm IK Prototype
echo   - Uses Unity UDP 5005 input
echo   - Does NOT replace START_VR_HAND_TO_MUJOCO.bat
echo ============================================================
echo.

echo [CHECK] UDP 5005 availability...
powershell -NoProfile -Command "$p = Get-NetUDPEndpoint -LocalPort 5005 -ErrorAction SilentlyContinue; if ($p) { Write-Host '[ERROR] UDP 5005 is already in use. Stop the production controller first.' -ForegroundColor Red; $p | Select-Object LocalAddress,LocalPort,OwningProcess | Format-Table; exit 1 }; exit 0"
if errorlevel 1 goto :end

echo [CHECK] Python 3.11 + MuJoCo...
py -3.11 -c "import mujoco; print('[OK] MuJoCo', mujoco.__version__)"
if errorlevel 1 (
    echo [ERROR] Python 3.11 MuJoCo environment is not available.
    goto :end
)

echo [CHECK] Mink + qpsolvers...
py -3.11 -c "import mink, qpsolvers; print('[OK] Mink import'); print('[OK] QP solvers:', qpsolvers.available_solvers)"
if errorlevel 1 (
    echo [INFO] Mink/DAQP is not installed for Python 3.11.
    echo [INFO] Installing: mink daqp
    py -3.11 -m pip install mink daqp
    if errorlevel 1 (
        echo [ERROR] Mink installation failed.
        goto :end
    )
)

echo.
echo [RUN] Mink G1 right-arm prototype
py -3.11 MuJoCo_G1_Controller\scripts\run_mink_g1_right_arm_prototype.py
if errorlevel 1 (
    echo.
    echo [ERROR] Mink prototype exited with an error.
)

:end
echo.
pause
endlocal
