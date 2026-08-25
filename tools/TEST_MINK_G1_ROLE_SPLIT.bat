@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ============================================================
echo   G1 Mink Role-Split IK Experiment
echo   - Position: shoulder 3 + elbow dominant
echo   - Orientation: wrist roll + pitch + yaw dominant
echo   - Normal proximal orientation assist: 0%%
echo   - Wrist-limit hysteresis escape assist
echo   - No speed mode switching
echo   - No proximal hard freeze
echo ============================================================
echo.

echo [CHECK] UDP 5005 availability...
powershell -NoProfile -Command "$p = Get-NetUDPEndpoint -LocalPort 5005 -ErrorAction SilentlyContinue; if ($p) { Write-Host '[ERROR] UDP 5005 is already in use. Stop the current Mink controller first.' -ForegroundColor Red; $p | Select-Object LocalAddress,LocalPort,OwningProcess | Format-Table; exit 1 }; exit 0"
if errorlevel 1 goto :end

echo [CHECK] Python 3.11 + Mink + DAQP...
py -3.11 -c "import mujoco, mink, qpsolvers; print('[OK] Mink', mink.__version__ if hasattr(mink,'__version__') else 'imported'); print('[OK] QP solvers:', qpsolvers.available_solvers)"
if errorlevel 1 (
    echo [ERROR] Python 3.11 Mink/MuJoCo environment is not ready.
    goto :end
)

echo.
echo [RUN] Role-split Mink controller with wrist-limit hysteresis
py -3.11 MuJoCo_G1_Controller\scripts\run_mink_g1_right_arm_role_split_hysteresis.py
if errorlevel 1 (
    echo.
    echo [ERROR] Role-split Mink controller exited with an error.
)

:end
echo.
pause
endlocal
