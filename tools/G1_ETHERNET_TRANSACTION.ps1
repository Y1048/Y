# DHCP belongs to the active interface; Windows does not expose a persistent
# Get-NetIPInterface DHCP row on every build. Manual addresses are checked in
# both stores. DHCP leases are renewed by Windows, never replayed.
function GetG1ManualAddresses($index, $store)
{
    return @(Get-NetIPAddress -InterfaceIndex $index -AddressFamily IPv4 -PolicyStore $store -ErrorAction Stop |
        Where-Object { [string]$_.PrefixOrigin -eq 'Manual' })
}

function GetG1AddressKeys($addresses)
{
    return @($addresses | ForEach-Object { "$($_.IPAddress)/$($_.PrefixLength)/$($_.SkipAsSource)" } | Sort-Object)
}

function GetG1EthernetSnapshot($adapter)
{
    $snapshot = @{Index=$adapter.ifIndex; Guid=[string]$adapter.InterfaceGuid; Stores=@{}}
    $interfaces = @(Get-NetIPInterface -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -PolicyStore ActiveStore -ErrorAction Stop)
    if ($interfaces.Count -ne 1 -or [string]$interfaces[0].Dhcp -notin @('Enabled','Disabled'))
    {
        throw 'Unsupported active IPv4 interface state; no settings changed.'
    }
    $snapshot.Dhcp = [string]$interfaces[0].Dhcp
    foreach ($store in @('ActiveStore', 'PersistentStore'))
    {
        $routes = @(Get-NetRoute -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -PolicyStore $store -ErrorAction SilentlyContinue)
        if (@($routes | Where-Object { [string]$_.Protocol -notin @('Local','Dhcp') }).Count)
        {
            throw 'Custom IPv4 routes present; automatic changes blocked. No settings changed.'
        }
        $addresses = @(GetG1ManualAddresses $adapter.ifIndex $store)
        foreach ($address in $addresses)
        {
            if ([string]$address.Type -ne 'Unicast' -or $address.ValidLifetime.TotalSeconds -lt [uint32]::MaxValue -or
                $address.PreferredLifetime.TotalSeconds -lt [uint32]::MaxValue)
            {
                throw 'Unsupported temporary/manual IPv4 address; no settings changed.'
            }
        }
        $snapshot.Stores[$store] = @{Dhcp=$snapshot.Dhcp; Addresses=$addresses}
    }
    $active = $snapshot.Stores.ActiveStore
    $persistent = $snapshot.Stores.PersistentStore
    if (((GetG1AddressKeys $active.Addresses) -join ',') -ne ((GetG1AddressKeys $persistent.Addresses) -join ','))
    {
        throw 'Active/persistent IPv4 settings differ; no settings changed.'
    }
    $snapshot.Dns = GetG1DnsSnapshot $adapter
    return $snapshot
}

function AssertG1AdapterIdentity($snapshot)
{
    $current = @(Get-NetAdapter | Where-Object { $_.ifIndex -eq $snapshot.Index })
    if ($current.Count -ne 1 -or [string]$current[0].InterfaceGuid -ne $snapshot.Guid)
    {
        throw 'Adapter identity changed; refusing mutation on a different device.'
    }
}

function SetG1Ipv4State($snapshot, $states)
{
    AssertG1AdapterIdentity $snapshot
    Set-NetIPInterface -InterfaceIndex $snapshot.Index -AddressFamily IPv4 -PolicyStore ActiveStore -Dhcp Disabled -ErrorAction Stop
    foreach ($store in @('PersistentStore','ActiveStore'))
    {
        $state = $states[$store]
        foreach ($address in @(GetG1ManualAddresses $snapshot.Index $store))
        {
            Remove-NetIPAddress -InterfaceIndex $snapshot.Index -AddressFamily IPv4 -PolicyStore $store -IPAddress $address.IPAddress -Confirm:$false -ErrorAction Stop
        }
        foreach ($address in $state.Addresses)
        {
            New-NetIPAddress -InterfaceIndex $snapshot.Index -AddressFamily IPv4 -PolicyStore $store -IPAddress $address.IPAddress `
                -PrefixLength $address.PrefixLength -SkipAsSource ([bool]$address.SkipAsSource) -ErrorAction Stop | Out-Null
        }
    }
    Set-NetIPInterface -InterfaceIndex $snapshot.Index -AddressFamily IPv4 -PolicyStore ActiveStore -Dhcp $states.ActiveStore.Dhcp -ErrorAction Stop
}

function AssertG1Ipv4State($snapshot, $states)
{
    $interfaces = @(Get-NetIPInterface -InterfaceIndex $snapshot.Index -AddressFamily IPv4 -PolicyStore ActiveStore -ErrorAction Stop)
    if ($interfaces.Count -ne 1 -or [string]$interfaces[0].Dhcp -ne $states.ActiveStore.Dhcp)
    {
        throw 'IPv4 DHCP verification failed: ActiveStore'
    }
    foreach ($store in @('ActiveStore','PersistentStore'))
    {
        $addresses = @(GetG1ManualAddresses $snapshot.Index $store)
        $all_addresses = @(Get-NetIPAddress -InterfaceIndex $snapshot.Index -AddressFamily IPv4 -PolicyStore $store -ErrorAction Stop)
        if (($states[$store].Dhcp -eq 'Disabled' -and $all_addresses.Count -ne $addresses.Count) -or
            ((GetG1AddressKeys $addresses) -join ',') -ne ((GetG1AddressKeys $states[$store].Addresses) -join ','))
        {
            throw "IPv4 verification failed: $store"
        }
    }
}

function TestG1WiredSsh()
{
    # Windows may briefly mark a newly assigned address tentative (DAD).
    for ($attempt = 0; $attempt -lt 6; $attempt++)
    {
        $client = [System.Net.Sockets.TcpClient]::new()
        try
        {
            $pending = $client.ConnectAsync('192.168.123.164', 22)
            if ($pending.Wait(1500) -and $client.Connected) { return $true }
        }
        catch { }
        finally { $client.Dispose() }
        if ($attempt -lt 5) { Start-Sleep -Milliseconds 500 }
    }
    return $false
}

function InvokeG1EthernetChange($adapter, [bool]$automatic, $status_path, [bool]$verify_robot_ssh = $false)
{
    $snapshot = GetG1EthernetSnapshot $adapter
    $addresses = @()
    $dhcp = 'Enabled'
    if (-not $automatic)
    {
        $dhcp = 'Disabled'
        $addresses = @([pscustomobject]@{IPAddress='192.168.123.99';PrefixLength=24;SkipAsSource=$false})
    }
    $desired = @{ActiveStore=@{Dhcp=$dhcp;Addresses=$addresses};PersistentStore=@{Dhcp=$dhcp;Addresses=$addresses}}
    try
    {
        SetG1Ipv4State $snapshot $desired
        AssertG1Ipv4State $snapshot $desired
        ResetG1Dns $snapshot.Dns
        if ($verify_robot_ssh -and -not (TestG1WiredSsh))
        {
            throw 'G1 wired SSH did not respond after IPv4 configuration'
        }
        if (-not $automatic) { "$($adapter.Name) 192.168.123.99/24" | Set-Content -LiteralPath $status_path -Encoding ascii }
    }
    catch
    {
        $original_error = $_.Exception.Message
        $errors = @()
        try { if (Test-Path -LiteralPath $status_path) { Remove-Item -LiteralPath $status_path -Force } } catch { $errors += $_.Exception.Message }
        try { SetG1Ipv4State $snapshot $snapshot.Stores; AssertG1Ipv4State $snapshot $snapshot.Stores } catch { $errors += $_.Exception.Message }
        try
        {
            AssertG1AdapterIdentity $snapshot
            RestoreG1Dns $snapshot.Dns
        }
        catch { $errors += $_.Exception.Message }
        if ($errors.Count) { throw "Ethernet change failed: $original_error. ROLLBACK FAILED: $($errors -join '; '). Inspect the adapter before retrying." }
        throw "Ethernet change failed: $original_error. Previous IPv4 configuration and DNS restored; any DHCP lease must be reacquired."
    }
}
