@echo off
setlocal

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "CONTROLLER_ROOT=%PROJECT_ROOT%\MuJoCo_G1_Controller"

cd /d "%CONTROLLER_ROOT%"

echo G1 backend isolation diagnostic
echo ===============================
echo Phase A runs completely offline: no Unity, no UDP, no running MuJoCo required.
echo It isolates the 0.08 m/s reference, workspace final step, and pure wrist IK.
echo.

py -3.11 scripts\diagnose_backend_offline.py
set "OFFLINE_EXIT=%ERRORLEVEL%"

echo.
echo ------------------------------------------------------------
echo Phase B is the UDP end-to-end diagnostic.
echo Close Unity Play Mode completely and keep START_VR_HAND_TO_MUJOCO.bat running.
echo ------------------------------------------------------------
echo.

py -3.11 scripts\diagnose_fake_teleop.py
set "UDP_EXIT=%ERRORLEVEL%"

echo.
echo ===============================
echo DIAGNOSTIC SUMMARY
echo ===============================
if "%OFFLINE_EXIT%"=="0" (
    echo OFFLINE BACKEND: PASS
) else (
    echo OFFLINE BACKEND: FAIL ^(exit %OFFLINE_EXIT%^)
)
if "%UDP_EXIT%"=="0" (
    echo UDP END-TO-END: PASS
) else (
    echo UDP END-TO-END: FAIL or SUSPECT ^(exit %UDP_EXIT%^)
)

echo.
echo Interpretation:
echo - Offline IK FAIL = IK/fallback/guard problem, not Unity.
echo - Offline PASS + UDP FAIL = backend protocol/mapping/workspace integration problem.
echo - Offline PASS + UDP PASS + live VR FAIL = Unity/Quest side problem.
echo.
pause

if not "%OFFLINE_EXIT%"=="0" exit /b %OFFLINE_EXIT%
exit /b %UDP_EXIT%
