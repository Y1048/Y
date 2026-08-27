@echo off
setlocal

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"

echo Verifying the G1 head-camera simulation foundation...
echo.

py -3.11 -m unittest discover -s backend\tests -p "test_*.py"
if errorlevel 1 goto :failed

py -3.11 backend\tools\verify_camera_simulation.py
if errorlevel 1 goto :failed

echo.
echo PASS: camera mount, frame format, reachable inspection scene, and Unitree image transport.
if exist "%PROJECT_ROOT%\logs\camera\g1_head_camera_preview.bmp" start "" "%PROJECT_ROOT%\logs\camera\g1_head_camera_preview.bmp"
pause
exit /b 0

:failed
echo.
echo [FAIL] Camera-foundation validation failed. Do not switch to the physical camera yet.
echo [ACTION] Fix the first failed unittest or verify_camera_simulation message printed above, then rerun this BAT.
pause
exit /b 1
