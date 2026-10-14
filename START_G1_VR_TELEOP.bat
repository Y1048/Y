@echo off
setlocal
"%~dp0runtime\python\python.exe" -I -B "%~dp0tools\G1_PORTABLE.py" teleop %*
set "G1_TELEOP_EXIT=%ERRORLEVEL%"
if not "%G1_TELEOP_EXIT%"=="0" (
  echo.
  echo [G1 TELEOP FAILED] Exit code %G1_TELEOP_EXIT%. Review the error above.
  echo Logs: %~dp0logs\test_results\teleop_background
  echo A closed PC window does not prove the G1 controller stopped.
  pause
)
exit /b %G1_TELEOP_EXIT%
