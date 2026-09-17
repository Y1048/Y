@echo off
setlocal EnableExtensions
rem Shared feedback loop and standard 6D Mink QP; not a hardware launcher.
call "%~dp0START_VR_HAND_TO_MUJOCO.bat" --standard-mink --mujoco312
exit /b %errorlevel%
