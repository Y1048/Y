@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process PowerShell -Verb RunAs -Wait -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%~dp0ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1""'"
if errorlevel 1 (
    echo [ERROR] UDP 5007 firewall configuration was not completed.
    pause
    exit /b 1
)
echo G1 LowState UDP 5007 firewall rule is configured.
pause
endlocal
