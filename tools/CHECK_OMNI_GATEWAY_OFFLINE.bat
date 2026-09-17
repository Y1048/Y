@echo off
setlocal
cd /d "%~dp0.."
py -3.11 -B hardware\g1_arm_bridge\test_g1_omni_gateway_e2e.py
if errorlevel 1 (
  echo [FAILED] Omni Gateway offline end-to-end test
  exit /b 1
)
py -3.11 -B hardware\g1_arm_bridge\test_run_omni_fake_g1_integration.py
if errorlevel 1 (
  echo [FAILED] One-click fake G1 integration harness test
  exit /b 1
)
echo [PASS] Omni Gateway offline end-to-end test; no G1 SDK, DDS, or motor output
endlocal
