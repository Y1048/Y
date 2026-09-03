$ErrorActionPreference = "Stop"

$rule_name = "G1-LowState-to-Windows"

Remove-NetFirewallRule -Name $rule_name -ErrorAction SilentlyContinue
New-NetFirewallRule `
    -Name $rule_name `
    -DisplayName "G1 LowState UDP 5007 and 5009 to Windows" `
    -Direction Inbound `
    -Protocol UDP `
    -LocalPort 5007,5009 `
    -RemoteAddress LocalSubnet `
    -Action Allow `
    -Enabled True `
    -Profile Any | Out-Null

$project_root = Split-Path -Parent $PSScriptRoot
$status_path = Join-Path $project_root "logs\runtime\g1_lowstate_udp_firewall_configured.txt"
"$rule_name enabled for UDP 5007 and 5009" | Set-Content -LiteralPath $status_path -Encoding ascii
