@echo off
setlocal
cd /d "%~dp0.."

set "EXTRA_ARGS="
if /I "%~1"=="diag" (
    set "SAMPLES=1000"
    set "EXTRA_ARGS=--diagnose-only --progress-every 250"
) else if "%~1"=="" (
    set "SAMPLES=200000"
) else (
    set "SAMPLES=%~1"
)

set "PY_CMD="
py -3.11 -c "import mujoco, numpy" >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3.11"

if not defined PY_CMD (
    python -c "import mujoco, numpy" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    py -c "import mujoco, numpy" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py"
)

if not defined PY_CMD (
    echo Could not find a Python environment with both mujoco and numpy installed.
    echo Tried: py -3.11, python, py
    exit /b 1
)

echo G1 right-arm workspace analysis
echo --------------------------------
echo Python: %PY_CMD%
echo Samples: %SAMPLES%
if defined EXTRA_ARGS echo Mode: contact diagnostics only
echo.

%PY_CMD% MuJoCo_G1_Controller\scripts\analyze_right_arm_workspace.py --samples %SAMPLES% %EXTRA_ARGS%
if errorlevel 1 (
    echo.
    echo Workspace analysis failed.
    exit /b 1
)

if defined EXTRA_ARGS (
    echo.
    echo Diagnostic run complete. Review the contact-pair output above.
    exit /b 0
)

echo.
echo Results:
echo   logs\workspace\right_arm_workspace.npz
echo   logs\workspace\right_arm_workspace_summary.json
