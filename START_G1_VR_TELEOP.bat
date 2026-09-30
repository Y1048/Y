@echo off
"%~dp0runtime\python\python.exe" -I -B "%~dp0tools\G1_PORTABLE.py" teleop %*
exit /b %ERRORLEVEL%
