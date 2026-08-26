$ErrorActionPreference = "Stop"

$rule_name = "G1-DDS-to-WSL"
$host_rule_name = "G1-DDS-to-WSL-Host"
$wsl_creator_id = "{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}"
$adapter = Get-NetAdapter | Where-Object { $_.InterfaceDescription -like "ASIX AX88772A*" } | Select-Object -First 1
if(-not $adapter)
{
    throw "ASIX AX88772A Ethernet adapter was not found."
}

Get-NetFirewallHyperVRule -Name $rule_name -ErrorAction SilentlyContinue |
    Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue

New-NetFirewallHyperVRule `
    -Name $rule_name `
    -DisplayName "G1 DDS to WSL" `
    -Direction Inbound `
    -VMCreatorId $wsl_creator_id `
    -Protocol Any `
    -RemoteAddresses "192.168.123.0/24" `
    -Action Allow `
    -Enabled True `
    -Profiles Any | Out-Null

Remove-NetFirewallRule -Name $host_rule_name -ErrorAction SilentlyContinue
New-NetFirewallRule `
    -Name $host_rule_name `
    -DisplayName "G1 DDS to WSL Host" `
    -Direction Inbound `
    -InterfaceAlias $adapter.Name `
    -Protocol Any `
    -RemoteAddress "192.168.123.0/24" `
    -Action Allow `
    -Enabled True `
    -Profile Any | Out-Null

$project_root = Split-Path -Parent $PSScriptRoot
$status_path = Join-Path $project_root "logs\runtime\g1_dds_firewall_configured.txt"
"$rule_name enabled" | Set-Content -LiteralPath $status_path -Encoding ascii
