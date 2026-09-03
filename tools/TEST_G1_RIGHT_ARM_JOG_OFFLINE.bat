@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TIMESTAMP=%%T"
set "RESULT_PATH=%CD%\logs\test_results\g1_right_arm_jog_offline_%TIMESTAMP%.txt"
if not exist "%CD%\logs\test_results" mkdir "%CD%\logs\test_results"

echo ============================================================ > "%RESULT_PATH%"
echo G1 right-arm 7-DoF jog OFFLINE validation >> "%RESULT_PATH%"
echo - No Unitree SDK publisher >> "%RESULT_PATH%"
echo - No DDS command entity >> "%RESULT_PATH%"
echo - No robot command >> "%RESULT_PATH%"
echo ============================================================ >> "%RESULT_PATH%"

py -3.11 hardware\g1_arm_bridge\g1_right_arm_jog.py --validate-only >> "%RESULT_PATH%" 2>&1
if errorlevel 1 goto :failed

py -3.11 hardware\g1_arm_bridge\test_right_arm_jog_contract.py >> "%RESULT_PATH%" 2>&1
if errorlevel 1 goto :failed

py -3.11 hardware\g1_arm_bridge\test_g1_right_arm_jog.py >> "%RESULT_PATH%" 2>&1
if errorlevel 1 goto :failed

py -3.11 hardware\g1_arm_bridge\test_validate_right_arm_jog_collision_path.py >> "%RESULT_PATH%" 2>&1
if errorlevel 1 goto :failed

echo [PASS] Right-arm 7-DoF jog offline contract passed.>> "%RESULT_PATH%"
type "%RESULT_PATH%"
echo.
echo Result saved to: %RESULT_PATH%
pause
exit /b 0

:failed
echo [FAIL] Right-arm 7-DoF jog offline contract failed.>> "%RESULT_PATH%"
echo [ACTION] Read the first traceback or FAIL line above.>> "%RESULT_PATH%"
type "%RESULT_PATH%"
echo.
echo Result saved to: %RESULT_PATH%
echo [ACTION] Do not run the physical right-arm jog until this test passes.
pause
exit /b 1
