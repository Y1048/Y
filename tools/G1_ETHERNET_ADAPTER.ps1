function GetG1PhysicalEthernetAdapters
{
    return @(Get-NetAdapter -IncludeHidden | Where-Object {
        $_.HardwareInterface -eq $true -and
        $_.Virtual -eq $false -and
        $_.ConnectorPresent -ne $false -and
        ([string]$_.MediaType -eq '802.3' -or
         [string]$_.PhysicalMediaType -eq '802.3')
    })
}

function TestG1Ipv4Address($adapter)
{
    $addresses = @(Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue)
    return @($addresses | Where-Object {
        [string]$_.IPAddress -eq '192.168.123.99' -and
        [int]$_.PrefixLength -eq 24
    }).Count -gt 0
}

function FormatG1AdapterList($adapters)
{
    if (-not $adapters -or $adapters.Count -eq 0)
    {
        return 'none'
    }
    return (($adapters | ForEach-Object {
        "ifIndex=$($_.ifIndex) name='$($_.Name)' status=$($_.Status) device='$($_.InterfaceDescription)'"
    }) -join '; ')
}

function GetG1EthernetAdapter(
    [int]$InterfaceIndex = 0,
    [ValidateSet('Configure','Restore')]
    [string]$Mode = 'Configure')
{
    $physical = @(GetG1PhysicalEthernetAdapters)

    if ($InterfaceIndex -ne 0)
    {
        $explicit = @($physical | Where-Object { $_.ifIndex -eq $InterfaceIndex })
        if ($explicit.Count -ne 1)
        {
            throw "InterfaceIndex $InterfaceIndex is not one physical Ethernet adapter. No settings were changed."
        }
        return $explicit[0]
    }

    $configured = @($physical | Where-Object { TestG1Ipv4Address $_ })
    if ($configured.Count -eq 1)
    {
        return $configured[0]
    }
    if ($configured.Count -gt 1)
    {
        throw ("Multiple physical Ethernet adapters already have 192.168.123.99/24: " +
               (FormatG1AdapterList $configured) +
               ". Specify -InterfaceIndex explicitly; no settings were changed.")
    }

    if ($Mode -eq 'Restore')
    {
        throw ("No physical Ethernet adapter currently has 192.168.123.99/24. " +
               "Specify -InterfaceIndex explicitly if a particular adapter must be restored; no settings were changed.")
    }

    $linked = @($physical | Where-Object { [string]$_.Status -eq 'Up' })
    if ($linked.Count -eq 1)
    {
        return $linked[0]
    }
    if ($linked.Count -eq 0)
    {
        throw ("No linked physical Ethernet adapter was found. Connect the G1 Ethernet cable, " +
               "or specify -InterfaceIndex explicitly; no settings were changed. Physical Ethernet: " +
               (FormatG1AdapterList $physical))
    }

    throw ("Multiple linked physical Ethernet adapters were found: " +
           (FormatG1AdapterList $linked) +
           ". The G1 adapter cannot be inferred safely. Specify -InterfaceIndex explicitly; no settings were changed.")
}
