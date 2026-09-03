@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "CONFIG=%CD%\config\g1_right_shoulder_pitch_full_authority_trial.json"
set "MODE_JSON=%CD%\logs\runtime\g1_motion_mode_query.json"
set "PRECHECK_JSON=%CD%\logs\runtime\g1_startup_precheck.json"
set "PATH_PERMIT_JSON=%CD%\logs\runtime\g1_shoulder_pitch_full_authority_permit.json"

title G1 Shoulder Pitch Full Authority Trial

echo ============================================================
echo G1 RIGHT SHOULDER PITCH - FULL ARM SDK AUTHORITY TRIAL
echo   1: arm the right shoulder-pitch trial
echo   Up/Down: move within +/-1 degree after ARMING completes
echo   Q: smooth release to zero Arm SDK weight
echo   Actual rt/lowstate: mirrored to MuJoCo
echo ============================================================
echo [LIMIT] Arm SDK weight ramps from 0 to 1 over 5 seconds.
echo [LIMIT] All 14 measured arm targets are fixed during authority transfer.
echo [LIMIT] Input remains blocked until full weight and <=1.5 degree arm error.
echo [LIMIT] Right shoulder pitch only, +/-1 degree, 1 deg/s, 15 seconds.
echo [SAFETY] G1 must stand on level ground in Regular Mode.
echo [SAFETY] Keep the handheld remote ready for L2+B emergency stop.
echo.

netstat -ano -p UDP | findstr /R /C:":5007[ ]" >nul
if not errorlevel 1 (
    echo [ERROR] UDP 5007 is already in use.
    echo [ACTION] Close the old startup/Gate monitor and retry.
    goto :failed
)

netstat -ano -p UDP | findstr /R /C:":5009[ ]" >nul
if not errorlevel 1 (
    echo [ERROR] UDP 5009 is already in use.
    echo [ACTION] Close the old live MuJoCo viewer and retry.
    goto :failed
)

echo [STEP 1/5] Validating the locked full-authority trial contract...
py -3.11 hardware\g1_arm_bridge\g1_right_arm_jog.py --config "%CONFIG%" --validate-only
if errorlevel 1 (
    echo [ERROR] Full-authority trial config validation failed.
    echo [ACTION] Run tools\TEST_G1_SHOULDER_PITCH_FULL_AUTHORITY_OFFLINE.bat.
    goto :failed
)

echo [STEP 2/5] Querying G1 MotionSwitcher without changing it...
if exist "%MODE_JSON%" del /q "%MODE_JSON%"
if exist "%PRECHECK_JSON%" del /q "%PRECHECK_JSON%"
if exist "%PATH_PERMIT_JSON%" del /q "%PATH_PERMIT_JSON%"
wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/query_motion_mode_wsl.sh
if errorlevel 1 (
    echo [ERROR] MotionSwitcher CheckMode failed.
    echo [ACTION] Verify G1 power, Ethernet, WSL and Regular Mode.
    goto :failed
)

echo [STEP 3/5] Running a fresh read-only startup precheck...
start "G1 Full Authority Precheck - READ ONLY" wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_read_only_wsl.sh --timeout 0.25 --forward-host 127.0.0.1 --forward-port 5007 --forward-hz 100
timeout /t 2 /nobreak >nul
py -3.11 hardware\g1_arm_bridge\check_startup_readiness.py --host 0.0.0.0 --port 5007 --motion-mode-json "%MODE_JSON%" --output "%PRECHECK_JSON%"
set "PRECHECK_RC=%ERRORLEVEL%"
wsl -d Ubuntu -- bash -lc "pkill -f '[r]ead_only_lowstate.py.*--forward-port 5007' || true" >nul 2>&1
if not "%PRECHECK_RC%"=="0" (
    echo [ERROR] Startup precheck did not authorize DIRECT_TELEOP_READY.
    echo [ACTION] Read %PRECHECK_JSON% and do not bypass its reason.
    goto :failed
)

echo [STEP 3B/5] Checking the +/-1 degree shoulder-pitch path in MuJoCo...
py -3.11 hardware\g1_arm_bridge\validate_right_arm_jog_collision_path.py --config "%CONFIG%" --precheck-json "%PRECHECK_JSON%" --output "%PATH_PERMIT_JSON%"
if errorlevel 1 (
    echo [ERROR] The pose-bound shoulder-pitch permit was not created.
    echo [ACTION] Read %PATH_PERMIT_JSON% and do not bypass it.
    goto :failed
)

echo [STEP 4/5] Starting actual LowState MuJoCo mirror...
start "G1 Actual LowState MuJoCo Mirror" cmd /c call "%CD%\tools\VIEW_G1_LIVE_MUJOCO.bat"
powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(15); do { if (Get-NetUDPEndpoint -LocalPort 5009 -ErrorAction SilentlyContinue) { exit 0 }; Start-Sleep -Milliseconds 250 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo [ERROR] The live MuJoCo mirror did not bind UDP 5009.
    echo [ACTION] Read the separate viewer window and fix its first error.
    goto :failed
)
echo [PASS] The live MuJoCo mirror is listening on UDP 5009.

echo.
echo [STEP 5/5] Explicit physical-output confirmation
echo [CONFIRM] G1 is grounded in Regular Mode, the area is clear,
echo [CONFIRM] and the handheld remote is ready for L2+B emergency stop.
choice /C YN /N /M "Start the full-authority shoulder-pitch trial? [Y/N]: "
if errorlevel 2 (
    echo [BLOCKED] Physical output was cancelled by the operator.
    echo [ACTION] Leave output disabled and retry only after all displayed conditions are true.
    goto :failed
)

echo.
echo [ACTIVE NEXT] Press 1 once. Wait for [ARMED], then use Up/Down once at a time.
wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_right_arm_jog_wsl.sh --config /mnt/c/Users/user/Desktop/G1_Teleop_Project/config/g1_right_shoulder_pitch_full_authority_trial.json --path-permit-json /mnt/c/Users/user/Desktop/G1_Teleop_Project/logs/runtime/g1_shoulder_pitch_full_authority_permit.json --enable-hardware-output --confirm ENABLE_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL --confirm-grounded-regular G1_IS_GROUNDED_IN_REGULAR_MODE
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
    echo [PASS] Full-authority trial ended after returning Arm SDK weight to zero.
) else (
    echo [FAULT] Full-authority trial exited with code %RC%.
    echo [ACTION] Keep the remote ready and read the printed result JSON.
)
echo [INFO] Close the separate MuJoCo viewer when finished.
pause
exit /b %RC%

:failed
echo.
echo [FAIL] Full-authority physical trial was not started.
echo [INFO] No rt/arm_sdk publisher was created before all five checks passed.
echo [ACTION] Follow the first ACTION above and retry only after correction.
pause
exit /b 1
