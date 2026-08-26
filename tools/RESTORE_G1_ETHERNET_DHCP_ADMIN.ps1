$ErrorActionPreference = "Stop"

$adapter = Get-NetAdapter | Where-Object { $_.InterfaceDescription -like "ASIX AX88772A*" } | Select-Object -First 1
if(-not $adapter)
{
    throw "ASIX AX88772A Ethernet adapter was not found."
}
$interface_alias = $adapter.Name

Get-NetIPAddress -InterfaceAlias $interface_alias -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.PrefixOrigin -eq "Manual" } |
    Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
Set-NetIPInterface -InterfaceAlias $interface_alias -AddressFamily IPv4 -Dhcp Enabled
Set-DnsClientServerAddress -InterfaceAlias $interface_alias -ResetServerAddresses
