@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo TWIST2 RIGHT ARM - LOCAL OFFLINE VERIFICATION ONLY
echo No G1 connection / no DDS publisher / no robot command
echo ============================================================
py -3.11 "%~dp0verify_offline.py"
set "test_result=%errorlevel%"
if not "%test_result%"=="0" (
    echo [FAIL] Offline verification failed.
    echo [ACTION] Fix the first error above. This test uses local WSL Ubuntu and g++.
    echo [ACTION] Do not deploy to G1 or enable physical output to resolve this error.
) else (
    echo [PASS] Offline contracts passed. This is NOT physical-test authorization.
)
pause
exit /b %test_result%
