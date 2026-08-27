@echo off
setlocal
set "SCRIPT=%~dp0DETECT_G1_NETWORK_ADMIN.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p=Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%SCRIPT%""'; exit $p.ExitCode"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo [ERROR] G1 network capture failed with code %RC%.
    echo [ACTION] Connect the Ethernet adapter and G1, approve the administrator prompt, and retry.
    echo [ACTION] If it still fails, run DETECT_G1_NETWORK_ADMIN.ps1 from an administrator PowerShell and inspect the pktmon error.
)
endlocal & exit /b %RC%
