@echo off
setlocal
cd /d "%~dp0.."

set "STATUS_PATH=%CD%\logs\runtime\g1_gate5_lowstate_safety.json"
set "EVENT_PATH=%CD%\logs\runtime\g1_gate5_lowstate_safety.jsonl"

echo ============================================================
echo   G1 Gate 5 - REAL LowState through Safety Gate
echo   - Subscribes only to rt/lowstate in WSL
echo   - Requested HOLD target equals measured pose
echo   - No DDS publisher and no robot command
echo ============================================================
echo.
echo [STEP 1] Starting READ-ONLY LowState UDP forwarder...
start "G1 Gate 5 LowState Forwarder - READ ONLY" wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_read_only_wsl.sh --timeout 0.25 --forward-host 127.0.0.1 --forward-port 5007 --forward-hz 30
timeout /t 2 /nobreak >nul

echo [STEP 2] Starting Gate 5 monitor on UDP 5007...
py -3.11 hardware\g1_arm_bridge\gate5_lowstate_safety_monitor.py --host 0.0.0.0 --port 5007 --status-json "%STATUS_PATH%" --event-log "%EVENT_PATH%"
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
    echo [STOP] Gate 5 was stopped by the operator.
) else (
    echo [FAULT] Gate 5 stopped fail-closed with code %RC%.
    echo [ACTION] Read %STATUS_PATH% and the last entries in %EVENT_PATH% for the fault reason.
    echo [ACTION] Close the READ-ONLY forwarder, run TEST_G1_GATE5_READ_ONLY.bat, then verify Ethernet and LowState before retrying.
)
echo [INFO] Close the separate READ-ONLY forwarder window when finished.
echo Status saved to: %STATUS_PATH%
echo Event log saved to: %EVENT_PATH%
echo No robot command was sent by this launcher.
echo.
pause
exit /b %RC%
