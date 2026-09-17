@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Start-Process PowerShell -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%~dp0ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1""'; exit $p.ExitCode"
if errorlevel 1 (
    echo [ERROR] UDP 5007/5009 firewall configuration was not completed.
    echo [ACTION] Read the first PowerShell error; verify exactly one G1 ASIX adapter is connected.
    echo [ACTION] If multiple exist, run the PS1 as administrator with -InterfaceIndex using the G1 adapter index.
    echo [ACTION] This rule allows only the G1 Ethernet subnet, not Wi-Fi or arbitrary WSL addresses.
    pause
    exit /b 1
)
echo G1 LowState UDP 5007/5009 firewall rule is configured.
pause
endlocal
