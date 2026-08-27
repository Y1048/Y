@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "UNITY_EXE=C:\Program Files\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe"
set "UNITY_PROJECT=%CD%\Unity_G1_VR"
set "RESULT_DIR=%CD%\logs\test_results"
set "RESULT_PATH=%RESULT_DIR%\g1_mink_fk_parity.log"
set "REFERENCE_PATH=%CD%\logs\runtime\g1_mink_fk_reference.json"
if not exist "%RESULT_DIR%" mkdir "%RESULT_DIR%"
type nul > "%RESULT_PATH%"

echo ============================================================
echo   G1 Unity vs MuJoCo Wrist-Yaw FK Parity Test
echo   - Unity Editor must be closed for batch validation
echo   - No Quest required
echo   - No robot command
echo ============================================================
echo.

if not exist "%UNITY_EXE%" (
    echo [ERROR] Unity 6000.5.4f1 was not found:
    echo         %UNITY_EXE%
    echo [ERROR] Unity 6000.5.4f1 was not found: %UNITY_EXE%>> "%RESULT_PATH%"
    echo [ACTION] Install Unity 6000.5.4f1 or update UNITY_EXE in this BAT.
    echo [ACTION] Install Unity 6000.5.4f1 or update UNITY_EXE in this BAT.>> "%RESULT_PATH%"
    goto :fail
)

powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process -Filter \"Name='Unity.exe'\" | Where-Object { $_.CommandLine -like '*Unity_G1_VR*' }; if ($p) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [BLOCKED] Unity_G1_VR is currently open.
    echo [ACTION] Save your work, close Unity completely, then run this test again.
    echo [BLOCKED] Unity_G1_VR is currently open.>> "%RESULT_PATH%"
    echo [ACTION] Save your work, close Unity_G1_VR completely, then rerun this BAT.>> "%RESULT_PATH%"
    set "RC=2"
    goto :finish
)

echo [1/2] Exporting MuJoCo right_wrist_yaw_link FK samples...
py -3.11 MuJoCo_G1_Controller\scripts\export_g1_mink_fk_reference.py >> "%RESULT_PATH%" 2>&1
if errorlevel 1 goto :fail

echo.
echo [2/2] Validating Unity G1 FK against MuJoCo...
"%UNITY_EXE%" -batchmode -quit -projectPath "%UNITY_PROJECT%" -executeMethod G1MinkFkParityValidator.ValidateBatch -logFile - >> "%RESULT_PATH%" 2>&1
if errorlevel 1 goto :fail

echo.
echo [PASS] Unity and MuJoCo wrist-yaw FK parity passed.
echo [PASS] Unity and MuJoCo wrist-yaw FK parity passed.>> "%RESULT_PATH%"
set "RC=0"
goto :finish

:fail
echo.
echo [FAIL] G1 wrist-yaw FK parity test failed.
echo [FAIL] G1 wrist-yaw FK parity test failed.>> "%RESULT_PATH%"
echo [ACTION] Open %RESULT_PATH%, find the first Unity error or nonzero FK sample, fix it, and rerun this BAT.
echo [ACTION] Find the first Unity error or nonzero FK sample above, fix it, and rerun this BAT.>> "%RESULT_PATH%"
set "RC=1"

:finish
echo.
type "%RESULT_PATH%"
echo Result saved to: %RESULT_PATH%
echo FK reference saved to: %REFERENCE_PATH%
echo.
pause
endlocal & exit /b %RC%
