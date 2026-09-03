@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

for /f "delims=" %%F in ('powershell -NoProfile -Command "$f=Get-ChildItem 'logs\captures\g1_mink_capture_*.jsonl' -ErrorAction SilentlyContinue ^| Sort-Object LastWriteTime -Descending ^| Select-Object -First 1; if($f){$f.FullName}"') do set "CAPTURE=%%F"
if not defined CAPTURE (
    echo [ERROR] No recorded Mink capture was found.
    echo [ACTION] Run tools\START_G1_GATE7_VR_RECORDING.bat and record one engaged session first.
    goto :failed
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "RESULT_JSON=%CD%\logs\test_results\g1_gate7_capture_fault_matrix_%STAMP%.json"
echo Capture: %CAPTURE%
py -3.11 hardware\g1_arm_bridge\gate7_fault_injection_matrix.py --capture "%CAPTURE%" --result-json "%RESULT_JSON%"
if errorlevel 1 goto :failed

echo.
echo [PASS] Latest real VR capture passed the Gate 7 fault matrix.
echo Result saved to: %RESULT_JSON%
pause
exit /b 0

:failed
echo.
echo [FAIL] Latest-capture Gate 7 fault matrix did not pass.
echo [ACTION] Keep hardware output locked and follow the first ACTION above.
if defined RESULT_JSON echo Result path: %RESULT_JSON%
pause
exit /b 2
