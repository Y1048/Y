param([int]$InterfaceIndex = 0)
$ErrorActionPreference = 'Stop'
$adapters = @(Get-NetAdapter | Where-Object { $_.InterfaceDescription -like 'ASIX AX88772A*' })
if ($InterfaceIndex -ne 0) { $adapters = @($adapters | Where-Object { $_.ifIndex -eq $InterfaceIndex }) }
if ($adapters.Count -ne 1) { throw 'Expected one G1 ASIX adapter; use -InterfaceIndex when multiple exist. No rules changed.' }
$adapter = $adapters[0]
$project_root = Split-Path -Parent $PSScriptRoot
$status_path = Join-Path $project_root 'logs\runtime\g1_dds_firewall_configured.txt'
New-Item -ItemType Directory -Path (Split-Path -Parent $status_path) -Force | Out-Null
if (Test-Path -LiteralPath $status_path) { Remove-Item -LiteralPath $status_path -Force }

function GetRuleSnapshot($kind, $name)
{
    if ($kind -eq 'HyperV')
    {
        $rules = @(Get-NetFirewallHyperVRule -PolicyStore PersistentStore -ErrorAction Stop | Where-Object { $_.Name -eq $name })
    }
    else
    {
        $rules = @(Get-NetFirewallRule -PolicyStore PersistentStore -ErrorAction Stop | Where-Object { $_.Name -eq $name })
    }
    if ($rules.Count -eq 0) { return $null }
    if ($rules.Count -ne 1) { throw "Ambiguous local rule: $name" }
    $rule = $rules[0]
    $state = @{Direction=[string]$rule.Direction; Action=[string]$rule.Action; Enabled=[string]$rule.Enabled}
    if ($kind -eq 'HyperV')
    {
        $state.VMCreatorId = [string]$rule.VMCreatorId
        $state.Protocol = [string]$rule.Protocol
        $state.RemoteAddresses = @($rule.RemoteAddresses)
        $state.Profiles = [string]$rule.Profiles
    }
    else
    {
        $ports = @($rule | Get-NetFirewallPortFilter -ErrorAction Stop)
        $addresses = @($rule | Get-NetFirewallAddressFilter -ErrorAction Stop)
        $interfaces = @($rule | Get-NetFirewallInterfaceFilter -ErrorAction Stop)
        if ($ports.Count -ne 1 -or $addresses.Count -ne 1 -or $interfaces.Count -ne 1) { throw "Cannot snapshot filters: $name" }
        $state.Protocol = [string]$ports[0].Protocol
        $state.RemoteAddress = @($addresses[0].RemoteAddress)
        $state.InterfaceAlias = @($interfaces[0].InterfaceAlias)
        $state.Profile = [string]$rule.Profile
    }
    return $state
}

function AssertRuleSnapshot($item, $expected)
{
    $actual = GetRuleSnapshot $item.Kind $item.Name
    if ($null -eq $expected)
    {
        if ($null -ne $actual) { throw "Rule still exists: $($item.Name)" }
        return
    }
    if ($null -eq $actual) { throw "Rule missing: $($item.Name)" }
    foreach ($key in $expected.Keys)
    {
        $wanted = (@($expected[$key]) | Sort-Object) -join ','
        $observed = (@($actual[$key]) | Sort-Object) -join ','
        if ($key -eq 'Protocol')
        {
            $wanted = $wanted -replace '^256$', 'Any'
            $observed = $observed -replace '^256$', 'Any'
        }
        if ($key -eq 'VMCreatorId')
        {
            $wanted = $wanted.Trim('{}')
            $observed = $observed.Trim('{}')
        }
        if ($wanted -ne $observed) { throw "Rule verification failed: $($item.Name)/$key" }
    }
}

function SetRuleState($item, $values, [bool]$create)
{
    $arguments = @{Name=$item.Name; PolicyStore='PersistentStore'; ErrorAction='Stop'}
    foreach ($key in $values.Keys) { $arguments[$key] = $values[$key] }
    if ($create) { $arguments.DisplayName = $item.Name }
    if ($item.Kind -eq 'HyperV')
    {
        if ($create) { New-NetFirewallHyperVRule @arguments | Out-Null }
        else { Set-NetFirewallHyperVRule @arguments | Out-Null }
    }
    else
    {
        if ($create) { New-NetFirewallRule @arguments | Out-Null }
        else { Set-NetFirewallRule @arguments | Out-Null }
    }
}

$items = @(
    @{Kind='HyperV'; Name='G1-DDS-to-WSL'; Desired=@{
        Direction='Inbound'; VMCreatorId='{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}'
        Protocol='Any'; RemoteAddresses='192.168.123.0/24'; Action='Allow'; Enabled='True'; Profiles='Any'
    }},
    @{Kind='Host'; Name='G1-DDS-to-WSL-Host'; Desired=@{
        Direction='Inbound'; InterfaceAlias=$adapter.Name; Protocol='Any'
        RemoteAddress='192.168.123.0/24'; Action='Allow'; Enabled='True'; Profile='Any'
    }}
)
# Snapshot both rules before mutation; attempt every rollback even if one fails.
foreach ($item in $items) { $item.Previous = GetRuleSnapshot $item.Kind $item.Name }
$attempted = @()
try
{
    foreach ($item in $items)
    {
        $attempted += $item
        SetRuleState $item $item.Desired ($null -eq $item.Previous)
        AssertRuleSnapshot $item $item.Desired
    }
    'G1 DDS rules verified' | Set-Content -LiteralPath $status_path -Encoding ascii
}
catch
{
    $original_error = $_.Exception.Message
    $rollback_errors = @()
    try { if (Test-Path -LiteralPath $status_path) { Remove-Item -LiteralPath $status_path -Force } }
    catch { $rollback_errors += $_.Exception.Message }
    for ($i = $attempted.Count - 1; $i -ge 0; $i--)
    {
        $item = $attempted[$i]
        try
        {
            if ($null -ne $item.Previous) { SetRuleState $item $item.Previous $false }
            elseif ($null -ne (GetRuleSnapshot $item.Kind $item.Name))
            {
                if ($item.Kind -eq 'HyperV') { Remove-NetFirewallHyperVRule -Name $item.Name -PolicyStore PersistentStore -ErrorAction Stop }
                else { Remove-NetFirewallRule -Name $item.Name -PolicyStore PersistentStore -ErrorAction Stop }
            }
            AssertRuleSnapshot $item $item.Previous
        }
        catch { $rollback_errors += "$($item.Name): $($_.Exception.Message)" }
    }
    if ($rollback_errors.Count) { throw "DDS firewall update failed: $original_error. ROLLBACK FAILED: $($rollback_errors -join '; '). Inspect both local rules before retrying." }
    throw "DDS firewall update failed: $original_error. Previous local rule states restored."
}
