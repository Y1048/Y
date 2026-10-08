@echo off
setlocal
cd /d "%~dp0.."
if exist "runtime\python\python.exe" (
  "runtime\python\python.exe" -B tools\quest_input_observer.py %*
) else (
  py -3 -B tools\quest_input_observer.py %*
)
pause
