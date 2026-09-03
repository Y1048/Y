@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

for /f "delims=" %%F in ('powershell -NoProfile -Command "$f=Get-ChildItem 'logs\captures\g1_mink_capture_*.jsonl' -ErrorAction SilentlyContinue ^| Sort-Object LastWriteTime -Descending ^| Select-Object -First 1; if($f){$f.FullName}"') do set "CAPTURE=%%F"
if not defined CAPTURE (
    echo [ERROR] No recorded Mink capture was found.
    echo [ACTION] Run tools\START_G1_GATE7_VR_RECORDING.bat and record one session first.
    goto :failed
)

set "BASELINE=%CAPTURE:.jsonl=.baseline.json%"
echo Capture: %CAPTURE%
if not exist "%BASELINE%" (
    echo [INFO] No baseline exists; creating the first deterministic baseline.
    py -3.11 hardware\g1_arm_bridge\gate7_capture_regression.py "%CAPTURE%" --baseline "%BASELINE%" --write-baseline
) else (
    echo [INFO] Comparing the latest capture against its saved baseline.
    py -3.11 hardware\g1_arm_bridge\gate7_capture_regression.py "%CAPTURE%" --baseline "%BASELINE%"
)
if errorlevel 1 goto :failed

echo.
echo [PASS] Latest recorded-input regression matched or its baseline was created.
echo Baseline: %BASELINE%
pause
exit /b 0

:failed
echo.
echo [FAIL] Latest recorded-input regression did not pass.
echo [ACTION] Review the printed changed fields before any hardware test.
pause
exit /b 2
