@echo off
setlocal
cd /d "%~dp0.."
title G1 input values - READ ONLY 50 Hz
py -3.11 -B tools\PRINT_G1_INPUTS_50HZ.py %*
if errorlevel 1 pause
endlocal
