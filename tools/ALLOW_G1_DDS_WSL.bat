@echo off
setlocal
set "SCRIPT=%~dp0ALLOW_G1_DDS_WSL_ADMIN.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p=Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%SCRIPT%""'; exit $p.ExitCode"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo [ERROR] G1 DDS firewall configuration for WSL failed with code %RC%.
    echo [ACTION] Verify exactly one G1 ASIX adapter; use -InterfaceIndex in the PS1 if multiple exist.
    echo [ACTION] If ROLLBACK FAILED is shown, inspect both local G1 DDS rules before retrying.
    echo [ACTION] If it still fails, run ALLOW_G1_DDS_WSL_ADMIN.ps1 from an administrator PowerShell to see the detailed error.
)
endlocal & exit /b %RC%
