@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

for /f %%T in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')"') do set "LOWSTATE_TOKEN=%%T"
if not defined LOWSTATE_TOKEN (
    echo [ERROR] Could not create the per-run LowState provenance token.
    exit /b 2
)

echo ============================================================
echo   G1 Mink Right-Arm - Hardware Pose Sync Startup
echo   - Receives READ-ONLY LowState snapshot on UDP 5007
echo   - Seeds Mink from actual G1 right-arm pose
echo   - Sends NO robot motor command
echo ============================================================
echo.

echo [STEP 0] Starting read-only G1 LowState forwarder...
start "G1 LowState Read Only Forwarder" wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_read_only_wsl.sh --forward-host 127.0.0.1 --forward-port 5007 --forward-hz 30 --forward-token %LOWSTATE_TOKEN%
timeout /t 3 /nobreak >nul

echo [STEP 1] Waiting for a fresh provenance-bound G1 LowState snapshot...
py -3.11 hardware\g1_arm_bridge\receive_initial_state.py --port 5007 --timeout 8 --max-packet-age 1.0 --expected-forward-token %LOWSTATE_TOKEN%
set "SYNC_RC=%ERRORLEVEL%"
wsl -d Ubuntu -- bash -lc "pkill -TERM -f '[r]ead_only_lowstate_entry.py.*--forward-token %LOWSTATE_TOKEN%' || true" >nul 2>&1
if not "%SYNC_RC%"=="0" (
    echo.
    echo [ERROR] Hardware pose synchronization failed.
    echo [ACTION] Check the G1 LowState Read Only Forwarder window for a missing 192.168.123.99/24 interface, token mismatch, or LowState timeout.
    echo [ACTION] Close both windows, run START_G1_READ_ONLY.bat successfully, then retry this BAT.
    goto :end
)

echo.
echo [STEP 2] Verifying measured pose through Mink and Unity packet...
set G1_USE_HARDWARE_INITIAL_STATE=1
py -3.11 hardware\g1_arm_bridge\verify_initial_pose_sync.py
if errorlevel 1 (
    echo.
    echo [ERROR] Hardware pose synchronization validation failed.
    echo [ACTION] Inspect logs\runtime\g1_hardware_initial_state.json and run py -3.11 hardware\g1_arm_bridge\verify_initial_pose_sync.py directly.
    echo [ACTION] Do not proceed until all seven right-arm values are finite and match the current G1 pose.
    goto :end
)

echo.
echo [STEP 3] Starting current virtual-center Mink controller...
echo [INFO] Hardware output remains disabled in this process.
py -3.11 MuJoCo_G1_Controller\scripts\run_mink_g1_right_arm_virtual_center_live.py
if errorlevel 1 (
    echo.
    echo [ERROR] Mink hardware-synchronized startup exited with an error.
    echo [ACTION] Run the printed Python command directly and inspect the first traceback or collision failure.
    echo [ACTION] Hardware output is disabled; fix the simulation error before any command integration.
)

:end
echo.
pause
endlocal
