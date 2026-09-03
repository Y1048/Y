@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo   G1 Full 29-Joint - Live MuJoCo + Unity Mirror [READ ONLY]
echo   rt/lowstate + rt/odommodestate ^> WSL SDK2/DDS
echo   ^> UDP 5009 ^> MuJoCo full body + relative base pose
echo   validated state ^> UDP 5010 ^> Unity hardware preview
echo   Sends NO robot motor command
echo ============================================================
echo.

echo [INFO] Put Unity in Play mode to mirror the same 29-joint state on UDP 5010.
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\tools\SET_UNITY_DISPLAY_MODE.ps1" -Mode hardware
if errorlevel 1 (
    echo [ERROR] Could not select hardware-only Unity display.
    echo [ACTION] Stop Unity Play and check local logs\runtime write access.
    pause
    exit /b 2
)
echo.

echo [STEP 1] Starting the read-only joint/base-state forwarder...
start "G1 Live LowState Forwarder" wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_read_only_wsl.sh --forward-host 127.0.0.1 --forward-port 5009 --forward-hz 30 --record-jsonl auto
timeout /t 3 /nobreak >nul

echo [STEP 2] Starting the continuously updated MuJoCo Viewer...
py -3.11 hardware\g1_arm_bridge\live_lowstate_mujoco.py --port 5009 --unity-host 127.0.0.1 --unity-port 5010 --measurement-log auto
set viewer_exit=%errorlevel%
wsl -d Ubuntu -- bash -lc "pkill -f '[r]ead_only_lowstate.py.*--forward-port 5009' || true" >nul 2>&1
if not "%viewer_exit%"=="0" (
    echo.
    echo [ERROR] The live MuJoCo mirror stopped with an error.
    echo [ACTION] Check the forwarder window for a missing 192.168.123.99/24 interface or rt/lowstate timeout.
    echo [ACTION] Base motion additionally requires the read-only rt/odommodestate topic.
    echo [ACTION] If packets are sent but not received, run tools\ALLOW_G1_LOWSTATE_TO_WINDOWS.bat once and retry.
)

echo.
echo [INFO] The dedicated UDP 5009 forwarder has been stopped.
echo [INFO] The forwarder window prints the exact telemetry JSONL result path.
pause
endlocal
