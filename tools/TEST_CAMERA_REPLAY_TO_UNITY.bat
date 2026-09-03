@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
title G1 Camera Offline Replay to Unity

set "PROJECT_ROOT=%CD%"
set "UNITY_PROJECT=%PROJECT_ROOT%\Unity_G1_VR"
set "UNITY_EXE=C:\Program Files\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe"
set "REPLAY_SCRIPT=%PROJECT_ROOT%\hardware\g1_arm_bridge\g1_camera_replay_tcp.py"

echo ============================================================
echo   G1 Camera PiP - OFFLINE REPLAY
echo   Synthetic JPEG ^> TCP 127.0.0.1:5011 ^> Unity
echo   Uses NO G1, Unitree SDK, DDS, or robot command
echo ============================================================
echo.

if not exist "%REPLAY_SCRIPT%" (
    echo [ERROR] Offline camera replay script was not found.
    echo [ACTION] Restore hardware\g1_arm_bridge\g1_camera_replay_tcp.py from Git.
    goto :failed
)

if not exist "%UNITY_EXE%" (
    echo [ERROR] Unity 6000.5.4f1 was not found.
    echo [ACTION] Install Unity 6000.5.4f1 or update UNITY_EXE in this BAT.
    goto :failed
)

py -3.11 -c "import PIL" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11 Pillow is not installed.
    echo [ACTION] Run: py -3.11 -m pip install pillow
    goto :failed
)

if /I "%~1"=="--help" (
    py -3.11 "%REPLAY_SCRIPT%" --help
    endlocal & exit /b %ERRORLEVEL%
)

wsl -d Ubuntu -- bash -lc "pgrep -f '[g]1_camera_tcp_bridge.py' >/dev/null" >nul 2>&1
if not errorlevel 1 (
    echo [ERROR] The real G1 camera bridge is still running in WSL.
    echo [ACTION] Close its command window or run: wsl -d Ubuntu -- pkill -f g1_camera_tcp_bridge.py
    goto :failed
)

powershell -NoProfile -Command "$p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue ^| Where-Object { $_.CommandLine -and $_.CommandLine.Contains('g1_camera_replay_tcp.py') -and $_.ProcessId -ne $PID }; if($p){exit 0}else{exit 1}" >nul 2>&1
if not errorlevel 1 (
    echo [ERROR] Another offline camera replay is already running.
    echo [ACTION] Close its command window before starting a second replay.
    goto :failed
)

powershell -NoProfile -Command "$c=Get-NetTCPConnection -LocalPort 5011 -State Established -ErrorAction SilentlyContinue; if($c){exit 0}else{exit 1}" >nul 2>&1
if not errorlevel 1 (
    echo [ERROR] TCP 5011 already has an active camera source.
    echo [ACTION] Close START_G1_CAMERA_TO_UNITY or the previous replay, then retry.
    goto :failed
)

set "UNITY_PROJECT_RUNNING=0"
powershell -NoProfile -Command "$u='%UNITY_PROJECT%'.ToLowerInvariant(); $p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue ^| Where-Object { $_.Name -eq 'Unity.exe' -and $_.CommandLine -and $_.CommandLine.ToLowerInvariant().Contains($u) }; if($p){exit 0}else{exit 1}" >nul 2>&1
if not errorlevel 1 set "UNITY_PROJECT_RUNNING=1"

if "%UNITY_PROJECT_RUNNING%"=="0" (
    echo [START] Unity G1 VR project
    start "G1 VR Unity" "%UNITY_EXE%" -projectPath "%UNITY_PROJECT%"
) else (
    echo [KEEP] Unity G1 VR project is already open.
)

echo.
echo [NEXT]
echo   1. Open Assets\Scenes\SampleScene if needed.
echo   2. Press Play in Unity.
echo   3. Confirm the centered PiP turns green.
echo   4. Confirm OFFLINE REPLAY and a moving green marker are visible.
echo   5. Press Ctrl+C here to finish and save the result JSON.
echo.

py -3.11 "%REPLAY_SCRIPT%" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo [ERROR] Offline camera replay exited with code %RC%.
    echo [ACTION] Read the message above and verify Unity is in Play mode.
)

echo.
echo [INFO] The replay prints its result JSON path before this prompt.
pause
endlocal & exit /b %RC%

:failed
echo.
echo [FAIL] Offline camera replay was not started.
echo [ACTION] Review the error above, start Unity Play mode, and retry the replay.
pause
endlocal & exit /b 1
