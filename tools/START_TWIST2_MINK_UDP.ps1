param(
 [ValidateSet('All','Check','Input','Relay','Robot','Camera')][string]$Mode='Check',
 [string]$RelayToken='',
 [switch]$Preview
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
if($Preview -and $Mode -ne 'All'){throw '-Preview requires -Mode All.'}
if($Mode -eq 'All') {
 if(!$RelayToken){$RelayToken=[guid]::NewGuid().ToString('N')}
 if($RelayToken -notmatch '^[A-Za-z0-9]{16,128}$'){throw 'Invalid relay token.'}
 $plans=@(foreach($childMode in @('Input','Relay','Camera','Robot')) {
  $arguments='-NoProfile -NoExit -ExecutionPolicy Bypass -File "{0}" -Mode {1}' -f $PSCommandPath,$childMode
  if($childMode -in @('Relay','Robot')){$arguments+=' -RelayToken '+$RelayToken}
  [pscustomobject]@{Mode=$childMode; FilePath="$PSHOME\powershell.exe"; Arguments=$arguments; WorkingDirectory=$root}
 })
 if($Preview){$plans | ConvertTo-Json; exit 0}
 $occupied=@(Get-NetUDPEndpoint -ErrorAction Stop | Where-Object LocalPort -in 5005,5008)
 if($occupied.Count) {
  $occupied | Select-Object LocalAddress,LocalPort,OwningProcess | Format-Table | Out-Host
  throw 'UDP 5005/5008 already in use. Close the existing Mink/relay window before starting All. No process was stopped or launched.'
 }
 foreach($plan in $plans) {
  Start-Process -FilePath $plan.FilePath -ArgumentList $plan.Arguments -WorkingDirectory $plan.WorkingDirectory -WindowStyle Normal | Out-Null
 }
 Write-Host 'Opened Input, Relay, Camera and Robot windows. Relay/Robot share one token. Camera feeds Unity PiP on TCP 5011. Robot requires SSH login and manual P/R1; no key is sent automatically.'
 exit 0
}
$Host.UI.RawUI.WindowTitle="TWIST2 Mink UDP - $Mode"
if($Mode -eq 'Check') {
 Get-NetUDPEndpoint -ErrorAction SilentlyContinue | Where-Object LocalPort -in 5005,5008,5014 | Select-Object LocalAddress,LocalPort,OwningProcess
 Write-Host 'Input/Robot live targets: max 0.7 rad/s, 10 deg/s^2; initial pose 0.08 rad/s. Stop/freeze overrides acceleration smoothing. Relay: localhost:5008 -> G1:5014. No process started.'
 Write-Host 'Camera: existing read-only VideoClient bridge -> Unity TCP 5011. Start Unity Play to display PiP.'
 exit 0
}
if($Mode -eq 'Input') {
 $env:G1_TWIST2_KEYBOARD_RATE='1'
 $env:G1_USE_HARDWARE_INITIAL_STATE='0'
 & py -3.11 -B "$root/MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live_entry.py" --ik-solver vanilla --collision-profile hardware-guarded --disable-gate7-simulation-feedback
 exit $LASTEXITCODE
}
if($Mode -eq 'Camera') {
 & wsl.exe -d Ubuntu -- bash -lc "pgrep -f '[g]1_camera_tcp_bridge.py' >/dev/null"
 if($LASTEXITCODE -eq 0){Write-Host 'Camera bridge already running; keeping existing process.'; exit 0}
 if($LASTEXITCODE -ne 1){throw 'Could not inspect the existing WSL camera bridge.'}
 & "$root/tools/START_G1_CAMERA_TO_UNITY.bat"
 exit $LASTEXITCODE
}
if($RelayToken -notmatch '^[A-Za-z0-9]{16,128}$'){throw 'Relay requires -RelayToken with 16..128 letters/digits, identical to G1.'}
if($Mode -eq 'Robot') {
 $command = "cd /home/unitree/g1_vr_07_10deg_trial_20260908 && G1_VR_BIND_IPV4=192.168.123.164 G1_VR_SOURCE_IPV4=192.168.123.99 G1_VR_UDP_PORT=5014 G1_VR_RELAY_TOKEN=$RelayToken ./build/g1_twist2_mink_udp_trial eth0 /home/unitree/twist2_deploy/twist2_1017_20k_torchscript.pt --enable-actuation --policy-seconds 300 --udp-right-arm"
 & ssh.exe -tt -o StrictHostKeyChecking=yes -o ConnectTimeout=5 unitree@192.168.123.164 $command
 exit $LASTEXITCODE
}
& py -3.11 -B "$root/hardware/g1_arm_bridge/gate7_mink_wsl_relay.py" --target-host 192.168.123.164 --target-port 5014 --relay-token $RelayToken
exit $LASTEXITCODE
