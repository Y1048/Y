@echo off
setlocal
cd /d "%~dp0.."

set "MODE_JSON=%CD%\logs\runtime\g1_motion_mode_query.json"
set "PRECHECK_JSON=%CD%\logs\runtime\g1_startup_precheck.json"

echo ============================================================
echo   G1 Teleoperation Startup Precheck - READ ONLY
echo   - Queries MotionSwitcher with CheckMode only
echo   - Observes rt/lowstate for one second
echo   - Checks Gate 5 limits, settling, and Mink collision clearance
echo   - Sends NO robot command
echo ============================================================
echo.

if exist "%MODE_JSON%" del /q "%MODE_JSON%"
if exist "%PRECHECK_JSON%" del /q "%PRECHECK_JSON%"

echo [STEP 1/3] Querying the active G1 motion service without changing it...
wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/query_motion_mode_wsl.sh
if errorlevel 1 (
    echo.
    echo [ERROR] The read-only MotionSwitcher CheckMode query failed.
    echo [ACTION] Keep robot commands disabled, verify G1 Ethernet and WSL, then retry.
    echo [ACTION] Details are in %MODE_JSON% when the query reached Python.
    goto :failed
)

echo.
echo [STEP 2/3] Starting the dedicated read-only LowState forwarder...
start "G1 Startup Precheck LowState - READ ONLY" wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_read_only_wsl.sh --timeout 0.25 --forward-host 127.0.0.1 --forward-port 5007 --forward-hz 30
powershell -NoProfile -Command "Start-Sleep -Seconds 2"

echo [STEP 3/3] Evaluating the measured startup state...
py -3.11 hardware\g1_arm_bridge\check_startup_readiness.py --host 0.0.0.0 --port 5007 --motion-mode-json "%MODE_JSON%" --output "%PRECHECK_JSON%"
set "RC=%ERRORLEVEL%"

wsl -d Ubuntu -- bash -lc "pkill -f '[r]ead_only_lowstate.py.*--forward-port 5007' || true" >nul 2>&1

echo.
if "%RC%"=="0" (
    echo [PASS] The measured Regular pose may bypass Startup Recovery.
    echo [INFO] This result does not authorize or send a robot command.
) else if "%RC%"=="10" (
    echo [BLOCKED] Direct teleoperation startup was not authorized.
    echo [ACTION] Follow the reason and action printed above; do not bypass the check.
) else (
    echo [ERROR] The startup precheck could not complete, code %RC%.
    echo [ACTION] Open %PRECHECK_JSON%, fix the reported input or model error, and retry.
)
echo Result saved to: %PRECHECK_JSON%
echo Motion mode query saved to: %MODE_JSON%
echo No robot command was sent.
echo.
pause
exit /b %RC%

:failed
echo.
echo Result path: %PRECHECK_JSON%
echo Motion mode query path: %MODE_JSON%
echo No robot command was sent.
echo.
pause
exit /b 2
