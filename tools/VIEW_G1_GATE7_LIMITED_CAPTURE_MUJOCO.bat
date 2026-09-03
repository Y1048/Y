@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

for /f "delims=" %%F in ('dir /b /a-d /o-d "logs\captures\g1_mink_capture_*.jsonl" 2^>nul') do if not defined CAPTURE set "CAPTURE=%CD%\logs\captures\%%F"
if not defined CAPTURE (
    echo [ERROR] No recorded Mink capture was found.
    echo [ACTION] Run tools\START_G1_GATE7_VR_RECORDING.bat with Quest first.
    goto :failed
)

echo ============================================================
echo G1 GATE 7 QUEST CAPTURE - EXPERIMENTAL LIMITED REPLAY
echo   Ruckig: 50/125 deg/s, acceleration 3x, jerk 6x
echo   Unitree SDK: NONE / DDS publisher: NONE / Robot command: NONE
echo ============================================================
echo Capture: %CAPTURE%
py -3.11 -c "import ruckig" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python package ruckig 0.19.4 is not installed.
    echo [ACTION] Run: py -3.11 -m pip install ruckig==0.19.4
    goto :failed
)
set "REPLAY_ARGS=--experimental-limiter"
if /I "%~1"=="--validate-only" set "REPLAY_ARGS=%REPLAY_ARGS% --validate-only"
py -3.11 hardware\g1_arm_bridge\gate7_capture_mujoco_replay.py "%CAPTURE%" %REPLAY_ARGS%
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo [FAIL] Experimental limited MuJoCo replay failed.
echo [ACTION] Keep physical Gate 7 locked and fix the first reported error.
pause
exit /b 2
