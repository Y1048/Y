@echo off
set "SCRIPT=%~dp0RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%SCRIPT%""'"
