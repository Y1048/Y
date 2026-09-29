@echo off
"%~dp0..\runtime\python\python.exe" -I -B "%~dp0G1_PORTABLE.py" bimanual-demo %*
exit /b %ERRORLEVEL%
