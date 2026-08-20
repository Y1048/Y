@echo off
setlocal EnableExtensions

title G1 Quest Hand Tracking Test

set "PROJECT_ROOT=%~dp0"
set "CONTROLLER_ROOT=%PROJECT_ROOT%MuJoCo_G1_Controller"
set "UNITY_PROJECT=%PROJECT_ROOT%Unity_G1_Quest3S"
set "UNITY_EXE=C:\Program Files\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe"
set "MUJOCO_SCRIPT=%CONTROLLER_ROOT%\scripts\g1_right_arm_udp_ik_demo.py"

echo ========================================
echo G1 Quest hand tracking to MuJoCo test
echo ========================================
echo.

if not exist "%UNITY_EXE%" (
    echo [ERROR] Unity 6000.5.4f1 was not found.
    echo %UNITY_EXE%
    goto :failed
)

if not exist "%UNITY_PROJECT%\Assets\Scenes\SampleScene.unity" (
    echo [ERROR] The Unity test scene was not found.
    goto :failed
)

if not exist "%MUJOCO_SCRIPT%" (
    echo [ERROR] The MuJoCo controller was not found.
    goto :failed
)

py -3.11 -c "import mujoco, numpy" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11 or MuJoCo is not ready.
    goto :failed
)

tasklist /FI "IMAGENAME eq OVRServer_x64.exe" 2>nul | find /I "OVRServer_x64.exe" >nul
if errorlevel 1 (
    echo [WARNING] Meta Horizon Link is not running.
    echo           Open Meta Horizon Link and connect Quest Link first.
) else (
    echo [OK] Meta Horizon Link runtime is running.
)

set "UDP_RUNNING=0"
netstat -ano -p UDP | findstr /R /C:":5005[ ]" >nul
if not errorlevel 1 set "UDP_RUNNING=1"

set "UNITY_RUNNING=0"
tasklist /FI "IMAGENAME eq Unity.exe" 2>nul | find /I "Unity.exe" >nul
if not errorlevel 1 set "UNITY_RUNNING=1"

if /I "%~1"=="--check" (
    echo [OK] Required project files and programs are ready.
    if "%UDP_RUNNING%"=="1" (echo [STATUS] UDP port 5005 is already in use.) else (echo [STATUS] MuJoCo controller is not running.)
    if "%UNITY_RUNNING%"=="1" (echo [STATUS] Unity is already open.) else (echo [STATUS] Unity is not running.)
    exit /b 0
)

if "%UDP_RUNNING%"=="0" (
    echo [START] MuJoCo G1 right-arm controller
    start "G1 MuJoCo Right Arm" /D "%CONTROLLER_ROOT%" cmd /k py -3.11 scripts\g1_right_arm_udp_ik_demo.py --scene control --view overview
    timeout /t 2 /nobreak >nul
) else (
    echo [KEEP] A UDP controller is already listening on port 5005.
)

if "%UNITY_RUNNING%"=="0" (
    echo [START] Unity Quest project
    start "G1 Quest Unity" "%UNITY_EXE%" -projectPath "%UNITY_PROJECT%"
) else (
    echo [KEEP] The Unity Quest project is already open.
)

echo.
echo Ready for the live test:
echo   1. In Meta Horizon Link, confirm Quest Link is connected.
echo   2. In Unity, open Assets/Scenes/SampleScene if needed.
echo   3. Press the Play button at the top of Unity.
echo   4. Put on Quest and move the cyan wrist marker to the white target.
echo   5. Hold it inside the target for around 0.55 seconds while it turns yellow.
echo   6. After the target turns green, move and rotate your right wrist.
echo   7. Confirm that MuJoCo prints "receiving" and the right arm moves.
echo.
echo Marker colors:
echo   Cyan   = actual Quest wrist
echo   White  = waiting for alignment
echo   Yellow = aligned; hold still to engage
echo   Green  = teleoperation active
echo   Orange = G1 workspace limit reached
echo.
echo Test without Quest: tools\TEST_FAKE_VR_TO_MUJOCO.bat
echo.
echo Keep this window open only as a checklist; closing it does not stop the test.
pause
exit /b 0

:failed
echo.
echo The test was not started.
pause
exit /b 1
