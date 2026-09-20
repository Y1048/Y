@echo off
rem Resolve only; never start Unity. Call inside SETLOCAL DisableDelayedExpansion.
rem Keep 6000.5.4f1 pinned; a valid caller override has highest priority.
rem Remote launch shells can omit variables required by UPM 9.x. Fill only the
rem current CMD environment; never write machine/user environment settings.
if not defined PROGRAMDATA if defined SystemDrive if exist "%SystemDrive%\ProgramData\" set "PROGRAMDATA=%SystemDrive%\ProgramData"
if not defined ALLUSERSPROFILE if defined PROGRAMDATA set "ALLUSERSPROFILE=%PROGRAMDATA%"
if not defined TEMP if defined LOCALAPPDATA if exist "%LOCALAPPDATA%\Temp\" set "TEMP=%LOCALAPPDATA%\Temp"
if not defined TMP if defined TEMP set "TMP=%TEMP%"
set "UNITY_EXE_SOURCE="
if not defined UNITY_EXE goto :program_files
if not exist "%UNITY_EXE%" goto :program_files
if exist "%UNITY_EXE%\" goto :program_files
set "UNITY_EXE_SOURCE=environment"
goto :resolved

:program_files
set "UNITY_EXE="
if not defined ProgramFiles goto :user_profile
if not exist "%ProgramFiles%\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe" goto :user_profile
if exist "%ProgramFiles%\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe\" goto :user_profile
set "UNITY_EXE=%ProgramFiles%\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe"
set "UNITY_EXE_SOURCE=ProgramFiles"
goto :resolved

:user_profile
if not defined USERPROFILE goto :missing
if not exist "%USERPROFILE%\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe" goto :missing
if exist "%USERPROFILE%\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe\" goto :missing
set "UNITY_EXE=%USERPROFILE%\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe"
set "UNITY_EXE_SOURCE=USERPROFILE"

:resolved
if /I "%~1"=="--check-unity-path" set UNITY_EXE
exit /b 0

:missing
if /I "%~1"=="--check-unity-path" echo [ERROR] Unity 6000.5.4f1 was not found.
exit /b 1
