param([int]$InterfaceIndex = 0)
$ErrorActionPreference = "Stop"

$adapters = @(Get-NetAdapter | Where-Object { $_.InterfaceDescription -like "ASIX AX88772A*" })
if ($InterfaceIndex -ne 0)
{
    $adapters = @($adapters | Where-Object { $_.ifIndex -eq $InterfaceIndex })
}
if ($adapters.Count -ne 1)
{
    throw "Expected one G1 ASIX adapter; use -InterfaceIndex when multiple exist. No firewall rules were changed."
}
$adapter = $adapters[0]

$rule_name = "G1-LowState-to-Windows"
$project_root = Split-Path -Parent $PSScriptRoot
$status_path = Join-Path $project_root "logs\runtime\g1_lowstate_udp_firewall_configured.txt"
New-Item -ItemType Directory -Path (Split-Path -Parent $status_path) -Force | Out-Null
if (Test-Path -LiteralPath $status_path) { Remove-Item -LiteralPath $status_path -Force }

function GetRuleSnapshot
{
    $rules = @(Get-NetFirewallRule -PolicyStore PersistentStore -ErrorAction Stop |
        Where-Object { $_.Name -eq $rule_name })
    if ($rules.Count -eq 0) { return $null }
    if ($rules.Count -ne 1) { throw "Expected a unique local firewall rule: $rule_name" }
    $rule = $rules[0]
    $ports = @($rule | Get-NetFirewallPortFilter -ErrorAction Stop)
    $addresses = @($rule | Get-NetFirewallAddressFilter -ErrorAction Stop)
    $interfaces = @($rule | Get-NetFirewallInterfaceFilter -ErrorAction Stop)
    if ($ports.Count -ne 1 -or $addresses.Count -ne 1 -or $interfaces.Count -ne 1)
    {
        throw "Cannot snapshot firewall filters for $rule_name"
    }
    return @{
        Direction = [string]$rule.Direction; Action = [string]$rule.Action
        Enabled = [string]$rule.Enabled; Profile = [string]$rule.Profile
        Protocol = [string]$ports[0].Protocol; LocalPort = @($ports[0].LocalPort)
        RemoteAddress = @($addresses[0].RemoteAddress)
        InterfaceAlias = @($interfaces[0].InterfaceAlias)
    }
}

function AssertRuleSnapshot($expected)
{
    $actual = GetRuleSnapshot
    if ($null -eq $expected)
    {
        if ($null -ne $actual) { throw "New firewall rule still exists after rollback" }
        return
    }
    if ($null -eq $actual) { throw "Firewall rule is missing" }
    foreach ($key in $expected.Keys)
    {
        $wanted = (@($expected[$key]) | Sort-Object) -join ','
        $observed = (@($actual[$key]) | Sort-Object) -join ','
        if ($key -eq 'Protocol')
        {
            $wanted = $wanted -replace '^17$', 'UDP'
            $observed = $observed -replace '^17$', 'UDP'
        }
        if ($wanted -ne $observed) { throw "Firewall verification failed: $key" }
    }
}

$previous = GetRuleSnapshot
$desired = @{
    Direction = 'Inbound'; Protocol = 'UDP'; LocalPort = @(5007, 5009)
    InterfaceAlias = $adapter.Name; RemoteAddress = '192.168.123.0/24'
    Action = 'Allow'; Enabled = 'True'; Profile = 'Any'
}
# Update only the snapshotted fields; unrelated application/service filters stay intact.
try
{
    if ($null -eq $previous)
    {
        New-NetFirewallRule -Name $rule_name -PolicyStore PersistentStore `
            -DisplayName "G1 LowState UDP 5007 and 5009 to Windows" @desired | Out-Null
    }
    else
    {
        Set-NetFirewallRule -Name $rule_name -PolicyStore PersistentStore @desired | Out-Null
    }
    AssertRuleSnapshot $desired
    "$rule_name enabled on $($adapter.Name) from 192.168.123.0/24 for UDP 5007 and 5009" |
        Set-Content -LiteralPath $status_path -Encoding ascii
}
catch
{
    $original_error = $_.Exception.Message
    try
    {
        if (Test-Path -LiteralPath $status_path) { Remove-Item -LiteralPath $status_path -Force }
        if ($null -eq $previous)
        {
            if ($null -ne (GetRuleSnapshot))
            {
                Remove-NetFirewallRule -Name $rule_name -PolicyStore PersistentStore -ErrorAction Stop
            }
        }
        else
        {
            Set-NetFirewallRule -Name $rule_name -PolicyStore PersistentStore @previous | Out-Null
        }
        AssertRuleSnapshot $previous
    }
    catch
    {
        throw "Firewall update failed: $original_error. ROLLBACK FAILED: $($_.Exception.Message). Inspect the local rule before retrying."
    }
    throw "Firewall update failed: $original_error. Previous local rule state restored."
}
