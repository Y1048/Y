@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "CONFIG=%CD%\config\g1_gate6_interrupt_release_test.json"
set "MODE_JSON=%CD%\logs\runtime\g1_motion_mode_query.json"
set "PRECHECK_JSON=%CD%\logs\runtime\g1_startup_precheck.json"
set "STATUS_JSON=%CD%\logs\runtime\g1_gate6_interrupt_release_test.json"
set "EVENT_LOG=%CD%\logs\runtime\g1_gate6_interrupt_release_test.jsonl"

title G1 Gate 6 Interruption Release Test
echo ============================================================
echo G1 GATE 6 INTERRUPTION / CONTROL-RETURN TEST - PHYSICAL
echo   Holds the measured dual-arm pose at Arm SDK weight 0.2
echo   Ctrl+C requests a 2 s weight release plus 25 zero frames
echo ============================================================
echo [SAFETY] This launcher is intentionally locked by default.
echo [SAFETY] G1 must be grounded in Regular Mode, area clear, L2+B ready.
echo [SAFETY] No other arm or waist command publisher may be running.
echo.

for /f %%A in ('py -3.11 -c "import json; print(str(json.load(open(r'%CONFIG%', encoding='utf-8'))['hardware_output_authorized']).lower())"') do set "AUTHORIZED=%%A"
if /I not "%AUTHORIZED%"=="true" (
    echo [BLOCKED] config\g1_gate6_interrupt_release_test.json keeps hardware_output_authorized=false.
    echo [ACTION] Do not bypass this lock. Review the offline result and obtain explicit approval for this physical run.
    goto :failed
)

py -3.11 hardware\g1_arm_bridge\test_gate6_interrupt_release.py
if errorlevel 1 (
    echo [ERROR] Offline interruption-release verification failed.
    echo [ACTION] Fix its first reported error before creating any publisher.
    goto :failed
)

echo [STEP 1/3] Querying MotionSwitcher without changing it...
if exist "%MODE_JSON%" del /q "%MODE_JSON%"
if exist "%PRECHECK_JSON%" del /q "%PRECHECK_JSON%"
wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/query_motion_mode_wsl.sh
if errorlevel 1 (
    echo [ERROR] MotionSwitcher CheckMode failed.
    echo [ACTION] Verify G1 power, Ethernet, WSL, and Regular Mode.
    goto :failed
)

echo [STEP 2/3] Creating a fresh read-only startup precheck...
start "G1 Gate 6 Precheck LowState - READ ONLY" wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_read_only_wsl.sh --timeout 0.25 --forward-host 127.0.0.1 --forward-port 5007 --forward-hz 100
timeout /t 2 /nobreak >nul
py -3.11 hardware\g1_arm_bridge\check_startup_readiness.py --host 0.0.0.0 --port 5007 --motion-mode-json "%MODE_JSON%" --output "%PRECHECK_JSON%"
set "PRECHECK_RC=%ERRORLEVEL%"
wsl -d Ubuntu -- bash -lc "pkill -f '[r]ead_only_lowstate.py.*--forward-port 5007' || true" >nul 2>&1
if not "%PRECHECK_RC%"=="0" (
    echo [ERROR] Startup precheck did not return DIRECT_TELEOP_READY.
    echo [ACTION] Read %PRECHECK_JSON% and do not bypass its reason.
    goto :failed
)

echo [STEP 3/3] Explicit physical-output confirmation
echo [CONFIRM] G1 is grounded in Regular Mode, the area is clear,
echo [CONFIRM] L2+B is ready, and no competing arm/waist publisher exists.
choice /C YN /N /M "Start measured-pose interruption test? [Y/N]: "
if errorlevel 2 (
    echo [BLOCKED] Physical output was cancelled by the operator.
    echo [ACTION] Keep output disabled and retry only when every condition is true.
    goto :failed
)

echo.
echo [ACTIVE NEXT] Wait until weight reaches 0.200, then press Ctrl+C once.
echo [OBSERVE] Confirm a smooth 2 s release and natural Regular control return.
wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_gate6_hold_wsl.sh --config /mnt/c/Users/user/Desktop/G1_Teleop_Project/config/g1_gate6_interrupt_release_test.json --precheck-json /mnt/c/Users/user/Desktop/G1_Teleop_Project/logs/runtime/g1_startup_precheck.json --status-json /mnt/c/Users/user/Desktop/G1_Teleop_Project/logs/runtime/g1_gate6_interrupt_release_test.json --event-log /mnt/c/Users/user/Desktop/G1_Teleop_Project/logs/runtime/g1_gate6_interrupt_release_test.jsonl --enable-hardware-output --confirm ENABLE_G1_GATE6_INTERRUPT_RELEASE_TEST --confirm-grounded-regular G1_IS_GROUNDED_IN_REGULAR_MODE
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo [FAULT] Physical interruption test exited with code %RC%.
    echo [ACTION] Use L2+B if motion remains and inspect %STATUS_JSON%.
    goto :failed_with_code
)

echo [PASS] The software completed the zero-weight release sequence.
echo [VERIFY] Operator must still confirm no jump, sound, or balance disturbance.
echo Runtime status saved to: %STATUS_JSON%
echo Event log saved to: %EVENT_LOG%
call :relock
if errorlevel 1 exit /b 2
pause
exit /b 0

:failed
set "RC=1"
:failed_with_code
echo.
echo [FAIL] Gate 6 interruption test did not complete normally.
echo [ACTION] Follow the first ACTION above. Do not proceed to live Gate 7 output.
call :relock
if errorlevel 1 exit /b 2
pause
exit /b %RC%

:relock
py -3.11 -c "from pathlib import Path; p=Path(r'%CONFIG%'); s=p.read_text(encoding='utf-8'); old=chr(34)+'hardware_output_authorized'+chr(34)+': true'; new=chr(34)+'hardware_output_authorized'+chr(34)+': false'; assert old in s or new in s, 'Gate 6 authorization field is missing'; p.write_text(s.replace(old, new, 1), encoding='utf-8') if old in s else None"
if errorlevel 1 (
    echo [WARNING] Automatic Gate 6 authorization reset failed.
    echo [ACTION] Do not run another test; set hardware_output_authorized=false manually.
    exit /b 2
)
echo [LOCKED] Gate 6 physical authorization was restored to false.
exit /b 0
