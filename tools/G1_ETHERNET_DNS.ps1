# IPv4 DNS only. This helper never changes an IP address, route, or registry value directly.
function GetG1DnsSnapshot($adapter)
{
    $guid = [guid]$adapter.InterfaceGuid
    $registry_path = 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\' + $guid.ToString('B')
    $properties = Get-ItemProperty -LiteralPath $registry_path -ErrorAction Stop
    $manual = [string]$properties.NameServer
    $servers = @($manual -split '[,;\s]+' | Where-Object { $_ })
    foreach ($server in $servers)
    {
        $parsed = [System.Net.IPAddress]::Parse($server)
        if ($parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork)
        {
            throw 'Unsupported IPv4 DNS override; no DNS changes made.'
        }
    }
    $clients = @(Get-DnsClientServerAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -ErrorAction Stop)
    if ($clients.Count -ne 1) { throw 'Expected one IPv4 DNS client; no DNS changes made.' }
    return @{Client=$clients[0]; RegistryPath=$registry_path; Servers=$servers}
}

function AssertG1DnsState($snapshot, $expected)
{
    $properties = Get-ItemProperty -LiteralPath $snapshot.RegistryPath -ErrorAction Stop
    $actual = @(([string]$properties.NameServer) -split '[,;\s]+' | Where-Object { $_ })
    # Order matters: the first server is preferred. Empty means automatic, not no DNS.
    if (($actual -join ',') -ne (@($expected) -join ',')) { throw 'IPv4 DNS verification failed: override differs.' }
}

function RestoreG1Dns($snapshot)
{
    if ($snapshot.Servers.Count -eq 0)
    {
        Set-DnsClientServerAddress -InputObject $snapshot.Client -ResetServerAddresses -ErrorAction Stop
    }
    else
    {
        Set-DnsClientServerAddress -InputObject $snapshot.Client -ServerAddresses $snapshot.Servers -ErrorAction Stop
    }
    AssertG1DnsState $snapshot $snapshot.Servers
}

function ResetG1Dns($snapshot)
{
    try
    {
        Set-DnsClientServerAddress -InputObject $snapshot.Client -ResetServerAddresses -ErrorAction Stop
        AssertG1DnsState $snapshot @()
    }
    catch
    {
        $original_error = $_.Exception.Message
        try
        {
            RestoreG1Dns $snapshot
        }
        catch { throw "DNS update failed: $original_error. DNS ROLLBACK FAILED: $($_.Exception.Message). Inspect this adapter; IP settings may already have changed." }
        throw "DNS update failed: $original_error. Previous IPv4 DNS mode restored; IP settings may already have changed."
    }
}
