@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

title G1 Gate 7 VR Recording - No Robot Output

echo ============================================================
echo G1 GATE 7 VR UDP RECORDING - NO ROBOT OUTPUT
echo   Mink UDP 5008 ^> capture proxy ^> Gate 7 UDP 5014
echo ============================================================

for %%P in (5008 5014) do (
    netstat -ano -p UDP | findstr /R /C:":%%P[ ]" >nul
    if not errorlevel 1 (
        echo [ERROR] UDP %%P is already in use.
        echo [ACTION] Close the old Gate 7, recorder or relay window, then retry.
        goto :failed
    )
)

py -3.11 hardware\g1_arm_bridge\gate7_live_dry_run.py --mink-port 5014 --validate-only
if errorlevel 1 (
    echo [ERROR] Gate 7 dry-run validation failed.
    echo [ACTION] Run tools\TEST_G1_GATE7_LIVE_DRY_RUN.bat and fix its first error.
    goto :failed
)

echo [START] Gate 7 dry-run receiver on UDP 5014...
start "G1 Gate 7 Recorded Session Dry Run" cmd /k py -3.11 hardware\g1_arm_bridge\gate7_live_dry_run.py --mink-port 5014 --measured-source mink --event-log auto --result-json auto
timeout /t 3 /nobreak >nul

echo [START] Strict UDP 5008 capture and forward proxy...
start "G1 Mink UDP Recorder" cmd /k py -3.11 hardware\g1_arm_bridge\gate7_mink_capture.py
timeout /t 2 /nobreak >nul

netstat -ano -p UDP | findstr /R /C:":5008[ ]" >nul
if errorlevel 1 (
    echo [ERROR] Recorder did not bind UDP 5008.
    echo [ACTION] Read the recorder window and fix its first error.
    goto :failed
)

echo [START] Unity and Mink/MuJoCo...
call START_VR_HAND_TO_MUJOCO.bat
set "RC=%ERRORLEVEL%"
echo.
echo [INFO] Perform the representative VR arm motions in Unity Play Mode.
echo [INFO] Stop the recorder with Ctrl+C first; it prints the capture path.
echo [INFO] Then stop Gate 7 with Ctrl+C and close the remaining windows.
echo [INFO] No G1 publisher or robot command is used.
pause
exit /b %RC%

:failed
echo.
echo [FAIL] VR UDP recording was not started.
echo [ACTION] Follow the first ACTION above; no robot command was sent.
pause
exit /b 2
