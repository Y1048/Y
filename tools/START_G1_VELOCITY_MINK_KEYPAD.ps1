param(
 [ValidateSet('All','Check','Input','ArmRelay','VelocityRelay','Camera','Robot')][string]$Mode='Check',
 [string]$RelayToken='',
 [switch]$Preview
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
if($Mode -in @('All','Robot')) {
 throw 'BLOCKED after 2026-09-15 continuous-gait fall: Robot/All disabled pending lower-body policy correction and supported physical revalidation.'
}
if($Mode -notin @('All','Check')) {
 $consoleDir=Join-Path $root 'logs\test_results\velocity_mink_console'
 New-Item -ItemType Directory -Force -Path $consoleDir|Out-Null
 $stamp=Get-Date -Format 'yyyyMMdd_HHmmss_fffffff'
 $consoleLog=Join-Path $consoleDir ("{0}_{1}.log" -f $stamp,$Mode.ToLowerInvariant())
 Start-Transcript -Path $consoleLog -Force|Out-Null
 Write-Host "[CONSOLE LOG] $consoleLog"
}
if($Mode -eq 'All') {
 if(!$RelayToken){$RelayToken=[guid]::NewGuid().ToString('N')}
 if($RelayToken -notmatch '^[A-Za-z0-9]{16,128}$'){throw 'Invalid relay token.'}
 $modes=@('Input','ArmRelay','VelocityRelay','Camera','Robot')
 $plans=@(foreach($child in $modes){
  $args='-NoProfile -NoExit -ExecutionPolicy Bypass -File "{0}" -Mode {1}' -f $PSCommandPath,$child
  if($child -in @('Input','ArmRelay','VelocityRelay','Robot')){$args+=' -RelayToken '+$RelayToken}
  [pscustomobject]@{Mode=$child;FilePath="$PSHOME\powershell.exe";Arguments=$args;WorkingDirectory=$root}
 })
 if($Preview){$plans|ConvertTo-Json;exit 0}
 $occupied=@(Get-NetUDPEndpoint -ErrorAction Stop|Where-Object LocalPort -in 5005,5008,5016)
 if($occupied.Count){$occupied|Select-Object LocalAddress,LocalPort,OwningProcess|Format-Table|Out-Host;throw 'UDP 5005/5008/5016 is already in use. No process was stopped.'}
 foreach($plan in $plans){Start-Process -FilePath $plan.FilePath -ArgumentList $plan.Arguments -WorkingDirectory $plan.WorkingDirectory -WindowStyle Normal|Out-Null}
 Write-Host 'Opened Input, arm relay, keypad relay, camera, and Robot windows.'
 Write-Host 'Latched keypad: each 8/2/4/6/7/9 press changes one axis by 0.2; key release retains it; 5 alone stops; limit +/-0.8.'
 Write-Host 'Continuous velocity policy owns the legs; keypad 5 keeps its zero-command in-place gait.'
 Write-Host 'Unity Play supplies Mink and keypad input. Robot still requires SSH password and manual uppercase P.'
 exit 0
}
$Host.UI.RawUI.WindowTitle="G1 Velocity Mink Keypad - $Mode"
if($Mode -eq 'Check'){
 Get-NetUDPEndpoint -ErrorAction SilentlyContinue|Where-Object LocalPort -in 5005,5008,5016|Select-Object LocalAddress,LocalPort,OwningProcess
 Write-Host 'CHECK ONLY. Keypad: localhost5016 -> G1:5017. Mink: localhost5008 -> G1:5014. One G1 LowCmd owner.'
 Write-Host 'Robot build expected: continuous g1_velocity_12dof_motion policy; zero input is an in-place gait.'
 exit 0
}
if($Mode -eq 'Input'){
 if($RelayToken -notmatch '^[A-Za-z0-9]{16,128}$'){throw 'Input requires the shared relay token.'}
 $env:G1_TWIST2_KEYBOARD_RATE='1';$env:G1_USE_HARDWARE_INITIAL_STATE='0'
 $env:G1_MINK_SIM_MUJOCO_ROOT="$root/logs/diagnostics/mujoco_versions/3.12.0"
 $env:G1_CYCLE_RELAY_TOKEN=$RelayToken
 & py -3.11 -B "$root/MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live_entry.py" --ik-solver vanilla --live-cycle-candidate --upstream-mink-collision --speed-profile today
 exit $LASTEXITCODE
}
if($Mode -eq 'Camera'){
 & wsl.exe -d Ubuntu -- bash -lc "pgrep -f '[g]1_camera_tcp_bridge.py' >/dev/null"
 if($LASTEXITCODE -eq 0){Write-Host 'Camera bridge already running; keeping existing process.';exit 0}
 if($LASTEXITCODE -ne 1){throw 'Could not inspect the existing WSL camera bridge.'}
 & "$root/tools/START_G1_CAMERA_TO_UNITY.bat";exit $LASTEXITCODE
}
if($RelayToken -notmatch '^[A-Za-z0-9]{16,128}$'){throw 'Relay/Robot requires the shared token.'}
if($Mode -eq 'ArmRelay'){
 & py -3.11 -B "$root/hardware/g1_arm_bridge/gate7_mink_cycle_relay.py" --target-host 192.168.123.164 --relay-token $RelayToken --profile today
 exit $LASTEXITCODE
}
if($Mode -eq 'VelocityRelay'){
 & py -3.11 -B "$root/hardware/g1_arm_bridge/g1_velocity_keypad_relay.py" --target-host auto --target-port 5017 --discovery-port 5018 --relay-token $RelayToken --status-file "$root/logs/test_results/keypad_velocity_status.json"
 exit $LASTEXITCODE
}
$command="cd /home/unitree/g1_velocity_mink_keypad_right_arm_20260914 && sha256sum -c SHA256SUMS && ./run_velocity_mink_keypad.sh $RelayToken"
& ssh.exe -tt -o StrictHostKeyChecking=yes -o ConnectTimeout=5 unitree@192.168.123.164 $command
exit $LASTEXITCODE
