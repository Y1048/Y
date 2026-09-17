@echo off
setlocal
cd /d "%~dp0"
echo OFFLINE trajectory A/B - NO robot output, NO SDK or DDS
echo A: current stop waypoint / B: experimental through waypoint
echo F8: A/B at same time / F10: restart / F11: speed / F12: pause
echo 0-5s: reach 4cm forward / 5-20s: settle / 20-30s: wrist turn / 30-40s: hold
echo Watch shoulder and elbow travel after 20s. First calculation takes time.
py -3.11 -B -c "import sys,runpy; sys.path.insert(0,'logs/diagnostics/mujoco_versions/3.12.0'); sys.path.insert(0,'backend/tools'); import mujoco; assert mujoco.__version__=='3.12.0', 'Isolated MuJoCo 3.12 required'; sys.argv=['view_ik_comparison.py','--trajectory-ab','--case','9','--clip-seconds','40','--playback-speed','1']; runpy.run_path('backend/tools/view_ik_comparison.py',run_name='__main__')"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo [ACTION] Read the first Python error. Do not run a hardware launcher.
echo Result: %CD%\logs\experiments\trajectory_ab\latest.json
pause
exit /b %RC%
