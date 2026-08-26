@echo off
set "SCRIPT=%~dp0CONFIGURE_G1_ETHERNET_ADMIN.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%SCRIPT%""'"
