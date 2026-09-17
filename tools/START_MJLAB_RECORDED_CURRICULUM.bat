@echo off
setlocal
cd /d "%~dp0.."
set "ITERATIONS=%~1"
set "RAMP=%~2"
if "%ITERATIONS%"=="" set "ITERATIONS=1000"
if "%RAMP%"=="" set "RAMP=800"
echo ============================================================
echo mjlab recorded-upper curriculum - simulation only
echo Fixed budget: %ITERATIONS% iterations
echo Recorded amplitude: 25%% to 100%% over %RAMP%, then full amplitude
echo No G1 SDK, DDS, network, publisher, or motor output
echo ============================================================
wsl.exe -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/experiments/independent_locomotion/run_recorded_curriculum.sh %ITERATIONS% %RAMP%
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo [COMPLETE] Fixed and recorded curriculum runs finished.
) else (
  echo [FAILED] Exit code %RC%. Run CHECK_MJLAB_MATCHED_TRAINING.bat.
)
pause
exit /b %RC%
