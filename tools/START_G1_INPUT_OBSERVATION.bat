@echo off
setlocal
cd /d "%~dp0.."
py -3.11 -B tools\G1_INPUT_OBSERVATION_LAUNCH.py %*
if errorlevel 1 pause
endlocal
