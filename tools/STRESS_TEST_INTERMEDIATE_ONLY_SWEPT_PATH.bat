@echo off
setlocal
cd /d "%~dp0.."

echo G1 INTERMEDIATE-ONLY SWEPT-PATH STRESS TEST
echo ===========================================
echo.
echo This is an offline MuJoCo diagnostic. It does not command hardware.
echo It searches for safe endpoints whose straight C-space path is unsafe.
echo Reference path uses the same production joint limits and clamping.
echo.

py -3.11 MuJoCo_G1_Controller\scripts\stress_test_intermediate_only_swept_path_v2.py %*
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
  echo [PASS] Intermediate-only swept-path stress diagnostic passed.
) else if "%RC%"=="2" (
  echo [PARTIAL PASS] No safety failures, but the target case count was not reached.
) else (
  echo [FAIL] Intermediate-only swept-path stress diagnostic failed.
)

exit /b %RC%
