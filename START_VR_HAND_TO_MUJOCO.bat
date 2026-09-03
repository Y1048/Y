@echo off
setlocal EnableExtensions

title G1 Quest Hand Tracking + Mink

set "PROJECT_ROOT=%~dp0"
set "CONTROLLER_ROOT=%PROJECT_ROOT%MuJoCo_G1_Controller"
set "UNITY_PROJECT=%PROJECT_ROOT%Unity_G1_VR"
set "UNITY_EXE=C:\Program Files\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe"
set "MUJOCO_SCRIPT=%CONTROLLER_ROOT%\scripts\run_mink_g1_right_arm_virtual_center_live_entry.py"
set "CAMERA_LAUNCHER=%PROJECT_ROOT%tools\START_G1_CAMERA_TO_UNITY.bat"
set "IK_MODE=virtual-center"
set "CHECK_ONLY=0"
set "DISPLAY_MODE=simulation"
if /I "%~1"=="--hardware-display" set "DISPLAY_MODE=hardware"
if /I "%~2"=="--hardware-display" set "DISPLAY_MODE=hardware"
if /I "%~1"=="--baseline" (
    set "MUJOCO_SCRIPT=%CONTROLLER_ROOT%\scripts\run_mink_g1_right_arm_prototype_entry.py"
    set "IK_MODE=baseline"
)
if /I "%~2"=="--baseline" (
    set "MUJOCO_SCRIPT=%CONTROLLER_ROOT%\scripts\run_mink_g1_right_arm_prototype_entry.py"
    set "IK_MODE=baseline"
)
if /I "%~1"=="--check" set "CHECK_ONLY=1"
if /I "%~2"=="--check" set "CHECK_ONLY=1"
set "TELEOP_CONFIG=%PROJECT_ROOT%config\teleop.json"
set "GATE7_FEEDBACK_PORT=5012"

echo ========================================
echo G1 Quest hand tracking to Mink/MuJoCo
echo ========================================
echo IK mode: %IK_MODE%
echo.

if not exist "%UNITY_EXE%" (
    echo [ERROR] Unity 6000.5.4f1 was not found.
    echo %UNITY_EXE%
    echo [ACTION] Install Unity 6000.5.4f1 in Unity Hub, or update UNITY_EXE in this BAT to its actual path.
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

py -3.11 -c "import mujoco, numpy, mink, qpsolvers" >nul 2>&1
if errorlevel 1 (
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
powershell -NoProfile -Command "$ip=Get-NetIPAddress -IPAddress '192.168.123.99' -ErrorAction SilentlyContinue; if($ip -and (Test-Connection 192.168.123.164 -Count 1 -Quiet)){exit 0}else{exit 1}" >nul 2>&1
if not errorlevel 1 set "G1_CAMERA_AVAILABLE=1"

set "G1_CAMERA_RUNNING=0"
wsl -d Ubuntu -- bash -lc "pgrep -f '[g]1_camera_tcp_bridge.py' >/dev/null" >nul 2>&1
if not errorlevel 1 set "G1_CAMERA_RUNNING=1"

if "%CHECK_ONLY%"=="1" (
    echo [OK] Required project files, config, and programs are ready.
    if "%UDP_RUNNING%"=="1" (echo [STATUS] UDP port %UDP_PORT% is already in use.) else (echo [STATUS] Mink controller is not running.)
    if "%UNITY_PROJECT_RUNNING%"=="1" (echo [STATUS] Unity G1 VR project is already open.) else (echo [STATUS] Unity G1 VR project is not running.)
    if "%G1_CAMERA_AVAILABLE%"=="1" (echo [STATUS] G1 camera API is reachable by Ethernet.) else (echo [STATUS] G1 camera bridge will stay off until G1 Ethernet is connected.)
    exit /b 0
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
    start "G1 Mink Right Arm" /D "%CONTROLLER_ROOT%" cmd /k py -3.11 "%MUJOCO_SCRIPT%"
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
    echo [INFO] G1 camera bridge skipped: 192.168.123.164 is not reachable.
)

echo.
echo Ready for the live test:
echo   1. In Meta Horizon Link, confirm Quest Link is connected.
echo   2. In Unity, open Assets/Scenes/SampleScene if needed.
echo   3. Press the Play button at the top of Unity.
echo      If G1 Ethernet is connected, the head-camera PiP turns green after live JPEG frames arrive.
echo   4. Move the cyan Quest wrist marker to the G1 wrist engagement target.
echo   5. Hold it inside the target for around 0.55 seconds while it turns yellow.
echo   6. After the target turns green, move and rotate your right wrist.
echo   7. Confirm that the Mink/MuJoCo right arm follows the wrist pose.
echo   8. The inspection stick and panel are currently hidden for camera/arm tests.
echo   9. After disengagement, Gate 7 simulation feedback on UDP 5012 shows the
echo      10-second HOLD and Regular-pose return directly in the MuJoCo window.
echo.
echo Controller:
if "%IK_MODE%"=="virtual-center" (
    echo   Smooth virtual-center: position=right_wrist_roll_link, rotation=right_wrist_yaw_link
) else (
    echo   Baseline Mink 6D FrameTask on right_wrist_yaw_link
)
echo   DAQP QP solver preferred
echo   Non-right-arm DOFs frozen
echo   Joint, velocity, and collision limits enabled
echo   Gate 7 command provenance: explicit live_mink
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
