param([int]$InterfaceIndex = 0)
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot 'G1_ETHERNET_ADAPTER.ps1')
$adapter = GetG1EthernetAdapter -InterfaceIndex $InterfaceIndex -Mode Restore

$status_path = Join-Path (Split-Path -Parent $PSScriptRoot) "logs\runtime\g1_ethernet_configured.txt"
if (Test-Path -LiteralPath $status_path) { Remove-Item -LiteralPath $status_path -Force }

. (Join-Path $PSScriptRoot 'G1_ETHERNET_DNS.ps1')
. (Join-Path $PSScriptRoot 'G1_ETHERNET_TRANSACTION.ps1')
InvokeG1EthernetChange $adapter $true $status_path
Write-Output "DHCP enabled and manual IPv4 addresses removed. IPv4 DNS is automatic; IPv6 DNS was not changed. A DHCP lease is not guaranteed."
