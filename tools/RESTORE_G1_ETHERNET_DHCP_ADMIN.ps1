param([int]$InterfaceIndex = 0)
$ErrorActionPreference = "Stop"

$adapters = @(Get-NetAdapter | Where-Object { $_.InterfaceDescription -like "ASIX AX88772A*" })
if ($InterfaceIndex -ne 0)
{
    $adapters = @($adapters | Where-Object { $_.ifIndex -eq $InterfaceIndex })
}
if ($adapters.Count -ne 1)
{
    throw "Expected one ASIX AX88772A adapter. Check Get-NetAdapter and specify -InterfaceIndex explicitly; no settings were changed."
}
$adapter = $adapters[0]
$interface_index = $adapter.ifIndex
$interface_alias = $adapter.Name

$status_path = Join-Path (Split-Path -Parent $PSScriptRoot) "logs\runtime\g1_ethernet_configured.txt"
if (Test-Path -LiteralPath $status_path) { Remove-Item -LiteralPath $status_path -Force }

. (Join-Path $PSScriptRoot 'G1_ETHERNET_DNS.ps1')
. (Join-Path $PSScriptRoot 'G1_ETHERNET_TRANSACTION.ps1')
InvokeG1EthernetChange $adapter $true $status_path
Write-Output "DHCP enabled and manual IPv4 addresses removed. IPv4 DNS is automatic; IPv6 DNS was not changed. A DHCP lease is not guaranteed."
