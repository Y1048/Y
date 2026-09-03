@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
for /f %%T in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')"') do set "LOWSTATE_TOKEN=%%T"
set "ADAPTER_STARTED=0"
if not defined LOWSTATE_TOKEN (
    echo [ERROR] Could not create the per-run LowState provenance token.
    goto :failed
)
set "ADAPTER_LOG=%CD%\logs\test_results\g1_gate7_adapter_%STAMP%.log"
set "ADAPTER_READY=%CD%\logs\runtime\g1_gate7_adapter_ready_%STAMP%.json"
set "ADAPTER_READY_WSL=/mnt/c/Users/user/Desktop/G1_Teleop_Project/logs/runtime/g1_gate7_adapter_ready_%STAMP%.json"

set "GATE7_CONFIG=%CD%\config\g1_gate7_mink_arm_sdk.json"
set "HARDWARE_CONFIG=%CD%\config\g1_gate7_live_hardware_output.json"
set "GATE7_CONFIG_WSL=/mnt/c/Users/user/Desktop/G1_Teleop_Project/config/g1_gate7_mink_arm_sdk.json"
set "HARDWARE_CONFIG_WSL=/mnt/c/Users/user/Desktop/G1_Teleop_Project/config/g1_gate7_live_hardware_output.json"
set "HARDWARE_CONFIRM=ENABLE_G1_GATE7_LIVE_ARM_SDK"
set "PROFILE_NAME=standard"
if /I "%~1"=="--first-live" (
    set "GATE7_CONFIG=%CD%\config\g1_gate7_first_live_mink_arm_sdk.json"
    set "HARDWARE_CONFIG=%CD%\config\g1_gate7_first_live_hardware_output.json"
    set "GATE7_CONFIG_WSL=/mnt/c/Users/user/Desktop/G1_Teleop_Project/config/g1_gate7_first_live_mink_arm_sdk.json"
    set "HARDWARE_CONFIG_WSL=/mnt/c/Users/user/Desktop/G1_Teleop_Project/config/g1_gate7_first_live_hardware_output.json"
    set "HARDWARE_CONFIRM=ENABLE_G1_GATE7_FIRST_LIVE_TRIAL"
    set "PROFILE_NAME=first-live trial"
)
if /I "%~1"=="--visible-ten" (
    set "GATE7_CONFIG=%CD%\config\g1_gate7_visible_motion_mink_arm_sdk.json"
    set "HARDWARE_CONFIG=%CD%\config\g1_gate7_visible_motion_hardware_output.json"
    set "GATE7_CONFIG_WSL=/mnt/c/Users/user/Desktop/G1_Teleop_Project/config/g1_gate7_visible_motion_mink_arm_sdk.json"
    set "HARDWARE_CONFIG_WSL=/mnt/c/Users/user/Desktop/G1_Teleop_Project/config/g1_gate7_visible_motion_hardware_output.json"
    set "HARDWARE_CONFIRM=ENABLE_G1_GATE7_VISIBLE_MOTION_TRIAL"
    set "PROFILE_NAME=10-degree visible-motion trial"
)
set "MODE_JSON=%CD%\logs\runtime\g1_motion_mode_query.json"
set "PRECHECK_JSON=%CD%\logs\runtime\g1_startup_precheck.json"

title G1 Gate 7 Live Hardware

echo ============================================================
echo G1 GATE 7 LIVE HARDWARE - rt/arm_sdk
echo   Unity/Mink UDP 5008 ^> validated relay ^> WSL UDP 5013
echo   WSL Gate 7 + direct rt/lowstate ^> rt/arm_sdk
echo   Profile: %PROFILE_NAME%
echo ============================================================
echo [SAFETY] This path is locked until the bounded shoulder trial is accepted.
echo [SAFETY] G1 must be grounded in Regular Mode with L2+B ready.
echo.

for /f %%A in ('py -3.11 -c "import json; print(str(json.load(open(r'%HARDWARE_CONFIG%', encoding='utf-8'))['hardware_output_authorized']).lower())"') do set "AUTHORIZED=%%A"
if /I not "%AUTHORIZED%"=="true" (
    echo [BLOCKED] %HARDWARE_CONFIG% keeps hardware_output_authorized=false.
    echo [ACTION] Review this exact profile and obtain explicit approval before unlocking it.
    echo [ACTION] Do not bypass this lock merely to test the launcher.
    goto :failed
)

wsl -d Ubuntu -- /home/user/.venvs/g1-teleop/bin/python -c "import importlib.metadata as m, mujoco, ruckig, mink, qpsolvers, daqp; assert mujoco.__version__ == '3.11.0'; assert ruckig.__version__ == '0.19.4'; assert m.version('mink') == '1.3.0'; assert m.version('qpsolvers') == '4.13.0'; assert m.version('daqp') == '0.9.1'" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] A pinned WSL Gate 7 dependency is missing or has the wrong version.
    echo [ACTION] Restore MuJoCo 3.11.0, Ruckig 0.19.4, Mink 1.3.0,
    echo [ACTION] qpsolvers 4.13.0 and DAQP 0.9.1 in /home/user/.venvs/g1-teleop.
    goto :failed
)

wsl -d Ubuntu -- bash -lc "ss -lun | grep -q ':5013 '"
if not errorlevel 1 (
    echo [ERROR] WSL UDP 5013 is already in use.
    echo [ACTION] Close the old Gate 7 hardware adapter window, then retry.
    goto :failed
)

rem A successful one-run wrapper exits while its relay window can remain open.
rem Only remove that exact stale relay after proving no WSL hardware adapter is
rem listening. Never terminate an unknown owner of UDP 5008.
for /f %%P in ('powershell -NoProfile -Command "$e=Get-NetUDPEndpoint -LocalPort 5008 -ErrorAction SilentlyContinue ^| Select-Object -First 1; if($e){$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$e.OwningProcess); if($p.CommandLine -match 'gate7_mink_wsl_relay\.py'){Write-Output $e.OwningProcess}else{Write-Output 0}}"') do set "UDP5008_OWNER=%%P"
if defined UDP5008_OWNER if not "%UDP5008_OWNER%"=="0" (
    echo [CLEANUP] Closing stale Gate 7 relay on Windows UDP 5008 ^(PID %UDP5008_OWNER%^).
    powershell -NoProfile -Command "Stop-Process -Id %UDP5008_OWNER% -Force -ErrorAction Stop"
    timeout /t 1 /nobreak >nul
)
netstat -ano -p UDP | findstr /R /C:":5008[ ]" >nul
if not errorlevel 1 (
    echo [ERROR] Windows UDP 5008 is used by an unknown or active process.
    echo [ACTION] Identify the owner; do not let this launcher terminate it automatically.
    goto :failed
)

echo [STEP 1/5] Validating locked contracts...
py -3.11 hardware\g1_arm_bridge\gate7_live_arm_sdk.py --validate-only --gate7-config "%GATE7_CONFIG%" --hardware-config "%HARDWARE_CONFIG%"
if errorlevel 1 (
    echo [ERROR] Gate 7 live hardware contract validation failed.
    echo [ACTION] Run tools\TEST_G1_GATE7_HARDWARE_FOUNDATION_OFFLINE.bat and fix its first error.
    goto :failed
)

echo [STEP 2/5] Querying MotionSwitcher without changing it...
if exist "%MODE_JSON%" del /q "%MODE_JSON%"
if exist "%PRECHECK_JSON%" del /q "%PRECHECK_JSON%"
wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/query_motion_mode_wsl.sh
if errorlevel 1 (
    echo [ERROR] MotionSwitcher CheckMode failed.
    echo [ACTION] Verify G1 power, Ethernet, WSL and Regular Mode.
    goto :failed
)

echo [STEP 3/5] Creating a fresh provenance-bound read-only startup precheck...
start "G1 Gate 7 Precheck LowState - READ ONLY" wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_read_only_wsl.sh --timeout 0.25 --forward-host 127.0.0.1 --forward-port 5007 --forward-hz 100 --forward-token %LOWSTATE_TOKEN%
timeout /t 2 /nobreak >nul
py -3.11 hardware\g1_arm_bridge\check_startup_readiness_entry.py --host 0.0.0.0 --port 5007 --motion-mode-json "%MODE_JSON%" --output "%PRECHECK_JSON%" --expected-forward-token %LOWSTATE_TOKEN%
set "PRECHECK_RC=%ERRORLEVEL%"
wsl -d Ubuntu -- bash -lc "pkill -TERM -f '[r]ead_only_lowstate_entry.py.*--forward-token %LOWSTATE_TOKEN%' || true" >nul 2>&1
if not "%PRECHECK_RC%"=="0" (
    echo [ERROR] Startup precheck did not return DIRECT_TELEOP_READY.
    echo [ACTION] Read %PRECHECK_JSON% and do not bypass its reason.
    goto :failed
)

echo.
echo [STEP 4/5] Explicit physical-output confirmation
echo [CONFIRM] G1 is grounded in Regular Mode, the area is clear,
echo [CONFIRM] and the handheld remote is ready for L2+B emergency stop.
choice /C YN /N /M "Start Gate 7 live physical output? [Y/N]: "
if errorlevel 2 (
    echo [BLOCKED] Physical output was cancelled by the operator.
    echo [ACTION] Leave output disabled and retry only when all conditions are true.
    goto :failed
)

rem WSL mirrored networking reports more than one host address. Select the
rem source address of the actual G1 Ethernet route instead of hostname -I[0].
for /f "delims=" %%I in ('powershell -NoProfile -Command "$r=(wsl -d Ubuntu -- ip -4 route get 192.168.123.164 | Out-String); if($r -match '\bsrc\s+([0-9.]+)'){$Matches[1]}"') do set "WSL_GATE7_HOST=%%I"
if not defined WSL_GATE7_HOST (
    echo [ERROR] Could not determine the WSL source IP for G1 192.168.123.164.
    echo [ACTION] Verify G1 Ethernet and run: wsl -d Ubuntu -- ip -4 route get 192.168.123.164
    goto :failed
)
echo [NETWORK] Windows relay target selected from G1 route: %WSL_GATE7_HOST%:5013

echo [STEP 5/5] Starting validated relay, Unity/Mink, then WSL adapter...
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\tools\SET_UNITY_DISPLAY_MODE.ps1" -Mode hardware
if errorlevel 1 (
    echo [ERROR] Could not select hardware-only Unity display.
    echo [ACTION] Stop Unity Play and correct local display configuration before retrying.
    goto :failed
)
start "G1 Gate 7 Mink Relay" cmd /k py -3.11 hardware\g1_arm_bridge\gate7_mink_wsl_relay.py --target-host %WSL_GATE7_HOST% --target-port 5013
timeout /t 2 /nobreak >nul
netstat -ano -p UDP | findstr /R /C:":5008[ ]" >nul
if errorlevel 1 (
    echo [ERROR] The validated relay did not bind Windows UDP 5008.
    echo [ACTION] Stop the WSL adapter with Ctrl+C and read the relay window.
    goto :failed
)

start "G1 VR and Mink" cmd /c call "%CD%\START_VR_HAND_TO_MUJOCO.bat" --hardware-display
timeout /t 2 /nobreak >nul

if exist "%ADAPTER_READY%" del /q "%ADAPTER_READY%"
start "G1 Gate 7 rt-arm-sdk PHYSICAL" wsl -d Ubuntu -- env G1_GATE7_ADAPTER_LOG=/mnt/c/Users/user/Desktop/G1_Teleop_Project/logs/test_results/g1_gate7_adapter_%STAMP%.log bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_gate7_live_arm_sdk_wsl.sh --gate7-config %GATE7_CONFIG_WSL% --hardware-config %HARDWARE_CONFIG_WSL% --ready-file %ADAPTER_READY_WSL% --enable-hardware-output --confirm %HARDWARE_CONFIRM% --confirm-grounded-regular G1_IS_GROUNDED_IN_REGULAR_MODE
set "ADAPTER_STARTED=1"
echo [INFO] WSL adapter log: %ADAPTER_LOG%
echo [WAIT] Waiting up to 20 seconds for WSL validation and UDP 5013 bind...
timeout /t 1 /nobreak >nul
for /L %%S in (1,1,20) do (
    if exist "%ADAPTER_READY%" goto :adapter_ready
    timeout /t 1 /nobreak >nul
)
echo [ERROR] The WSL Gate 7 adapter did not bind UDP 5013 within 20 seconds.
echo [ACTION] Read the separate adapter window and fix its first error.
goto :failed

:adapter_ready
echo [PASS] The WSL Gate 7 adapter reported UDP 5013 ready.
echo [INFO] Ready evidence: %ADAPTER_READY%

echo [READY] Press Play in Unity. The adapter waits up to 120 seconds for a
echo [READY] valid relayed Mink packet before it can create a publisher.
set "RC=0"
echo.
echo [INFO] Stop Gate 7 with Ctrl+C in the WSL adapter window.
echo [INFO] It ramps Arm SDK weight to zero and sends repeated zero frames.
echo [INFO] Then close the relay window.
if /I "%~1"=="--first-live" exit /b %RC%
if /I "%~1"=="--visible-ten" exit /b %RC%
pause
exit /b %RC%

:failed
if "%ADAPTER_STARTED%"=="1" (
    echo [SAFETY] Requesting this Gate 7 adapter to stop and zero-weight release...
    wsl -d Ubuntu -- bash -lc "pkill -TERM -f '[g]ate7_live_arm_sdk_entry.py.*--ready-file %ADAPTER_READY_WSL%' || true" >nul 2>&1
    timeout /t 3 /nobreak >nul
)
echo.
echo [FAIL] Gate 7 live physical path did not reach normal operation.
echo [ACTION] Follow the first ACTION above and keep physical output disabled.
pause
exit /b 1
