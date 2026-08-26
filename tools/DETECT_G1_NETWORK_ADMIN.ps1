$ErrorActionPreference = "Stop"

$project_root = Split-Path -Parent $PSScriptRoot
$log_dir = Join-Path $project_root "logs\runtime"
$etl_path = Join-Path $log_dir "g1_network_capture.etl"
$text_path = Join-Path $log_dir "g1_network_capture.txt"
$done_path = Join-Path $log_dir "g1_network_capture.done"

New-Item -ItemType Directory -Path $log_dir -Force | Out-Null
Remove-Item -LiteralPath $etl_path, $text_path, $done_path -Force -ErrorAction SilentlyContinue

try
{
    & pktmon stop 2>$null | Out-Null
}
catch
{
}

& pktmon start --capture --pkt-size 0 --file-name $etl_path | Out-Null
Start-Sleep -Seconds 5
& pktmon stop | Out-Null
& pktmon format $etl_path -o $text_path | Out-Null
Set-Content -LiteralPath $done_path -Value "complete" -Encoding ascii
