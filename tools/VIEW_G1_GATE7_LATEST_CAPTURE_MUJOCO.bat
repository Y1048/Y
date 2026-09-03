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
echo G1 GATE 7 QUEST CAPTURE - MUJOCO OFFLINE REPLAY
echo   First engage through tracking-loss window, repeated
echo   Unitree SDK: NONE / DDS publisher: NONE / Robot command: NONE
echo ============================================================
echo Capture: %CAPTURE%
set "REPLAY_ARGS="
if /I "%~1"=="--validate-only" set "REPLAY_ARGS=--validate-only"
py -3.11 hardware\g1_arm_bridge\gate7_capture_mujoco_replay.py "%CAPTURE%" %REPLAY_ARGS%
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo [FAIL] Quest capture MuJoCo replay failed.
echo [ACTION] Close any old MuJoCo window and fix the first reported error.
pause
exit /b 2
