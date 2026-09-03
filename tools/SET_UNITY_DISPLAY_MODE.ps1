param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('simulation', 'hardware', 'recorded')][string]$Mode
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$directory = Join-Path $root 'logs\runtime'
[void][IO.Directory]::CreateDirectory($directory)
$path = Join-Path $directory 'unity_display_mode.json'
$temporary = Join-Path $directory ('unity_display_mode.' + [guid]::NewGuid().ToString('N') + '.tmp')
$json = @{schema='g1.unity.display.v1'; mode=$Mode} | ConvertTo-Json
try
{
    [IO.File]::WriteAllText($temporary, $json, [Text.UTF8Encoding]::new($false))
    # Windows PowerShell 5.1 requires a typed null string for the backup path.
    if ([IO.File]::Exists($path)) { [IO.File]::Replace($temporary, $path, [NullString]::Value) }
    else { [IO.File]::Move($temporary, $path) }
}
finally
{
    if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
}
Write-Output "[DISPLAY] Unity mode: $Mode. Stop Play before changing modes; then press Play again."
Write-Output "[DISPLAY] Local display selection only. No robot authorization or command."
Write-Output "[DISPLAY] Config: $path"
