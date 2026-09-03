@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo   G1 Saved 29-Joint Pose - OFFLINE MuJoCo + Unity Replay
echo   Saved JSON ^> UDP 5009 ^> MuJoCo
echo   validated state ^> UDP 5010 ^> Unity hardware preview
echo   Requires no G1, Ethernet, WSL, DDS, or VR
echo   Sends NO robot motor command
echo ============================================================
echo.

echo [INFO] Put Unity in Play mode to show the replayed 29-joint pose on UDP 5010.
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\tools\SET_UNITY_DISPLAY_MODE.ps1" -Mode recorded
if errorlevel 1 (
    echo [ERROR] Could not select recorded-state Unity display.
    echo [ACTION] Stop Unity Play and check local logs\runtime write access.
    pause
    exit /b 2
)
echo.

py -3.11 hardware\g1_arm_bridge\replay_saved_lowstate_mujoco.py --unity-host 127.0.0.1 --unity-port 5010
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo [ERROR] Saved-pose MuJoCo replay failed with code %RC%.
    echo [ACTION] Read the first ERROR/ACTION line above.
    echo [ACTION] If the snapshot is incomplete, reconnect G1 later and run START_G1_READ_ONLY.bat once.
)

echo.
pause
exit /b %RC%
