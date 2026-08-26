$ErrorActionPreference = "Stop"

$adapter = Get-NetAdapter | Where-Object { $_.InterfaceDescription -like "ASIX AX88772A*" } | Select-Object -First 1
if(-not $adapter)
{
    throw "ASIX AX88772A Ethernet adapter was not found."
}
$interface_alias = $adapter.Name
$ip_address = "192.168.123.99"

Set-NetIPInterface -InterfaceAlias $interface_alias -AddressFamily IPv4 -Dhcp Disabled
Get-NetIPAddress -InterfaceAlias $interface_alias -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -ne $ip_address } |
    Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue

if(-not (Get-NetIPAddress -InterfaceAlias $interface_alias -AddressFamily IPv4 -IPAddress $ip_address -ErrorAction SilentlyContinue))
{
    New-NetIPAddress -InterfaceAlias $interface_alias -IPAddress $ip_address -PrefixLength 24 | Out-Null
}

Set-DnsClientServerAddress -InterfaceAlias $interface_alias -ResetServerAddresses

$project_root = Split-Path -Parent $PSScriptRoot
$status_path = Join-Path $project_root "logs\runtime\g1_ethernet_configured.txt"
"$interface_alias $ip_address/24" | Set-Content -LiteralPath $status_path -Encoding ascii
