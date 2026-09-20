@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0.."
echo Latest Quest-cycle VERIFY ONLY. No Unity, G1, DDS, SSH or motor output.
set "RUNTIME_ROOT=%USERPROFILE%\Desktop\G1_Teleop_Project"
if defined G1_BIMANUAL_RUNTIME_ROOT set "RUNTIME_ROOT=%G1_BIMANUAL_RUNTIME_ROOT%"
set "ENGINE_ROOT=%RUNTIME_ROOT%\logs\diagnostics\mujoco_versions\3.12.0"
for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss_fffffff"') do set STAMP=%%I
set "REPORT_DIR=logs\test_results\bimanual\reports"
if not exist "%REPORT_DIR%" mkdir "%REPORT_DIR%"
py -3.11 -B MuJoCo_G1_Controller\scripts\g1_bimanual_runtime.py ^
  --engine-root "%ENGINE_ROOT%" --mode report --latest --replay ^
  --require-quest-cycle --strict ^
  --json-output "%REPORT_DIR%\quest_cycle_%STAMP%.json" ^
  --markdown-output "%REPORT_DIR%\quest_cycle_%STAMP%.md" %*
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo QUEST CYCLE VERIFY PASS
) else (
  echo QUEST CYCLE VERIFY FAIL - inspect the newest quest_cycle report.
)
echo Report saved under %REPORT_DIR%
exit /b %RC%
