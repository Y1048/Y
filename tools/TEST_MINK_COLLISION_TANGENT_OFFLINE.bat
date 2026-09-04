@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ============================================================
echo G1 MINK COLLISION-TANGENT REGRESSION - OFFLINE
echo   Replays the measured 2026-09-04 5 mm boundary pose
echo   Unitree SDK: NONE / DDS publisher: NONE / Robot command: NONE
echo ============================================================

py -3.11 -m unittest -v ^
  backend.tests.test_mink_feasible_target.FeasibleTargetTest.test_measured_collision_boundary_keeps_moving_tangentially
if errorlevel 1 goto :failed

echo.
echo [PASS] The checked local tangent policy moved along the collision boundary.
echo [PASS] The measured 5 mm validation floor was preserved.
echo Result: unittest output shown above; this test does not create a robot command.
pause
exit /b 0

:failed
echo.
echo [FAIL] The measured collision-boundary regression failed.
echo [ACTION] Keep hardware output locked and inspect the first unittest failure above.
pause
exit /b 2
