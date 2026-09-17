@echo off
setlocal
cd /d "%~dp0"
echo G1 IK comparison - OFFLINE, no VR or robot connection required
echo Precomputed replay. Original IK and physical speed settings unchanged.
echo F8: toggle IK view   F9: next motion   F10: restart   F11: speed   F12: pause
echo Close the MuJoCo window to exit. On laptops, Fn may be required.
set "PLAYBACK_SPEED="
set /p "PLAYBACK_SPEED=Playback speed (0.1-16, Enter = 4): "
if not defined PLAYBACK_SPEED set "PLAYBACK_SPEED=4"
py -3.11 backend\tools\view_ik_comparison.py --playback-speed "%PLAYBACK_SPEED%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo [FAIL] IK comparison stopped.
    echo [ACTION] Read the Python error above. Do not start a physical launcher.
)
echo Result saved to: %CD%\logs\ik_visual_comparison\latest.json
pause
exit /b %RC%
