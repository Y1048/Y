@echo off
setlocal
cd /d "%~dp0"
"%~dp0runtime\python\python.exe" -I -B "%~dp0tools\G1_CAMERA_PREVIEW.py" %*
if errorlevel 1 pause
