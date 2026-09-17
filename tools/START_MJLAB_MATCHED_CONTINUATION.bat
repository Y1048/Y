@echo off
setlocal
cd /d "%~dp0.."
set "ITERATIONS=%~1"
if "%ITERATIONS%"=="" set "ITERATIONS=500"
echo ============================================================
echo mjlab matched continuation - simulation only
echo Fixed upper then recorded Mink upper, %ITERATIONS% iterations each
echo Repeated runs resume the newest fully completed continuation
echo No G1 SDK, DDS, network, publisher, or motor output
echo ============================================================
wsl.exe -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/experiments/independent_locomotion/run_matched_training_continuation.sh %ITERATIONS%
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo [COMPLETE] Both matched continuation runs finished.
) else (
  echo [FAILED] Exit code %RC%. Run CHECK_MJLAB_MATCHED_TRAINING.bat.
)
pause
exit /b %RC%
