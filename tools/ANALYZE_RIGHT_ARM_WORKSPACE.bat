@echo off
setlocal
cd /d "%~dp0.."

if "%~1"=="" (
    set SAMPLES=200000
) else (
    set SAMPLES=%~1
)

echo G1 right-arm workspace analysis
echo --------------------------------
echo Samples: %SAMPLES%
echo.

python MuJoCo_G1_Controller\scripts\analyze_right_arm_workspace.py --samples %SAMPLES%
if errorlevel 1 (
    echo.
    echo Workspace analysis failed.
    exit /b 1
)

echo.
echo Results:
echo   logs\workspace\right_arm_workspace.npz
echo   logs\workspace\right_arm_workspace_summary.json
