$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$resultRoot = Join-Path $root 'logs\test_results'
$latest = Get-ChildItem -LiteralPath $resultRoot -Directory -Filter 'mjlab_setup_*' |
    Sort-Object Name -Descending |
    Select-Object -First 1

if (-not $latest) {
    Write-Host '[NOT STARTED] No mjlab setup log exists.' -ForegroundColor Yellow
    exit 2
}

$console = Join-Path $latest.FullName 'console.log'
$smoke = Join-Path $latest.FullName 'smoke.json'
$text = if (Test-Path -LiteralPath $console) {
    Get-Content -LiteralPath $console -Raw
} else {
    ''
}

Write-Host "Log: $console"
if ($text -match 'SETUP_CHECK_COMPLETE:') {
    if (-not (Test-Path -LiteralPath $smoke)) {
        Write-Host '[FAILED] Completion marker exists but smoke.json is missing.' -ForegroundColor Red
        exit 1
    }
    $result = Get-Content -LiteralPath $smoke -Raw | ConvertFrom-Json
    if ($result.status -ne 'passed') {
        Write-Host '[FAILED] smoke.json does not report passed.' -ForegroundColor Red
        exit 1
    }
    Write-Host '[COMPLETE] G1 simulation smoke and two PPO iterations passed.' -ForegroundColor Green
    Write-Host "GPU: $($result.gpu); peak Torch allocation: $([math]::Round($result.torch_peak_allocated_bytes / 1MB, 1)) MiB"
    Write-Host 'This confirms only the synthetic setup check; it is not a trained walking policy.'
    exit 0
}

$wslProcesses = & wsl.exe -d Ubuntu -- bash -lc "ps -eo args | grep -E '[u]v sync|[s]moke_mjlab.py|[t]rain Mjlab-Velocity-Flat-Unitree-G1'" 2>$null
if ($LASTEXITCODE -eq 0 -and $wslProcesses) {
    $stage = if ($wslProcesses -match 'smoke_mjlab.py') {
        'G1 simulation smoke test'
    } elseif ($wslProcesses -match 'train Mjlab-Velocity') {
        'two-iteration PPO check'
    } else {
        'package installation/download'
    }
    Write-Host "[RUNNING] $stage" -ForegroundColor Cyan
    if ($console) { Get-Content -LiteralPath $console -Tail 5 }
    exit 3
}

Write-Host '[FAILED OR INTERRUPTED] No completion marker and no setup process is running.' -ForegroundColor Red
if ($console) { Get-Content -LiteralPath $console -Tail 20 }
exit 1
