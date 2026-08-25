@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ============================================================
echo   G1 Mink Virtual Wrist Center - OFFLINE A/B
echo   - No Unity
echo   - No Quest
echo   - No UDP controller
echo   - No robot command
echo ============================================================
echo.

py -3.11 MuJoCo_G1_Controller\scripts\test_mink_virtual_wrist_center_compare.py
if errorlevel 1 (
    echo.
    echo [ERROR] Virtual wrist center comparison exited with an error.
    goto :end
)

echo.
echo [PASS] Offline A/B comparison completed.

:end
echo.
pause
endlocal
