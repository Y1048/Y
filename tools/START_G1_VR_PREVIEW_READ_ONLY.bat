@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
echo ============================================================
echo G1 VR PREVIEW - READ ONLY
echo Actual joints: UDP 5009 to Unity 5010. Camera: TCP 5011.
echo No IK, Gate 7 adapter, or robot motor publisher is started.
echo Stop Unity Play and close previous physical adapters first.
echo ============================================================

rem Refuse to mix this diagnostic with an existing command relay or adapter.
netstat -ano -p UDP | findstr /R /C:":5008[ ]" >nul
if not errorlevel 1 (
    echo [BLOCKED] UDP 5008 is occupied.
    echo [ACTION] Close the previous relay or dry-run window; do not force-kill it.
    goto :failed
)
wsl -d Ubuntu -- bash -lc "command -v pgrep >/dev/null && command -v ss >/dev/null"
if errorlevel 1 goto :failed
wsl -d Ubuntu -- bash -lc "if pgrep -f '[g]ate7_live_arm_sdk|[g]1_right_arm_jog|[g]ate6_arm_sdk_hold' >/dev/null || ss -lun | grep -q ':5013 '; then exit 1; fi"
if errorlevel 1 (
    echo [BLOCKED] A physical adapter may still be running.
    echo [ACTION] Request its normal Ctrl+C release before retrying.
    goto :failed
)

echo [INFO] Use the existing Unity project. Press Play after the mirror starts.
echo [INFO] This only checks the wrist marker and actual pose, not arm control.
wsl -d Ubuntu -- bash -lc "pgrep -f '[g]1_camera_tcp_bridge.py' >/dev/null"
if errorlevel 1 (
    start "G1 Read-only Camera" cmd /k call "%~dp0START_G1_CAMERA_TO_UNITY.bat"
) else (
    echo [KEEP] Existing read-only camera bridge.
)
call "%~dp0VIEW_G1_LIVE_MUJOCO.bat"
set "RC=%ERRORLEVEL%"
echo [INFO] Close the camera window separately when finished.
exit /b %RC%

:failed
echo [ACTION] Check the error above. No physical test was started by this file.
pause
exit /b 2
