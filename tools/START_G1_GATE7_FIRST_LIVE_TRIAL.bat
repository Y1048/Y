@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo G1 GATE 7 FIRST LIVE VR TRIAL - PHYSICAL OUTPUT
echo   Separate profile: weight 1.0, 3 degree start-relative limit
echo   10/25 deg/s joint velocity, 20 second maximum duration
echo ============================================================
echo [SAFETY] This launcher remains locked until its two config files are
echo [SAFETY] explicitly reviewed and authorized for one physical run.
echo.

call "%CD%\tools\START_G1_GATE7_LIVE_HARDWARE.bat" --first-live
set "TRIAL_RC=%ERRORLEVEL%"

py -3.11 -c "from pathlib import Path; p=Path(r'%CD%\config\g1_gate7_first_live_hardware_output.json'); s=p.read_text(encoding='utf-8'); old=chr(34)+'hardware_output_authorized'+chr(34)+': true'; new=chr(34)+'hardware_output_authorized'+chr(34)+': false'; assert old in s or new in s, 'first-live authorization field is missing'; p.write_text(s.replace(old, new, 1), encoding='utf-8') if old in s else None"
if errorlevel 1 (
    echo [WARNING] Automatic first-live authorization reset failed.
    echo [ACTION] Do not run another test; set hardware_output_authorized=false manually.
    exit /b 2
)

echo [LOCKED] First-live hardware authorization was restored to false.
exit /b %TRIAL_RC%
