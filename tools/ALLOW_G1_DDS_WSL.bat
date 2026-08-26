@echo off
set "SCRIPT=%~dp0ALLOW_G1_DDS_WSL_ADMIN.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%SCRIPT%""'"
