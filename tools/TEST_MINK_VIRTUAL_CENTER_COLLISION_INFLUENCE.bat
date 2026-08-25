@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ============================================================
echo   G1 Mink Virtual Center Collision Influence - OFFLINE
echo   - No Unity
echo   - No Quest
echo   - No UDP controller
echo   - No robot command
echo ============================================================
echo.

py -3.11 MuJoCo_G1_Controller\scripts\test_mink_virtual_center_collision_influence.py
if errorlevel 1 (
    echo.
    echo [FAIL] Virtual-center collision influence diagnostic failed to run.
    pause
    exit /b 1
)

echo.
echo [PASS] Virtual-center collision influence diagnostic completed.
pause
endlocal
