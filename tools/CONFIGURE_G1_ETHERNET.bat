@echo off
setlocal
set "SCRIPT=%~dp0CONFIGURE_G1_ETHERNET_ADMIN.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p=Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%SCRIPT%""'; exit $p.ExitCode"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo [ERROR] G1 Ethernet configuration failed with code %RC%.
    echo [ACTION] Connect the ASIX AX88772A adapter, approve the administrator prompt, and retry.
    echo [ACTION] If it still fails, run CONFIGURE_G1_ETHERNET_ADMIN.ps1 from an administrator PowerShell and inspect the detailed error.
)
endlocal & exit /b %RC%
