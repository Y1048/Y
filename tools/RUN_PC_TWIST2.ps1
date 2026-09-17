param(
    [ValidateSet('Check', 'Readiness', 'Vr')]
    [string]$Mode = 'Check',
    [string]$RelayToken = '',
    [ValidateRange(2, 20)]
    [int]$PolicySeconds = 10
)
$ErrorActionPreference = 'Stop'
if ($Mode -eq 'Vr' -and $RelayToken -notmatch '^[a-zA-Z0-9]{16,128}$') {
    throw 'Vr requires -RelayToken with 16..128 letters/digits, shared with the relay'
}
$projectRoot = Split-Path -Parent $PSScriptRoot
$linuxRoot = & wsl.exe -e wslpath -a $projectRoot
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve the project in WSL' }
$modeArgument = '--' + $Mode.ToLowerInvariant()
if ($Mode -eq 'Vr') {
    & wsl.exe -e env "G1_VR_RELAY_TOKEN=$RelayToken" "G1_PC_POLICY_SECONDS=$PolicySeconds" bash "$($linuxRoot.Trim())/experiments/twist2_right_arm_manual/run_pc_twist2.sh" $modeArgument
} else {
    & wsl.exe -e bash "$($linuxRoot.Trim())/experiments/twist2_right_arm_manual/run_pc_twist2.sh" $modeArgument
}
exit $LASTEXITCODE
