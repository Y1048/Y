@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

title G1 Gate 7 LowState Dry Run Launcher

echo ============================================================
echo G1 Gate 7 REAL LOWSTATE DRY RUN - NO ROBOT OUTPUT
echo   G1 rt/lowstate ^> WSL Cyclone DDS subscriber ^> UDP 5007
echo   Unity ^> UDP 5005 ^> Mink/MuJoCo ^> UDP 5008 ^> Gate 7
echo   Unitree SDK publisher: NONE / Robot command: NONE
echo ============================================================
echo.

netstat -ano -p UDP | findstr /R /C:":5007[ ]" >nul
if not errorlevel 1 (
    echo [ERROR] UDP port 5007 is already in use.
    echo [ACTION] Close the old Gate 5 or Gate 7 LowState monitor, then retry.
    goto :failed
)

netstat -ano -p UDP | findstr /R /C:":5008[ ]" >nul
if not errorlevel 1 (
    echo [ERROR] UDP port 5008 is already in use.
    echo [ACTION] Close the old Safety Gate or Gate 7 dry-run window, then retry.
    goto :failed
)

wsl -d Ubuntu -- bash -lc "ip -o -4 addr show | grep -q '192[.]168[.]123[.]99/24'"
if errorlevel 1 (
    echo [ERROR] WSL cannot see G1 Ethernet address 192.168.123.99/24.
    echo [ACTION] Connect G1 Ethernet and run tools\DETECT_G1_NETWORK.bat.
    echo [ACTION] If needed, run tools\CONFIGURE_G1_ETHERNET.bat and retry.
    goto :failed
)

py -3.11 hardware\g1_arm_bridge\gate7_live_dry_run.py --measured-source lowstate --trajectory-generator ruckig --simulate-command-following --validate-only
if errorlevel 1 (
    echo [ERROR] Gate 7 LowState dependencies or locked config validation failed.
    echo [ACTION] Run tools\TEST_G1_GATE7_MINK_ARM_SDK_OFFLINE.bat and fix its first error.
    goto :failed
)

echo [START] Read-only rt/lowstate subscriber and UDP 5007 forwarder...
start "G1 Gate 7 LowState Forwarder - READ ONLY" wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/hardware/g1_arm_bridge/start_read_only_wsl.sh --timeout 0.25 --forward-host 127.0.0.1 --forward-port 5007 --forward-hz 100
timeout /t 3 /nobreak >nul

wsl -d Ubuntu -- bash -lc "pgrep -f '[r]ead_only_lowstate.py.*--forward-port 5007' >/dev/null"
if errorlevel 1 (
    echo [ERROR] The read-only LowState forwarder exited before Gate 7 started.
    echo [ACTION] Read the error in the separate forwarder window.
    echo [ACTION] Verify G1 power, Ethernet, Regular Mode, WSL venv and Cyclone DDS interface selection.
    goto :failed
)

echo [START] Gate 7 with measured-source=lowstate on UDP 5007...
start "G1 Gate 7 Real LowState Ruckig Dry Run" cmd /k py -3.11 hardware\g1_arm_bridge\gate7_live_dry_run.py --measured-source lowstate --trajectory-generator ruckig --simulate-command-following --lowstate-host 0.0.0.0 --lowstate-port 5007 --event-log auto --result-json auto
timeout /t 4 /nobreak >nul

netstat -ano -p UDP | findstr /R /C:":5008[ ]" >nul
if errorlevel 1 (
    echo [ERROR] Gate 7 did not bind Mink UDP 5008.
    echo [ACTION] Read the error in the separate Gate 7 window and retry.
    goto :failed
)

netstat -ano -p UDP | findstr /R /C:":5007[ ]" >nul
if errorlevel 1 (
    echo [ERROR] Gate 7 did not bind LowState UDP 5007.
    echo [ACTION] Read the error in the separate Gate 7 window and retry.
    goto :failed
)

echo [START] Unity + Mink/MuJoCo VR path...
call START_VR_HAND_TO_MUJOCO.bat
set "RC=%ERRORLEVEL%"

echo.
echo [INFO] Keep both the LowState forwarder and Gate 7 windows open during the test.
echo [INFO] Press Ctrl+C in Gate 7 to finish and print the exact event/result paths.
echo [INFO] Close the read-only forwarder window after Gate 7 has stopped.
echo [INFO] This launcher creates no DDS publisher and sends no G1 command.
pause
endlocal & exit /b %RC%

:failed
echo.
echo [FAIL] Gate 7 real-LowState dry run was not started.
echo [ACTION] Follow the first [ACTION] message above, then run this launcher again.
echo [INFO] No robot command was sent.
pause
endlocal & exit /b 1
