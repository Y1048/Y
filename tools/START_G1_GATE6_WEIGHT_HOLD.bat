@echo off
setlocal
cd /d "%~dp0.."
echo ============================================================
echo G1 FIXED-POSE HOLD - select ONE physical trial
echo No automatic progression. Review each result before the next.
echo ============================================================
py -3.11 -B hardware\g1_arm_bridge\gate6_weight_hold_trial.py
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo [ACTION] Read the first error and its result folder. Do not retry after abnormal motion.
pause
exit /b %RC%
