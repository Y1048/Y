@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo G1 SWEPT-PATH COLLISION GUARD STRESS TEST
echo ============================================================
echo.
echo This is MuJoCo-only. It does NOT command hardware or use VR UDP.
echo Default: 2500 runtime-envelope + 750 adversarial paths.
echo Dense reference scan: 0.05 deg joint spacing.
echo.

py -3.11 MuJoCo_G1_Controller\scripts\stress_test_swept_path_guard.py %*
set EXITCODE=%ERRORLEVEL%

echo.
if "%EXITCODE%"=="0" (
  echo [PASS] Swept-path guard stress diagnostic passed.
) else if "%EXITCODE%"=="2" (
  echo [INCONCLUSIVE] No clipping case was generated. Increase adversarial trials.
) else (
  echo [FAIL] Swept-path guard stress diagnostic found a safety failure.
)
echo.
echo Report: logs\diagnostics\swept_path_stress.json
exit /b %EXITCODE%
