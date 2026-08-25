@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo   G1 Palm-Center Engagement Patch
echo   - Preserves local binder edits
echo   - Engage UI/alignment: palm center
echo   - Mink/control motion: wrist frame unchanged
echo ============================================================
echo.

py -3.11 tools\apply_palm_center_engagement_patch.py
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
    echo [PASS] Palm-center engagement patch completed.
) else (
    echo [FAIL] Palm-center engagement patch failed with code %RC%.
)

echo.
pause
exit /b %RC%
