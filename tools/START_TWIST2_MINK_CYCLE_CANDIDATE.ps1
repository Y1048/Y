param(
 [ValidateSet('Check','All','Input','Relay','Robot','Camera')][string]$Mode='Check',
 [ValidateSet('yesterday','today')][string]$Profile='yesterday',
 [string]$RelayToken='', [switch]$Preview, [switch]$PdSweep, [switch]$HandoffOnly
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$expectedRobotSha256='28c16d62671445571d04711bb1a2e881a070cdf01703b171faa4c1ac36ecb1e7'
$robotBlockedReason='BLOCKED after backward-balance PD-sweep abort. Do not start Robot/All, including -PdSweep, until the run is reviewed.'
if($PdSweep -and $HandoffOnly){throw 'Choose either PdSweep or HandoffOnly'}
if($Preview -and $Mode -ne 'All'){throw 'Preview requires All'}
if($Mode -eq 'Check'){
 Write-Host "CANDIDATE profile=$Profile; pdSweep=$PdSweep; pinch or Select/B returns through safe waypoint while TWIST2 remains the command owner."
 Write-Host 'yesterday: 0.7 rad/s, 10 deg/s^2; today: arm90/wrist180 deg/s, 60 deg/s^2.'
 Write-Host "Last confirmed G1 SHA256 (remote rebuild NOT reverified): $expectedRobotSha256"
 Write-Host 'Separate G1 directory /home/unitree/g1_mink_cycle_compare_20260909; verified-Regular-handoff candidate; no damping output; no process started.'
 if($HandoffOnly){
  Write-Host 'Handoff-only: captured upper-body references, 1 s capture and 4 s TWIST2 leg blend; no arm trajectory or UDP input. NOT a whole-body no-motion test.'
 }elseif($PdSweep){
  Write-Host 'PD-sweep completion requests verified Regular handoff; no physical run is authorized.'
 }else{
  Write-Host 'UDP pinch/Select/B/Ctrl+C/Q returns to hold; automatic Regular handoff stays disabled for UDP.'
 }
 Write-Host 'Robot/All remain blocked, including HandoffOnly. Offline tests do not approve physical operation.'
 Write-Host $robotBlockedReason -ForegroundColor Red
 exit 0
}
if($Mode -eq 'All' -or $Mode -eq 'Robot'){throw $robotBlockedReason}
if(!$RelayToken -and $Mode -eq 'All'){$RelayToken=[guid]::NewGuid().ToString('N')}
if($RelayToken -notmatch '^[A-Za-z0-9]{16,128}$'){throw 'Invalid token'}
if($Mode -eq 'All'){
$childPowerShell=(Get-Command powershell.exe -CommandType Application -ErrorAction Stop).Source
 $plans=@(foreach($child in @('Input','Relay','Camera','Robot')){
  $sweepArg=if($PdSweep){' -PdSweep'}else{''}
  [pscustomobject]@{FilePath=$childPowerShell;Arguments=(('-NoProfile -NoExit -ExecutionPolicy Bypass -File "{0}" -Mode {1} -Profile {2} -RelayToken {3}' -f $PSCommandPath,$child,$Profile,$RelayToken)+$sweepArg);WorkingDirectory=$root}
 })
 if($Preview){$plans | ConvertTo-Json;exit 0}
 $occupied=@(Get-NetUDPEndpoint -ErrorAction Stop | Where-Object LocalPort -in 5005,5008,5015)
 if($occupied.Count){$occupied | Select-Object LocalPort,OwningProcess | Format-Table | Out-Host;throw 'Close existing Input/Relay first. No process stopped.'}
 foreach($plan in $plans){Start-Process -FilePath $plan.FilePath -ArgumentList $plan.Arguments -WorkingDirectory $plan.WorkingDirectory -WindowStyle Normal | Out-Null}
 exit 0
}
$Host.UI.RawUI.WindowTitle="TWIST2 cycle CANDIDATE - $Mode - $Profile"
$consoleLogDir=Join-Path $root 'logs/test_results/cycle_console'
New-Item -ItemType Directory -Force -Path $consoleLogDir | Out-Null
$consoleStamp=(Get-Date).ToString('yyyyMMdd_HHmmss_fffffff')
$consoleLog=Join-Path $consoleLogDir ("{0}_{1}_{2}.log" -f $consoleStamp,$Mode.ToLowerInvariant(),$Profile)
Start-Transcript -Path $consoleLog -Force | Out-Null
Write-Host "[CONSOLE LOG] $consoleLog"
if($Mode -eq 'Input'){
 $env:G1_TWIST2_KEYBOARD_RATE='1';$env:G1_USE_HARDWARE_INITIAL_STATE='0'
 $env:G1_MINK_SIM_MUJOCO_ROOT="$root/logs/diagnostics/mujoco_versions/3.12.0"
 $env:G1_CYCLE_RELAY_TOKEN=$RelayToken
 & py -3.11 -B "$root/MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live_entry.py" --ik-solver vanilla --live-cycle-candidate --upstream-mink-collision --speed-profile $Profile
 exit $LASTEXITCODE
}
if($Mode -eq 'Relay'){
 & py -3.11 -B "$root/hardware/g1_arm_bridge/gate7_mink_cycle_relay.py" --relay-token $RelayToken --profile $Profile --record "$root/logs/test_results/cycle_packets_$((Get-Date).ToString('yyyyMMdd_HHmmss_fffffff')).jsonl"
 exit $LASTEXITCODE
}
if($Mode -eq 'Camera'){
 & "$PSScriptRoot/START_TWIST2_MINK_UDP.ps1" -Mode Camera
 exit $LASTEXITCODE
}
Write-Host 'ROBOT WINDOW: Q returns the arm to safe hold; it does not end the full-body owner.' -ForegroundColor Yellow
Write-Host 'No verified live shutdown exists. Do not close this window while the controller owns LowCmd.' -ForegroundColor Yellow
$trialFlag=if($HandoffOnly){'--handoff-only-trial'}elseif($PdSweep){'--pd-sweep-trial'}else{'--udp-right-arm'}
$command="cd /home/unitree/g1_mink_cycle_compare_20260909 && echo '$expectedRobotSha256  build/g1_twist2_mink_cycle_trial' | sha256sum -c - && G1_MINK_SPEED_PROFILE=$Profile G1_VR_BIND_IPV4=192.168.123.164 G1_VR_SOURCE_IPV4=192.168.123.99 G1_VR_UDP_PORT=5014 G1_VR_RELAY_TOKEN=$RelayToken ./build/g1_twist2_mink_cycle_trial eth0 /home/unitree/twist2_deploy/twist2_1017_20k_torchscript.pt --enable-actuation --policy-seconds 300 $trialFlag"
& ssh.exe -tt -o StrictHostKeyChecking=yes -o ConnectTimeout=5 unitree@192.168.123.164 $command
exit $LASTEXITCODE
