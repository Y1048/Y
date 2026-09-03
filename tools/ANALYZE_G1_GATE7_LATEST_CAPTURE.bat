@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

for /f "delims=" %%F in ('dir /b /a-d /o-d "logs\captures\g1_mink_capture_*.jsonl" 2^>nul') do if not defined CAPTURE set "CAPTURE=%CD%\logs\captures\%%F"
if not defined CAPTURE (
    echo [ERROR] No recorded Mink capture was found.
    echo [ACTION] Run tools\START_G1_GATE7_VR_RECORDING.bat with Quest first.
    goto :failed
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "RESULT_JSON=%CD%\logs\quality\g1_gate7_capture_quality_%STAMP%.json"
set "RESULT_HTML=%CD%\logs\quality\g1_gate7_capture_quality_%STAMP%.html"
echo Capture: %CAPTURE%
py -3.11 hardware\g1_arm_bridge\gate7_capture_quality.py "%CAPTURE%" --result-json "%RESULT_JSON%" --result-html "%RESULT_HTML%"
if errorlevel 1 goto :failed

echo.
echo [PASS] Quest capture quality report was created.
echo JSON saved to: %RESULT_JSON%
echo HTML saved to: %RESULT_HTML%
start "G1 Capture Quality" "%RESULT_HTML%"
pause
exit /b 0

:failed
echo.
echo [FAIL] Quest capture quality analysis failed.
echo [ACTION] Keep hardware output locked and fix the first reported error.
pause
exit /b 2
