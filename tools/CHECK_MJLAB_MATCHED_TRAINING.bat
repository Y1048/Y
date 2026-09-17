@echo off
setlocal
cd /d "%~dp0.."
if not exist "logs\test_results\mjlab_matched_continuation_latest.txt" (
  echo No continuation run has been started.
  pause
  exit /b 1
)
set /p OUT=<"logs\test_results\mjlab_matched_continuation_latest.txt"
for /f "usebackq delims=" %%P in (`wsl.exe -d Ubuntu -- wslpath -w "%OUT%"`) do set "WINOUT=%%P"
echo Result directory: %WINOUT%
if exist "%WINOUT%\COMPLETE" (
  echo [COMPLETE] Both models finished.
) else if exist "%WINOUT%\FIXED_COMPLETE" (
  echo [RUNNING] Fixed model finished; recorded model is running.
) else (
  echo [RUNNING] Fixed model is running, or startup failed.
)
echo.
if exist "%WINOUT%\recorded_console.log" (
  powershell.exe -NoProfile -Command "Get-Content -LiteralPath '%WINOUT%\recorded_console.log' -Tail 24"
) else if exist "%WINOUT%\fixed_console.log" (
  powershell.exe -NoProfile -Command "Get-Content -LiteralPath '%WINOUT%\fixed_console.log' -Tail 24"
)
pause
