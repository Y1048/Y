@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "UNITY_EXE=C:\Program Files\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe"
set "UNITY_PROJECT=%CD%\Unity_G1_VR"

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
    goto :fail
)

powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process -Filter \"Name='Unity.exe'\" | Where-Object { $_.CommandLine -like '*Unity_G1_VR*' }; if ($p) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [BLOCKED] Unity_G1_VR is currently open.
    echo           Save your work, close Unity completely, then run this test again.
    exit /b 2
)

echo [1/2] Exporting MuJoCo right_wrist_yaw_link FK samples...
py -3.11 MuJoCo_G1_Controller\scripts\export_g1_mink_fk_reference.py
if errorlevel 1 goto :fail

echo.
echo [2/2] Validating Unity G1 FK against MuJoCo...
"%UNITY_EXE%" -batchmode -quit -projectPath "%UNITY_PROJECT%" -executeMethod G1MinkFkParityValidator.ValidateBatch -logFile -
if errorlevel 1 goto :fail

echo.
echo [PASS] Unity and MuJoCo wrist-yaw FK parity passed.
goto :end

:fail
echo.
echo [FAIL] G1 wrist-yaw FK parity test failed.
exit /b 1

:end
endlocal
exit /b 0
