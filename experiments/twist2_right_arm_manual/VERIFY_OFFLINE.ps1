$ErrorActionPreference = 'Stop'
$vcvars64 = $env:VCVARS64
if ([string]::IsNullOrWhiteSpace($vcvars64)) {
    $vcvars64 = Join-Path $env:ProgramFiles 'Microsoft Visual Studio/18/Community/VC/Auxiliary/Build/vcvars64.bat'
}
if (-not (Test-Path -LiteralPath $vcvars64 -PathType Leaf)) {
    throw 'Visual Studio vcvars64.bat was not found. Set VCVARS64 before calling this script.'
}
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Push-Location $root
try {
    $expected = 'E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F'
    if ((Get-FileHash experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp).Hash -ne $expected) {
        throw 'Physical reference changed; review before continuing.'
    }
    foreach ($name in @('test_state_watchdog','test_upper_target_offline','test_offline_writer_study','test_offline_owner','test_owner_startup','test_offline_dispatch','test_owner_torque_fade','test_native_vr_policy_adapter','owner_policy_stdio')) {
        $command = 'call "' + $vcvars64 + '" >nul && cl /nologo /std:c++17 /EHsc /W4 /WX /Ilogs\test_results /Fe:logs\test_results\' + $name + '.exe /Fo:logs\test_results\' + $name + '.obj experiments\twist2_right_arm_manual\' + $name + '.cpp'
        & cmd.exe /d /c $command
        if ($LASTEXITCODE -ne 0) { throw "Build failed: $name" }
    }
    & .\logs\test_results\test_state_watchdog.exe
    if ($LASTEXITCODE -ne 0) { throw 'Watchdog failed' }
    & .\logs\test_results\test_offline_writer_study.exe
    if ($LASTEXITCODE -ne 0) { throw 'Writer study failed' }
    & py -3.11 -m pytest backend/tests/test_offline_owner.py backend/tests/test_seed_window_comparison.py backend/tests/test_lowstate_mink_seed.py experiments/twist2_right_arm_manual/test_cpp_upper_target.py experiments/twist2_right_arm_manual/test_cpp_input_tick.py -q
    if ($LASTEXITCODE -ne 0) { throw 'Regression failed' }
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
    & py -3.11 experiments/twist2_right_arm_manual/replay_cpp_input_tick.py logs/test_results/twist2_vr_shadow_20260907_175950_1b96b661/samples.jsonl --output-dir "logs/test_results/twist2_preflight_$stamp"
    if ($LASTEXITCODE -ne 0) { throw 'Saved Quest replay failed' }
    Write-Output 'OFFLINE CHECKS PASSED. Hardware output remains unauthorized; no robot IO was started.'
} finally { Pop-Location }
