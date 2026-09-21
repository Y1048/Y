@echo off
setlocal
cd /d "%~dp0.."
title PC to G1 observation audit - NO MOTOR OUTPUT
py -3.11 -B tools\G1_INPUT_RECEIVE_AUDIT.py send %*
if errorlevel 1 pause
endlocal
