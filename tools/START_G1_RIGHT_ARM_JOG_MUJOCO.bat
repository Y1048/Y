@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "MODE_JSON=%CD%\logs\runtime\g1_motion_mode_query.json"
set "PRECHECK_JSON=%CD%\logs\runtime\g1_startup_precheck.json"
set "PATH_PERMIT_JSON=%CD%\logs\runtime\g1_right_arm_jog_path_permit.json"
for /f %%T in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')"') do set "LOWSTATE_TOKEN=%%T"
if not defined LOWSTATE_TOKEN (
    echo [ERROR] Could not create the per-run LowState provenance token.
    goto :failed
)

title G1 Right Arm 7-DoF Jog + Live MuJoCo

echo ============================================================
echo G1 RIGHT ARM 7-DOF JOG - PHYSICAL rt/arm_sdk OUTPUT
echo   During the run: 1-7 select joint, Up/Down move in 1 degree steps
echo   Q: smooth release to zero Arm SDK weight
echo   Actual rt/lowstate: mirrored to MuJoCo
echo ============================================================
echo [LIMIT] Collision-safe directional range within +/-20 degrees
echo [LIMIT] Target velocity: shoulder/elbow 2.5 deg/s, wrist 5 deg/s
echo [LIMIT] New key input is blocked when its target would lead measured by over 2 deg
echo [LIMIT] Maximum Arm SDK weight: 0.25
echo [LIMIT] Maximum active duration: 30 seconds
echo [LIMIT] Select the first joint within 15 seconds; waiting weight stays zero
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

echo [STEP 1/5] Running the offline command-contract test...
py -3.11 hardware\g1_arm_bridge\g1_right_arm_jog.py --validate-only
if errorlevel 1 (
    echo [ERROR] Right-arm jog config validation failed.
    echo [ACTION] Run tools\TEST_G1_RIGHT_ARM_JOG_OFFLINE.bat and fix its first failure.
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

echo [STEP 3/5] Running a fresh provenance-bound read-only startup precheck...
start "G1 Arm Jog Precheck LowState - READ ONLY" wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_read_only_wsl.sh --timeout 0.25 --forward-host 127.0.0.1 --forward-port 5007 --forward-hz 100 --forward-token %LOWSTATE_TOKEN%
timeout /t 2 /nobreak >nul
py -3.11 hardware\g1_arm_bridge\check_startup_readiness_entry.py --host 0.0.0.0 --port 5007 --motion-mode-json "%MODE_JSON%" --output "%PRECHECK_JSON%" --expected-forward-token %LOWSTATE_TOKEN%
set "PRECHECK_RC=%ERRORLEVEL%"
wsl -d Ubuntu -- bash -lc "pkill -TERM -f '[r]ead_only_lowstate_entry.py.*--forward-token %LOWSTATE_TOKEN%' || true" >nul 2>&1
if not "%PRECHECK_RC%"=="0" (
    echo [ERROR] Startup precheck did not authorize DIRECT_TELEOP_READY.
    echo [ACTION] Read %PRECHECK_JSON% and do not bypass its reason.
    goto :failed
)

echo [STEP 3B/5] Computing pose-bound directional limits for all 7 joints...
py -3.11 hardware\g1_arm_bridge\validate_right_arm_jog_collision_path_entry.py --precheck-json "%PRECHECK_JSON%" --output "%PATH_PERMIT_JSON%"
if errorlevel 1 (
    echo [ERROR] A provenance-bound right-arm Jog permit could not be created.
    echo [ACTION] Read %PATH_PERMIT_JSON% and do not bypass it.
    goto :failed
)

echo [STEP 4/5] Starting actual LowState MuJoCo mirror...
start "G1 Actual LowState MuJoCo Mirror" cmd /c call "%CD%\tools\VIEW_G1_LIVE_MUJOCO.bat"
powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(15); do { if (Get-NetUDPEndpoint -LocalPort 5009 -ErrorAction SilentlyContinue) { exit 0 }; Start-Sleep -Milliseconds 250 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo [ERROR] The live MuJoCo mirror did not bind UDP 5009.
    echo [ACTION] Read the separate viewer window; the nested launcher may still be loading or may have printed its first error.
    goto :failed
)
echo [PASS] The live MuJoCo mirror is listening on UDP 5009.

echo.
echo [STEP 5/5] Explicit physical-output confirmation
echo [CONFIRM] G1 is grounded in Regular Mode, the area is clear,
echo [CONFIRM] and the handheld remote is ready for L2+B emergency stop.
choice /C YN /N /M "Start the bounded physical interactive right-arm jog? [Y/N]: "
if errorlevel 2 (
    echo [BLOCKED] Physical output was cancelled by the operator.
    echo [ACTION] Leave output disabled; retry only after all displayed conditions are true.
    goto :failed
)

echo.
echo [ACTIVE NEXT] Focus this window. Use 1-7 to select, Up/Down slowly, Q to release.
wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_right_arm_jog_wsl.sh --path-permit-json /mnt/c/Users/user/Desktop/G1_Teleop_Project/logs/runtime/g1_right_arm_jog_path_permit.json --enable-hardware-output --confirm ENABLE_G1_RIGHT_ARM_JOG --confirm-grounded-regular G1_IS_GROUNDED_IN_REGULAR_MODE
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
    echo [PASS] The right-arm jog stopped after returning Arm SDK weight to zero.
) else (
    echo [FAULT] The right-arm jog exited with code %RC%.
    echo [ACTION] Keep the remote ready, confirm the arm is stable, and read the printed result JSON.
)
echo [INFO] Close the separate MuJoCo viewer when finished.
pause
exit /b %RC%

:failed
echo.
echo [FAIL] Physical right-arm jog was not started.
echo [INFO] No rt/arm_sdk publisher was created by this launcher path.
echo [ACTION] Follow the first ACTION above, close any viewer window, and retry only after correction.
pause
exit /b 1
