param([int]$InterfaceIndex = 0, [switch]$VerifyRobotSsh)
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot 'G1_ETHERNET_ADAPTER.ps1')
$adapter = GetG1EthernetAdapter -InterfaceIndex $InterfaceIndex -Mode Configure

if ($VerifyRobotSsh -and [string]$adapter.Status -ne 'Up')
{
    throw 'Selected G1 Ethernet link is disconnected; no settings were changed.'
}
$other_g1_subnet = @(Get-NetIPAddress -AddressFamily IPv4 -PolicyStore ActiveStore -ErrorAction Stop |
    Where-Object { $_.InterfaceIndex -ne $adapter.ifIndex -and $_.IPAddress -like '192.168.123.*' })
if ($other_g1_subnet.Count)
{
    throw 'Another adapter already uses 192.168.123.x; no settings were changed.'
}

$project_root = Split-Path -Parent $PSScriptRoot
$status_path = Join-Path $project_root "logs\runtime\g1_ethernet_configured.txt"
New-Item -ItemType Directory -Path (Split-Path -Parent $status_path) -Force | Out-Null
if (Test-Path -LiteralPath $status_path) { Remove-Item -LiteralPath $status_path -Force }

. (Join-Path $PSScriptRoot 'G1_ETHERNET_DNS.ps1')
. (Join-Path $PSScriptRoot 'G1_ETHERNET_TRANSACTION.ps1')
InvokeG1EthernetChange $adapter $false $status_path ([bool]$VerifyRobotSsh)
