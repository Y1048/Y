$ErrorActionPreference = "Stop"

$project_root = Split-Path -Parent $PSScriptRoot
$log_dir = Join-Path $project_root "logs\runtime"
$etl_path = Join-Path $log_dir "g1_network_capture.etl"
$text_path = Join-Path $log_dir "g1_network_capture.txt"
$done_path = Join-Path $log_dir "g1_network_capture.done"

New-Item -ItemType Directory -Path $log_dir -Force | Out-Null
Remove-Item -LiteralPath $etl_path, $text_path, $done_path -Force -ErrorAction SilentlyContinue

$capture_started = $false
try
{
    & pktmon start --capture --pkt-size 0 --file-name $etl_path | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "pktmon start failed: $LASTEXITCODE" }
    $capture_started = $true
    Start-Sleep -Seconds 5
    & pktmon stop | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "pktmon stop failed: $LASTEXITCODE" }
    $capture_started = $false
    if (!(Test-Path -LiteralPath $etl_path) -or (Get-Item -LiteralPath $etl_path).Length -le 0)
    {
        throw "pktmon did not create a nonempty ETL file"
    }
    & pktmon format $etl_path -o $text_path | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "pktmon format failed: $LASTEXITCODE" }
    if (!(Test-Path -LiteralPath $text_path) -or (Get-Item -LiteralPath $text_path).Length -le 0)
    {
        throw "pktmon did not create a nonempty text file"
    }
    Set-Content -LiteralPath $done_path -Value "complete" -Encoding ascii
    Write-Output "Result saved to: $text_path"
}
catch
{
    Write-Output "[ERROR] $($_.Exception.Message)"
    Write-Output "[ACTION] Inspect the pktmon error above. Capture completion was not recorded."
    if ($capture_started)
    {
        & pktmon stop | Out-Null
        if ($LASTEXITCODE -ne 0)
        {
            Write-Output "[ACTION] Capture cleanup failed; check pktmon status before retrying."
        }
    }
    exit 1
}
