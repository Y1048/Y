@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0.."
echo Bimanual session REPORT ONLY. No Unity, G1, DDS, SSH or motor output.
for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss_fffffff"') do set STAMP=%%I
set "REPORT_DIR=logs\test_results\bimanual\reports"
if not exist "%REPORT_DIR%" mkdir "%REPORT_DIR%"
py -3.11 -B MuJoCo_G1_Controller\scripts\g1_bimanual_runtime.py --mode report --latest ^
  --json-output "%REPORT_DIR%\session_%STAMP%.json" ^
  --markdown-output "%REPORT_DIR%\session_%STAMP%.md" %*
set "RC=%ERRORLEVEL%"
echo.
echo Report saved under %REPORT_DIR%
exit /b %RC%
