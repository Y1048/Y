@echo off
setlocal EnableExtensions

set "PROJECT_ROOT=%~dp0.."
set "SCRIPT=%PROJECT_ROOT%\MuJoCo_G1_Controller\scripts\replay_live_workspace.py"
set "TRACE=%PROJECT_ROOT%\Unity_G1_Quest3S\Logs\live_quest_trace.csv"

echo G1 live workspace replay diagnostic
echo ===================================
echo.

if not exist "%SCRIPT%" (
    echo [ERROR] Replay script not found:
    echo %SCRIPT%
    goto :failed
)

if not exist "%TRACE%" (
    echo [ERROR] Live Quest trace not found:
    echo %TRACE%
    echo Run Unity Play Mode with Quest tracking first.
    goto :failed
)

py -3.11 "%SCRIPT%" "%TRACE%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo Workspace replay finished with exit code %EXIT_CODE%.
) else (
    echo Workspace replay completed.
)
pause
exit /b %EXIT_CODE%

:failed
echo.
pause
exit /b 1
