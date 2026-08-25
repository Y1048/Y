@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ============================================================
echo   G1 Mink Collision Influence - OFFLINE
echo   - Current yaw-link role split
echo   - Collision ON vs OFF
echo   - No Unity / Quest / UDP / robot command
echo ============================================================
echo.

py -3.11 MuJoCo_G1_Controller\scripts\test_mink_collision_influence.py
if errorlevel 1 (
    echo.
    echo [ERROR] Collision influence diagnostic failed.
    goto :end
)

echo.
echo [PASS] Collision influence diagnostic completed.

:end
echo.
pause
endlocal
