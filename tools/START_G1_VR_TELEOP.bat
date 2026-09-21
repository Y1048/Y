@echo off
setlocal
cd /d "%~dp0.."
set "DEP_CHECK="
for %%A in (%*) do if /I "%%~A"=="--check-only" set "DEP_CHECK=--check-only"
if exist ".venv-teleop\Scripts\python.exe" (
    ".venv-teleop\Scripts\python.exe" -I -B tools\g1_teleop_dependencies.py %DEP_CHECK%
) else (
    py -3.11 -I -B tools\g1_teleop_dependencies.py %DEP_CHECK%
)
if errorlevel 1 (
    echo [START BLOCKED] Dependency check failed. No teleop workers started.
    echo Check network access and Python 3.11 x64, then run this BAT again.
    pause
    exit /b 1
)
set "G1_BIMANUAL_ENGINE_ROOT=%CD%\.venv-teleop\Lib\site-packages"
".venv-teleop\Scripts\python.exe" -B "tools\G1_VR_TELEOP_LAUNCH.py" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
endlocal & exit /b %RC%
