@echo off
setlocal
echo This starts one continuous TWIST2 owner: PD Kp 40,48,56 sweep, then VR udp_ready.
echo Keep the Robot window open. Review the Robot summary and type P yourself.
echo Select/B, Q, pinch, and Ctrl+C do not terminate the owner or restore AI.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_TWIST2_MINK_CYCLE_CANDIDATE.ps1" -Mode All -Profile today -PdSweep
