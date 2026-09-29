@echo off
"%~dp0..\runtime\python\python.exe" -I -B "%~dp0G1_PORTABLE.py" ethernet-configure %*
exit /b %ERRORLEVEL%
