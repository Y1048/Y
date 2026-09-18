@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Path-only check exits before the existing launcher actions.
call "%~dp0tools\RESOLVE_UNITY_EDITOR.bat" "%~1"
if /I "%~1"=="--check-unity-path" exit /b %ERRORLEVEL%

title G1 Quest Hand Tracking + Mink

set "PROJECT_ROOT=%~dp0"
set "CONTROLLER_ROOT=%PROJECT_ROOT%MuJoCo_G1_Controller"
set "UNITY_PROJECT=%PROJECT_ROOT%Unity_G1_VR"
set "MUJOCO_SCRIPT=%CONTROLLER_ROOT%\scripts\run_mink_g1_right_arm_virtual_center_live_entry.py"
set "CAMERA_LAUNCHER=%PROJECT_ROOT%tools\START_G1_CAMERA_TO_UNITY.bat"
set "IK_MODE=virtual-center"
set "IK_SOLVER=hierarchical"
set "CHECK_ONLY=0"
set "DISPLAY_MODE=simulation"
set "EXTERNAL_FEEDBACK=0"
set "CAMERA_REQUESTED=0"
set "RECORD_RIGHT_ARM_CSV=0"
for %%A in (%*) do (
    if /I "%%~A"=="--external-feedback" set "EXTERNAL_FEEDBACK=1"
    if /I "%%~A"=="--camera" set "CAMERA_REQUESTED=1"
    if /I "%%~A"=="--record-right-arm-csv" set "RECORD_RIGHT_ARM_CSV=1"
)
if /I "%~1"=="--hardware-display" set "DISPLAY_MODE=hardware"
if /I "%~2"=="--hardware-display" set "DISPLAY_MODE=hardware"
rem Standard 6D is the local baseline; preserve hardware solver selection.
if /I "%DISPLAY_MODE%"=="simulation" set "IK_SOLVER=vanilla"
if /I "%~1"=="--hierarchical" set "IK_SOLVER=hierarchical"
if /I "%~2"=="--hierarchical" set "IK_SOLVER=hierarchical"
if /I "%~1"=="--standard-mink" set "IK_SOLVER=vanilla"
if /I "%~2"=="--standard-mink" set "IK_SOLVER=vanilla"
rem Local Unity/MuJoCo uses Mink's upstream 5/10 mm collision distances.
rem The hardware-display path below always overrides this with its guarded profile.
set "COLLISION_PROFILE=mink-default"
if /I "%~1"=="--mink-default" set "COLLISION_PROFILE=mink-default"
if /I "%~2"=="--mink-default" set "COLLISION_PROFILE=mink-default"
if /I "%DISPLAY_MODE%"=="hardware" set "COLLISION_PROFILE=hardware-guarded"
if /I "%~1"=="--baseline" (
    set "MUJOCO_SCRIPT=%CONTROLLER_ROOT%\scripts\run_mink_g1_right_arm_prototype_entry.py"
    set "IK_MODE=baseline"
)
if /I "%~2"=="--baseline" (
    set "MUJOCO_SCRIPT=%CONTROLLER_ROOT%\scripts\run_mink_g1_right_arm_prototype_entry.py"
    set "IK_MODE=baseline"
)
if /I "%~1"=="--vanilla-mink" (
    set "MUJOCO_SCRIPT=%CONTROLLER_ROOT%\scripts\run_mink_g1_right_arm_prototype_entry.py"
    set "IK_MODE=vanilla-mink"
)
if /I "%~2"=="--vanilla-mink" (
    set "MUJOCO_SCRIPT=%CONTROLLER_ROOT%\scripts\run_mink_g1_right_arm_prototype_entry.py"
    set "IK_MODE=vanilla-mink"
)
if /I "%~1"=="--check" set "CHECK_ONLY=1"
if /I "%~2"=="--check" set "CHECK_ONLY=1"
set "TELEOP_CONFIG=%PROJECT_ROOT%config\teleop.json"
set "GATE7_FEEDBACK_PORT=5012"
set "LOCAL_ENGINE_312=0"
set "INITIAL_SEED_ARGS="
set "RIGHT_ARM_CSV_ARGS="
if defined G1_MINK_INITIAL_SEED set "INITIAL_SEED_ARGS=--seed-from-environment"
if defined G1_MINK_INITIAL_SESSION set "INITIAL_SEED_ARGS=--seed-from-environment"
if "%RECORD_RIGHT_ARM_CSV%"=="1" (
    if not exist "%PROJECT_ROOT%logs\test_results\mink_right_arm_csv" mkdir "%PROJECT_ROOT%logs\test_results\mink_right_arm_csv"
    for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss_fff"') do set "RIGHT_ARM_CSV_PATH=%PROJECT_ROOT%logs\test_results\mink_right_arm_csv\mink_right_arm_%%T.csv"
)
if defined RIGHT_ARM_CSV_PATH set RIGHT_ARM_CSV_ARGS=--right-arm-csv "%RIGHT_ARM_CSV_PATH%"
rem Local shared-loop baseline uses the engine validated by distance regression.
if /I "%DISPLAY_MODE%"=="simulation" if /I "%IK_MODE%"=="virtual-center" set "LOCAL_ENGINE_312=1"
if /I "%~1"=="--mujoco311" set "LOCAL_ENGINE_312=0"
if /I "%~2"=="--mujoco311" set "LOCAL_ENGINE_312=0"
if /I "%~1"=="--mujoco312" set "LOCAL_ENGINE_312=1"
if /I "%~2"=="--mujoco312" set "LOCAL_ENGINE_312=1"
if "%LOCAL_ENGINE_312%"=="1" (
    if /I not "%DISPLAY_MODE%"=="simulation" (
        echo [ERROR] MuJoCo 3.12 is local simulation only.
        goto :failed
    )
    if /I not "%IK_MODE%"=="virtual-center" (
        echo [ERROR] Isolated engine requires the shared controller loop.
        goto :failed
    )
    set "MUJOCO_SCRIPT=%CONTROLLER_ROOT%\scripts\run_mink_g1_simulation_312.py"
)

if defined INITIAL_SEED_ARGS if not "%LOCAL_ENGINE_312%"=="1" (
    echo [ERROR] LowState seed requires the isolated simulation engine.
    goto :failed
)
echo ========================================
echo G1 Quest hand tracking to Mink/MuJoCo
echo ========================================
echo IK mode: %IK_MODE%
echo IK solver: %IK_SOLVER%
echo.

if not exist "%UNITY_EXE%" (
    echo [ERROR] Unity 6000.5.4f1 was not found.
    echo %UNITY_EXE%
    echo [ACTION] Install Unity 6000.5.4f1 in Unity Hub, or set UNITY_EXE before calling this BAT.
    goto :failed
)

if not exist "%UNITY_PROJECT%\Assets\Scenes\SampleScene.unity" (
    echo [ERROR] The Unity test scene was not found.
    echo [ACTION] Restore Unity_G1_VR\Assets\Scenes\SampleScene.unity from Git before starting teleoperation.
    goto :failed
)

if not exist "%MUJOCO_SCRIPT%" (
    echo [ERROR] The Mink MuJoCo controller was not found.
    echo %MUJOCO_SCRIPT%
    echo [ACTION] Restore the missing controller script from Git, then run this BAT again.
    goto :failed
)

if not exist "%TELEOP_CONFIG%" (
    echo [ERROR] Teleoperation config was not found.
    echo %TELEOP_CONFIG%
    echo [ACTION] Restore config\teleop.json from Git; do not create an unverified replacement during a hardware test.
    goto :failed
)

if "%LOCAL_ENGINE_312%"=="1" (
    py -3.11 "%MUJOCO_SCRIPT%" --validate-only --ik-solver %IK_SOLVER% %INITIAL_SEED_ARGS%
) else (
    py -3.11 -c "import mujoco, numpy, mink, qpsolvers" >nul 2>&1
)
if errorlevel 1 (
    if "%LOCAL_ENGINE_312%"=="1" (
        echo [ERROR] Isolated MuJoCo 3.12 validation failed.
        echo [ACTION] Check the first Python error and restore the isolated engine folder:
        echo %PROJECT_ROOT%logs\diagnostics\mujoco_versions\3.12.0
        echo [ACTION] Do not replace the global or WSL installation to fix this launcher.
        goto :failed
    )
    echo [ERROR] Python 3.11 Mink/MuJoCo environment is not ready.
    echo [ACTION] Run: py -3.11 -m pip install mujoco mink daqp qpsolvers numpy
    echo [ACTION] Then run this BAT again.
    goto :failed
)

for /f %%P in ('py -3.11 -c "import json; print(json.load(open(r'%TELEOP_CONFIG%', encoding='utf-8'))['network']['udp_port'])"') do set "UDP_PORT=%%P"
if not defined UDP_PORT (
    echo [ERROR] Could not read network.udp_port from config\teleop.json.
    echo [ACTION] Validate config\teleop.json as JSON and restore its network.udp_port value.
    goto :failed
)

tasklist /FI "IMAGENAME eq OVRServer_x64.exe" 2>nul | find /I "OVRServer_x64.exe" >nul
if errorlevel 1 (
    echo [WARNING] Meta Horizon Link is not running.
    echo [ACTION] Open Meta Horizon Link, connect Quest Link, and confirm the headset is active before Unity Play Mode.
) else (
    echo [OK] Meta Horizon Link runtime is running.
)

set "UDP_RUNNING=0"
netstat -ano -p UDP | findstr /R /C:":%UDP_PORT%[ ]" >nul
if not errorlevel 1 set "UDP_RUNNING=1"

set "GATE7_FEEDBACK_RUNNING=0"
if "%UDP_RUNNING%"=="1" if "%LOCAL_ENGINE_312%"=="1" (
    echo [ERROR] Close the existing controller before changing the simulation engine.
    goto :failed
)
if "%UDP_RUNNING%"=="1" if /I "%IK_SOLVER%"=="vanilla" (
    echo [ERROR] Stop the existing controller before selecting standard Mink.
    goto :failed
)
netstat -ano -p UDP | findstr /R /C:":%GATE7_FEEDBACK_PORT%[ ]" >nul
if not errorlevel 1 set "GATE7_FEEDBACK_RUNNING=1"

if "%UDP_RUNNING%"=="1" if "%GATE7_FEEDBACK_RUNNING%"=="0" (
    echo [WARNING] The existing Mink process does not listen on simulation feedback UDP %GATE7_FEEDBACK_PORT%.
    echo [ACTION] Close the old Mink/MuJoCo window, then run this launcher again to enable Regular-return visualization.
)
if "%UDP_RUNNING%"=="0" if "%GATE7_FEEDBACK_RUNNING%"=="1" (
    echo [ERROR] UDP %GATE7_FEEDBACK_PORT% is already used by another process.
    echo [ACTION] Close the process using UDP %GATE7_FEEDBACK_PORT%, then run this launcher again.
    goto :failed
)

rem Detect THIS Unity project, not merely any Unity.exe process.
set "UNITY_PROJECT_RUNNING=0"
powershell -NoProfile -Command "$u='%UNITY_PROJECT%'.ToLowerInvariant(); $p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'Unity.exe' -and $_.CommandLine -and $_.CommandLine.ToLowerInvariant().Contains($u) }; if($p){exit 0}else{exit 1}" >nul 2>&1
if not errorlevel 1 set "UNITY_PROJECT_RUNNING=1"

set "G1_CAMERA_AVAILABLE=0"
set "G1_CAMERA_RUNNING=0"
if "%CAMERA_REQUESTED%"=="0" goto :camera_checks_done
powershell -NoProfile -Command "$ip=Get-NetIPAddress -IPAddress '192.168.123.99' -ErrorAction SilentlyContinue; if($ip -and (Test-Connection 192.168.123.164 -Count 1 -Quiet)){exit 0}else{exit 1}" >nul 2>&1
if not errorlevel 1 set "G1_CAMERA_AVAILABLE=1"

set "G1_CAMERA_RUNNING=0"
wsl -d Ubuntu -- bash -lc "pgrep -f '[g]1_camera_tcp_bridge.py' >/dev/null" >nul 2>&1
if not errorlevel 1 set "G1_CAMERA_RUNNING=1"
:camera_checks_done

if "%CHECK_ONLY%"=="1" (
    echo [OK] Required project files, config, and programs are ready.
    if "%UDP_RUNNING%"=="1" (echo [STATUS] UDP port %UDP_PORT% is already in use.) else (echo [STATUS] Mink controller is not running.)
    if "%UNITY_PROJECT_RUNNING%"=="1" (echo [STATUS] Unity G1 VR project is already open.) else (echo [STATUS] Unity G1 VR project is not running.)
    if "%G1_CAMERA_AVAILABLE%"=="1" (echo [STATUS] G1 camera API is reachable by Ethernet.) else (echo [STATUS] G1 camera bridge will stay off until G1 Ethernet is connected.)
    exit /b 0
)

if /I "%DISPLAY_MODE%"=="simulation" if /I "%IK_MODE%"=="virtual-center" if "%EXTERNAL_FEEDBACK%"=="0" (
    netstat -ano -p UDP | findstr /R /C:":5008[ ]" >nul
    if not errorlevel 1 (
        echo [ERROR] UDP 5008 is occupied. Do not reuse an unknown receiver.
        echo [ACTION] Close the old dry-run or relay before starting this simulation.
        goto :failed
    )
    py -3.11 "%PROJECT_ROOT%hardware\g1_arm_bridge\gate7_live_dry_run.py" --validate-only
    if errorlevel 1 (
        echo [ERROR] Regular-return simulation validation failed.
        echo [ACTION] Fix the first Python error above. No hardware output was started.
        goto :failed
    )
    start "G1 Regular Return - SIMULATION ONLY" /D "%PROJECT_ROOT%" cmd /k py -3.11 hardware\g1_arm_bridge\gate7_live_dry_run.py --measured-source mink --event-log auto --result-json auto
    timeout /t 4 /nobreak >nul
    netstat -ano -p UDP | findstr /R /C:":5008[ ]" >nul
    if errorlevel 1 (
        echo [ERROR] Regular-return simulator did not bind UDP 5008.
        echo [ACTION] Read the separate simulation window and fix its first error.
        goto :failed
    )
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%tools\SET_UNITY_DISPLAY_MODE.ps1" -Mode %DISPLAY_MODE%
if errorlevel 1 (
    echo [ERROR] Could not set the local Unity display mode.
    echo [ACTION] Stop Unity Play and check logs\runtime write access before retrying.
    goto :failed
)

if "%UNITY_PROJECT_RUNNING%"=="0" (
    echo [START] Unity G1 VR project
    start "G1 VR Unity" "%UNITY_EXE%" -projectPath "%UNITY_PROJECT%"
    timeout /t 2 /nobreak >nul
) else (
    echo [KEEP] Unity G1 VR project is already open.
)

if "%UDP_RUNNING%"=="0" (
    echo [START] Mink/DAQP G1 right-arm controller: %IK_MODE%
    if /I "%IK_MODE%"=="virtual-center" (
        echo [PROFILE] Collision: %COLLISION_PROFILE%
        start "G1 Mink Right Arm" /D "%CONTROLLER_ROOT%" cmd /k py -3.11 "%MUJOCO_SCRIPT%" --collision-profile %COLLISION_PROFILE% --ik-solver %IK_SOLVER% %INITIAL_SEED_ARGS% %RIGHT_ARM_CSV_ARGS%
    ) else (
        echo [PROFILE] Collision: %COLLISION_PROFILE%
        start "G1 Vanilla Mink Right Arm" /D "%CONTROLLER_ROOT%" cmd /k py -3.11 "%MUJOCO_SCRIPT%" --collision-profile %COLLISION_PROFILE%
    )
) else (
    echo [KEEP] A UDP controller is already listening on port %UDP_PORT%.
)

if "%G1_CAMERA_AVAILABLE%"=="1" (
    if "%G1_CAMERA_RUNNING%"=="0" (
        echo [START] Read-only G1 camera bridge to Unity TCP 5011
        start "G1 Camera Read Only" cmd /c call "%CAMERA_LAUNCHER%"
    ) else (
        echo [KEEP] The read-only G1 camera bridge is already running.
    )
) else (
    echo [INFO] Camera not started. Optional read-only camera: run this BAT with --camera.
    echo [INFO] With --camera, Windows 192.168.123.99 and reachable G1 192.168.123.164 are required.
)

echo.
echo Ready for the live test:
echo   1. In Meta Horizon Link, confirm Quest Link is connected.
echo   2. In Unity, open Assets/Scenes/SampleScene if needed.
echo   3. Press the Play button at the top of Unity.
echo      With --camera and G1 connected, the PiP turns green after live JPEG frames arrive.
echo   4. Move the cyan Quest wrist marker to the G1 wrist engagement target.
echo   5. Hold it inside the target for around 0.55 seconds while it turns yellow.
echo   6. After the target turns green, move and rotate your right wrist.
echo   7. Confirm that the Mink/MuJoCo right arm follows the wrist pose.
echo   8. The inspection stick and panel are currently hidden for camera/arm tests.
echo   9. In the default simulation, pinch requests Regular return;
echo      tracking-loss HOLD returns after 10 seconds through UDP 5012 feedback.
echo      Legacy baseline modes do not include this return simulator.
echo   10. Stop the Regular Return window with Ctrl+C when finished.
echo       It prints result paths. Close the optional camera window separately.
echo.
echo Controller:
if "%IK_MODE%"=="virtual-center" (
    if /I "%IK_SOLVER%"=="vanilla" (
        echo   Standard Mink: one 6D task on right_wrist_yaw_link, shared feedback loop
    ) else (
        echo   Smooth virtual-center: position=right_wrist_roll_link, rotation=right_wrist_yaw_link
    )
) else (
    echo   Vanilla Mink comparison: one 6D FrameTask on right_wrist_yaw_link
)
echo   DAQP QP solver preferred
echo   Non-right-arm DOFs frozen
echo   Joint, velocity, and collision limits enabled
echo   Collision profile: %COLLISION_PROFILE%
if "%LOCAL_ENGINE_312%"=="1" (
    echo   Gate 7 command provenance: simulation_only - physical relay rejects it
) else (
    echo   Gate 7 command provenance: explicit live_mink
)
echo.
echo Marker colors:
echo   Cyan   = actual Quest wrist
echo   White  = waiting for alignment
echo   Yellow = aligned; hold still to engage
echo   Green  = teleoperation active
echo   Gesture disengage = thumb-index pinch 0.50 s
echo.
echo Keep this window open only as a checklist; closing it does not stop the test.
pause
exit /b 0

:failed
echo.
echo [FAIL] The test was not started.
echo [ACTION] Complete the action shown immediately above, then run this BAT again.
pause
exit /b 1
