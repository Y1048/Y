@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ============================================================
echo   G1 Virtual Center Yaw Collision Geometry - OFFLINE
echo   - No Unity
echo   - No Quest
echo   - No UDP controller
echo   - No robot command
echo ============================================================
echo.

py -3.11 MuJoCo_G1_Controller\scripts\test_mink_virtual_center_yaw_collision_geometry.py
if errorlevel 1 (
    echo.
    echo [FAIL] Yaw collision geometry diagnostic failed.
    pause
    exit /b 1
)

echo.
echo [PASS] Yaw collision geometry diagnostic completed.
pause
endlocal
