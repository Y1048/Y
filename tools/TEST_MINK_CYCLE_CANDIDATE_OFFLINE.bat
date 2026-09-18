@echo off
setlocal
pushd "%~dp0.."
echo OFFLINE ONLY: builds local test consumers. No G1, SSH, WSL, SDK or publisher.
if not defined VCVARS64 set "VCVARS64=%ProgramFiles%\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
set "candidate_vcvars=%VCVARS64%"
if not exist "%candidate_vcvars%" goto failed
call "%candidate_vcvars%" >nul
if errorlevel 1 goto failed
if not exist logs\test_results mkdir logs\test_results
cl /nologo /std:c++17 /EHsc /W4 /WX experiments\twist2_right_arm_manual\test_mink_cycle_candidate_offline.cpp /Fe:logs\test_results\test_mink_cycle_candidate_offline.exe /Fo:logs\test_results\test_mink_cycle_candidate_offline.obj
if errorlevel 1 goto failed
cl /nologo /std:c++17 /EHsc /W4 /WX experiments\twist2_right_arm_manual\mink_cycle_candidate_stdio_offline.cpp /Fe:logs\test_results\mink_cycle_candidate_stdio_offline.exe /Fo:logs\test_results\mink_cycle_candidate_stdio_offline.obj
if errorlevel 1 goto failed
cl /nologo /std:c++17 /EHsc /W4 /WX experiments\twist2_right_arm_manual\test_mink_cycle_owner_offline.cpp /Fe:logs\test_results\test_mink_cycle_owner_offline.exe /Fo:logs\test_results\test_mink_cycle_owner_offline.obj
if errorlevel 1 goto failed
cl /nologo /std:c++17 /EHsc /W4 /WX experiments\twist2_right_arm_manual\test_mink_resampler_offline.cpp /Fe:logs\test_results\test_mink_resampler_offline.exe /Fo:logs\test_results\test_mink_resampler_offline.obj
if errorlevel 1 goto failed
cl /nologo /std:c++17 /EHsc /W4 /WX experiments\twist2_right_arm_manual\mink_resampler_batch_offline.cpp /Fe:logs\test_results\mink_resampler_batch_offline.exe /Fo:logs\test_results\mink_resampler_batch_offline.obj
if errorlevel 1 goto failed
cl /nologo /std:c++17 /EHsc /W4 /WX experiments\twist2_right_arm_manual\test_mink_resampled_owner_offline.cpp /Fe:logs\test_results\test_mink_resampled_owner_offline.exe /Fo:logs\test_results\test_mink_resampled_owner_offline.obj
if errorlevel 1 goto failed
cl /nologo /std:c++17 /EHsc /W4 /WX experiments\twist2_right_arm_manual\test_mink_policy_hold_offline.cpp /Fe:logs\test_results\test_mink_policy_hold_offline.exe /Fo:logs\test_results\test_mink_policy_hold_offline.obj
if errorlevel 1 goto failed
logs\test_results\test_mink_policy_hold_offline.exe
if errorlevel 1 goto failed
logs\test_results\test_mink_resampled_owner_offline.exe
if errorlevel 1 goto failed
logs\test_results\test_mink_resampler_offline.exe
if errorlevel 1 goto failed
logs\test_results\test_mink_cycle_owner_offline.exe
if errorlevel 1 goto failed
logs\test_results\test_mink_cycle_candidate_offline.exe
if errorlevel 1 goto failed
py -3.11 -B experiments\twist2_right_arm_manual\replay_mink_cycle_candidate_offline.py
if errorlevel 1 goto failed
echo Geometry audit uses the existing isolated MuJoCo 3.12.0; live runtime is unchanged.
py -3.11 -B experiments\twist2_right_arm_manual\audit_mink_resampler_geometry.py --isolated-mujoco
if errorlevel 1 goto failed
py -3.11 -B -c "import sys,unittest; sys.path.insert(0,'logs/diagnostics/mujoco_versions/3.12.0'); r=unittest.TextTestRunner().run(unittest.defaultTestLoader.discover('backend/tests',pattern='test_upstream_mink_tracking.py')); sys.exit(not r.wasSuccessful())"
if errorlevel 1 goto failed
popd
exit /b 0
:failed
echo Offline candidate validation failed. Nothing was deployed.
popd
exit /b 1
