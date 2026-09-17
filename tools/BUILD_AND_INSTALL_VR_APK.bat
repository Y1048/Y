@echo off
setlocal

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "PROJECT_DIR=%PROJECT_ROOT%\Unity_G1_VR"
set "UNITY_EXE=C:\Program Files\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe"
set "ADB_EXE=C:\Program Files\Meta Quest Developer Hub\resources\bin\adb.exe"
set "BUILD_ID="
for /f %%I in ('powershell -NoProfile -Command "[Guid]::NewGuid().ToString('N')"') do set "BUILD_ID=%%I"
if not defined BUILD_ID (
    echo [FAIL] Could not allocate a unique build ID.
    echo [ACTION] Check PowerShell availability before retrying.
    pause
    exit /b 1
)
set "APK_PATH=%PROJECT_ROOT%\Builds\%BUILD_ID%\G1TeleopVR.apk"
set "G1_APK_OUTPUT_PATH=%APK_PATH%"
set "LOG_DIR=%PROJECT_ROOT%\logs\unity"
set "LOG_PATH=%LOG_DIR%\unity_vr_apk_build_%BUILD_ID%.log"

if not exist "%UNITY_EXE%" (
    echo [ERROR] Unity 6000.5.4f1 was not found:
    echo %UNITY_EXE%
    echo [ACTION] Install Unity 6000.5.4f1 in Unity Hub, or update UNITY_EXE in this BAT.
    pause
    exit /b 1
)

if not exist "%ADB_EXE%" (
    echo [ERROR] Meta Quest Developer Hub adb was not found:
    echo %ADB_EXE%
    echo [ACTION] Install Meta Quest Developer Hub, or update ADB_EXE in this BAT.
    pause
    exit /b 1
)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo.
echo Building VR APK...
echo Project: %PROJECT_DIR%
echo Log: %LOG_PATH%
echo.

"%UNITY_EXE%" -batchmode -quit -projectPath "%PROJECT_DIR%" -executeMethod G1VRBuild.BuildApk -logFile "%LOG_PATH%"
if not %errorlevel%==0 (
    echo.
    echo [FAIL] Unity APK build failed. Open the log below:
    echo %LOG_PATH%
    echo [ACTION] Fix the first Unity compiler or build error in that log, close Unity, and run this BAT again.
    pause
    exit /b 1
)

if not exist "%APK_PATH%" (
    echo.
    echo [FAIL] APK was not created:
    echo %APK_PATH%
    echo [ACTION] Open %LOG_PATH% and verify that G1VRBuild.BuildApk completed without errors.
    pause
    exit /b 1
)

powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $p=$env:G1_APK_OUTPUT_PATH; $expected=(Get-Content -LiteralPath ($p+'.sha256') -Raw).Trim(); $h=[Security.Cryptography.SHA256]::Create(); $s=[IO.File]::OpenRead($p); try { $actual=[BitConverter]::ToString($h.ComputeHash($s)).Replace('-','') } finally { $s.Dispose(); $h.Dispose() }; if ($expected -notmatch '^[0-9A-F]{64}$' -or $actual -cne $expected) { throw 'APK hash mismatch' }"
if errorlevel 1 (
    echo [FAIL] The APK does not match this build's hash record.
    echo [ACTION] Do not install it. Check the build log and rebuild.
    echo Result saved to: %LOG_PATH%
    pause
    exit /b 1
)

echo.
echo Checking Quest connection...
"%ADB_EXE%" devices

set "DEVICE_SERIAL="
set /p "DEVICE_SERIAL=Enter the exact Quest serial shown as device above: "
powershell -NoProfile -Command "if ($env:DEVICE_SERIAL -notmatch '^[A-Za-z0-9][A-Za-z0-9_.:-]*$') { exit 1 }"
if errorlevel 1 (
    echo [FAIL] A valid explicit device serial is required.
    echo [ACTION] Rerun and select one authorized device from adb devices.
    pause
    exit /b 1
)

echo.
echo Installing APK to Quest...
"%ADB_EXE%" -s "%DEVICE_SERIAL%" install -r "%APK_PATH%"
if not %errorlevel%==0 (
    echo.
    echo [FAIL] APK install failed.
    echo [ACTION] Run "%ADB_EXE%" devices, reconnect USB, and accept USB debugging inside Quest.
    echo [ACTION] Continue only when the device is listed as device, not unauthorized or offline.
    pause
    exit /b 1
)

echo.
echo Done. In Quest, open Apps > Unknown Sources > G1 Teleop VR.
echo APK: %APK_PATH%
echo Device: %DEVICE_SERIAL%
echo Result saved to: %LOG_PATH%
echo.
pause
