@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Start-Process PowerShell -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%~dp0ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1""'; exit $p.ExitCode"
if errorlevel 1 (
    echo [ERROR] UDP 5007/5009 firewall configuration was not completed.
    echo [ACTION] Approve the administrator prompt, then run this BAT again.
    echo [ACTION] If it still fails, open PowerShell as administrator and run ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1 directly.
    pause
    exit /b 1
)
echo G1 LowState UDP 5007/5009 firewall rule is configured.
pause
endlocal
