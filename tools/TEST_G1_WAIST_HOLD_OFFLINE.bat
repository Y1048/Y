@echo off
setlocal
cd /d "%~dp0.."
echo OFFLINE WAIST HOLD STUDY - NO WSL / DDS / ROBOT COMMAND
py -3.11 -B -m pytest hardware\g1_arm_bridge\test_waist_hold_offline.py hardware\g1_arm_bridge\test_waist_guard_offline.py hardware\g1_arm_bridge\test_arm_sdk_release_contract.py -q -p no:cacheprovider
if errorlevel 1 goto :failed
py -3.11 -B hardware\g1_arm_bridge\waist_guard_offline.py logs\physical_tests --output logs\test_results\g1_waist_guard_offline.json
if errorlevel 1 goto :failed
echo [DONE] Study only. This does not authorize physical trials.
echo Result: %CD%\logs\test_results\g1_waist_guard_offline.json
pause
exit /b 0
:failed
echo [ACTION] Read the first error above. Restore missing saved captures if reported; do not connect G1 for this test.
pause
exit /b 1
