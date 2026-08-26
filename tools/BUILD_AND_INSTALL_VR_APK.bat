@echo off
setlocal

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "PROJECT_DIR=%PROJECT_ROOT%\Unity_G1_VR"
set "UNITY_EXE=C:\Program Files\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe"
set "ADB_EXE=C:\Program Files\Meta Quest Developer Hub\resources\bin\adb.exe"
set "APK_PATH=%PROJECT_ROOT%\Builds\G1TeleopVR.apk"
set "LOG_DIR=%PROJECT_ROOT%\logs\unity"
set "LOG_PATH=%LOG_DIR%\unity_vr_apk_build.log"

if not exist "%UNITY_EXE%" (
    echo Unity 6000.5.4f1 was not found:
    echo %UNITY_EXE%
    pause
    exit /b 1
)

if not exist "%ADB_EXE%" (
    echo Meta Quest Developer Hub adb was not found:
    echo %ADB_EXE%
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
    echo Unity APK build failed. Open the log below:
    echo %LOG_PATH%
    pause
    exit /b 1
)

if not exist "%APK_PATH%" (
    echo.
    echo APK was not created:
    echo %APK_PATH%
    pause
    exit /b 1
)

echo.
echo Checking Quest connection...
"%ADB_EXE%" devices

echo.
echo Installing APK to Quest...
"%ADB_EXE%" install -r "%APK_PATH%"
if not %errorlevel%==0 (
    echo.
    echo APK install failed. Check USB debugging authorization and adb devices.
    pause
    exit /b 1
)

echo.
echo Done. In Quest, open Apps > Unknown Sources > G1 Teleop VR.
echo.
pause
