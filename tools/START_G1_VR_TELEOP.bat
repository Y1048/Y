@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv-teleop\Scripts\python.exe" (
    echo [SETUP REQUIRED] Run tools\SETUP_G1_VR_TELEOP.bat once on this PC.
    pause
    exit /b 1
)
set "G1_BIMANUAL_ENGINE_ROOT=%CD%\.venv-teleop\Lib\site-packages"
".venv-teleop\Scripts\python.exe" -B "tools\G1_VR_TELEOP_LAUNCH.py" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
endlocal & exit /b %RC%
