param(
    [Parameter(Mandatory=$true)][string]$Capture,
    [Parameter(Mandatory=$true)][string]$ResultJson
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$unity = Join-Path $root 'Unity_G1_VR'
[xml]$project = Get-Content (Join-Path $unity 'Assembly-CSharp.csproj') -Raw
$corePath = $project.SelectSingleNode("//Reference[@Include='UnityEngine.CoreModule']/HintPath").InnerText
if (-not [IO.Path]::IsPathRooted($corePath)) { $corePath = Join-Path $unity $corePath }
[void][Reflection.Assembly]::LoadFrom($corePath)
$assemblyPath = Join-Path $unity 'Temp\bin\Debug\Assembly-CSharp.dll'
$assembly = [Reflection.Assembly]::LoadFrom($assemblyPath)
$type = $assembly.GetType('G1RobotStateUdpReceiver', $true)
$flags = [Reflection.BindingFlags]'Static,NonPublic'
$parser = $type.GetMethod('ParseStatePacket', $flags)
$baseCheck = $type.GetMethod('HasValidBaseState', $flags)
$mirrorCheck = $type.GetMethod('HasValidMirrorDiagnostics', $flags)
$jointCheck = $type.GetMethod('HasFullBodyVector', $flags)
if ($null -eq $parser) { throw 'Build the current Assembly-CSharp.csproj before running this test.' }

function Read-Packet([string]$Json) { return $parser.Invoke($null, @($Json)) }
function Assert-Condition([bool]$Condition, [string]$Message)
{
    if (-not $Condition) { throw $Message }
}

# Calls the compiled receiver's pure parser/validators, never a MonoBehaviour
# lifecycle method, viewer, socket, Unitree SDK, or DDS publisher.
foreach ($json in @('{}', '{"base_state":null,"mirror_diagnostics":null}'))
{
    $packet = Read-Packet $json
    Assert-Condition ($null -eq $packet.base_state) 'Missing/null base_state became a phantom object.'
    Assert-Condition ($null -eq $packet.mirror_diagnostics) 'Missing/null mirror diagnostics became a phantom object.'
}
$invalid = Read-Packet '{"base_state":{},"mirror_diagnostics":{}}'
Assert-Condition (-not $baseCheck.Invoke($null, @($invalid.base_state))) 'Malformed present base_state was accepted.'
Assert-Condition (-not $mirrorCheck.Invoke($null, @($invalid.mirror_diagnostics))) 'Malformed present mirror diagnostics were accepted.'
$valid = Read-Packet '{"base_state":{"valid":true,"topic":"rt/odommodestate","received_packets":1,"last_packet_age_s":0.01,"position_m":[0,0,0],"quaternion_xyzw":[0,0,0,1],"velocity_mps":[0,0,0],"yaw_speed_rad_s":0},"mirror_diagnostics":{"source_base_position_m":[0,0,0],"source_base_quaternion_xyzw":[0,0,0,1],"displayed_base_position_m":[0,0,0],"displayed_base_quaternion_xyzw":[0,0,0,1],"base_position_error_m":0,"base_orientation_error_deg":0,"max_joint_position_error_rad":0}}'
Assert-Condition ($baseCheck.Invoke($null, @($valid.base_state))) 'Valid base_state was rejected.'
Assert-Condition ($mirrorCheck.Invoke($null, @($valid.mirror_diagnostics))) 'Valid mirror diagnostics were rejected.'
$malformedRejected = $false
try { [void](Read-Packet '{bad json') } catch { $malformedRejected = $true }
Assert-Condition $malformedRejected 'Malformed JSON was accepted.'

$previewType = $assembly.GetType('G1UnityRightArmPreview', $true)
$modeType = $previewType.GetNestedType('DisplayMode')
$modeParser = $previewType.GetMethod('ParseDisplayMode')
$selector = $previewType.GetMethod('SelectDisplaySource')
$sourceCheck = $type.GetMethod('IsExpectedSource')
$modeCases = 0
foreach ($name in @('Unavailable', 'Simulation', 'Hardware', 'Recorded'))
{
    $mode = [Enum]::Parse($modeType, $name)
    foreach ($changed in @($false, $true))
    {
        foreach ($sim in @($false, $true))
        {
            foreach ($hardware in @($false, $true))
            {
                $expected = 'Unavailable'
                if (-not $changed)
                {
                    if ($name -eq 'Simulation' -and $sim) { $expected = 'Simulation' }
                    if ($name -in @('Hardware', 'Recorded') -and $hardware) { $expected = $name }
                }
                $actual = $selector.Invoke($null, @($mode, $changed, $sim, $hardware)).ToString()
                Assert-Condition ($actual -eq $expected) "Unexpected display source: $name / $changed / $sim / $hardware -> $actual"
                $modeCases++
            }
        }
    }
}
foreach ($name in @('simulation', 'hardware', 'recorded'))
{
    $json = @{schema='g1.unity.display.v1'; mode=$name} | ConvertTo-Json
    Assert-Condition ($modeParser.Invoke($null, @([string]$json)).ToString().ToLowerInvariant() -eq $name) "Rejected valid mode $name"
}
foreach ($json in @('{}', 'null', '{bad', '{"schema":"bad","mode":"hardware"}', '{"schema":"g1.unity.display.v1","mode":"auto"}'))
{
    Assert-Condition ($modeParser.Invoke($null, @($json)).ToString() -eq 'Unavailable') 'Bad mode did not fail closed.'
}
foreach ($source in @('mink_simulation', 'legacy_unspecified', '', $null))
{
    Assert-Condition (-not $sourceCheck.Invoke($null, @('g1_lowstate_read_only', $false, $source))) 'Hardware source filter accepted a non-hardware packet.'
}
Assert-Condition ($sourceCheck.Invoke($null, @('g1_lowstate_read_only', $false, 'g1_lowstate_read_only'))) 'Hardware source filter rejected measured data.'
Assert-Condition ($sourceCheck.Invoke($null, @('mink_simulation', $true, 'mink_simulation'))) 'Simulation source filter rejected Mink.'

$count = 0
$active = 0
$feasible = 0
$manifest = $null
foreach ($line in [IO.File]::ReadLines((Resolve-Path $Capture).Path))
{
    $record = $line | ConvertFrom-Json
    if ($record.schema -eq 'g1.mink.capture.manifest.v1')
    {
        $manifest = $record
        Assert-Condition ($record.hardware_output_authorized -eq $false) 'Capture is not an offline recording.'
        continue
    }
    Assert-Condition ($null -ne $manifest) 'Missing capture manifest.'
    $json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($record.payload_base64))
    $packet = Read-Packet $json
    Assert-Condition ($null -ne $packet.right_arm) "Packet $count lost right_arm."
    Assert-Condition ($jointCheck.Invoke($null, @($packet))) "Packet $count failed the 29-joint contract."
    if ($null -ne $packet.base_state)
    {
        Assert-Condition ($baseCheck.Invoke($null, @($packet.base_state))) "Packet $count has invalid base_state."
    }
    if ($null -ne $packet.mirror_diagnostics)
    {
        Assert-Condition ($mirrorCheck.Invoke($null, @($packet.mirror_diagnostics))) "Packet $count has invalid mirror diagnostics."
    }
    if ($packet.right_arm.active)
    {
        $active++
        Assert-Condition $packet.right_arm.feasible_target_valid "Active packet $count has no feasible target."
        Assert-Condition ($packet.right_arm.feasible_target_delta.Length -eq 3) "Active packet $count has no feasible delta."
        $feasible++
    }
    $count++
}
Assert-Condition ($count -gt 0) 'Empty capture.'
$result = [ordered]@{
    status='PASS'; capture_id=$manifest.capture_id; packets=$count;
    active_packets=$active; valid_feasible_targets=$feasible;
    optional_contract_fixtures='PASS'; malformed_json_rejected=$malformedRejected;
    display_mode_cases=$modeCases; display_config_fixtures='PASS'; hardware_source_filter='PASS';
    compiled_assembly_sha256=(Get-FileHash $assemblyPath -Algorithm SHA256).Hash;
    robot_command=$false; socket_created=$false;
    boundary='Compiled C# parsing and validation only; not a Unity headset or live UDP test.'
}
$resultPath = [IO.Path]::GetFullPath($ResultJson)
[void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($resultPath))
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $resultPath -Encoding utf8
Write-Output "PASS: $count packets, $active active feasible targets; missing, null, valid and invalid optional contracts."
Write-Output "Result saved to: $resultPath"
