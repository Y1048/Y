"""Exercise real transaction orchestration with network and DNS cmdlets mocked."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"


@pytest.mark.parametrize("automatic", [False, True])
@pytest.mark.parametrize("initial_dhcp", [False, True])
@pytest.mark.parametrize("fault", ["none", "write", "dns", "marker", "route", "stores", "rollback"])
def test_ethernet_transaction(automatic, initial_dhcp, fault):
    shell = shutil.which("powershell.exe")
    if not shell:
        pytest.skip("Windows PowerShell required")
    harness = r'''
$global:states=@{}
$global:initial=@{}
$global:count=0
$global:dns='192.0.2.53'
$global:marker=$false
$global:dns_failed=$false
foreach ($store in @('ActiveStore','PersistentStore')) {
    $addresses=@()
    if (-not INITIAL) { $addresses=@([pscustomobject]@{IPAddress='192.0.2.7';PrefixLength=24;SkipAsSource=$true;PrefixOrigin='Manual';Type='Unicast';ValidLifetime=[timespan]::MaxValue;PreferredLifetime=[timespan]::MaxValue}) }
    $mode=if (INITIAL) { 'Enabled' } else { 'Disabled' }
    $global:states[$store]=@{Dhcp=$mode;Addresses=$addresses}
    $global:initial[$store]=@{Dhcp=$mode;Addresses=$addresses}
}
function Get-NetAdapter { [pscustomobject]@{ifIndex=7;InterfaceGuid='00000000-0000-0000-0000-000000000007';Name='mock'} }
function Get-NetRoute {
    param($InterfaceIndex,$AddressFamily,$PolicyStore,$ErrorAction)
    if ('FAULT' -eq 'route') { [pscustomobject]@{Protocol='NetMgmt'} }
}
function Get-NetIPInterface {
    param($InterfaceIndex,$AddressFamily,$PolicyStore,$ErrorAction)
    $dhcp=$global:states[$PolicyStore].Dhcp
    if ('FAULT' -eq 'stores' -and $PolicyStore -eq 'PersistentStore') { $dhcp=if($dhcp -eq 'Enabled'){'Disabled'}else{'Enabled'} }
    [pscustomobject]@{Dhcp=$dhcp}
}
function Get-NetIPAddress { param($InterfaceIndex,$AddressFamily,$PolicyStore,$ErrorAction) $global:states[$PolicyStore].Addresses }
function CheckWrite($index,$family) {
    if ($index -ne 7 -or $family -ne 'IPv4') { throw 'wrong mutation scope' }
    $global:count++
    if ($global:count -eq 3 -and 'FAULT' -in @('write','rollback')) { throw 'injected write failure' }
    if ($global:count -gt 3 -and 'FAULT' -eq 'rollback') { throw 'injected rollback failure' }
}
function Set-NetIPInterface {
    param($InterfaceIndex,$AddressFamily,$PolicyStore,$Dhcp,$ErrorAction)
    $global:states[$PolicyStore].Dhcp=$Dhcp
    CheckWrite $InterfaceIndex $AddressFamily
}
function Remove-NetIPAddress {
    param($InterfaceIndex,$AddressFamily,$PolicyStore,$IPAddress,[switch]$Confirm,$ErrorAction)
    $global:states[$PolicyStore].Addresses=@($global:states[$PolicyStore].Addresses | Where-Object {$_.IPAddress -ne $IPAddress})
    CheckWrite $InterfaceIndex $AddressFamily
}
function New-NetIPAddress {
    param($InterfaceIndex,$AddressFamily,$PolicyStore,$IPAddress,$PrefixLength,$SkipAsSource,$ErrorAction)
    $global:states[$PolicyStore].Addresses+= [pscustomobject]@{IPAddress=$IPAddress;PrefixLength=$PrefixLength;SkipAsSource=$SkipAsSource;PrefixOrigin='Manual';Type='Unicast';ValidLifetime=[timespan]::MaxValue;PreferredLifetime=[timespan]::MaxValue}
    CheckWrite $InterfaceIndex $AddressFamily
}
function Get-ItemProperty { param($LiteralPath,$ErrorAction) [pscustomobject]@{NameServer=$global:dns} }
function Get-DnsClientServerAddress { param($InterfaceIndex,$AddressFamily,$ErrorAction) [pscustomobject]@{InterfaceIndex=7;AddressFamily=2} }
function Set-DnsClientServerAddress {
    param($InputObject,[switch]$ResetServerAddresses,$ServerAddresses,$ErrorAction)
    if ($InputObject.AddressFamily -ne 2) { throw 'wrong DNS family' }
    $global:dns=if($ResetServerAddresses){''}else{$ServerAddresses -join ','}
    if ('FAULT' -eq 'dns' -and -not $global:dns_failed) { $global:dns_failed=$true;throw 'DNS failed' }
}
function Test-Path { param($LiteralPath) $global:marker }
function Remove-Item { param($LiteralPath,[switch]$Force) $global:marker=$false }
function Set-Content { param($LiteralPath,$Encoding,[Parameter(ValueFromPipeline=$true)]$Value) $global:marker=$true;if('FAULT' -eq 'marker'){throw 'marker failed'} }
. 'TOOLS/G1_ETHERNET_DNS.ps1'
. 'TOOLS/G1_ETHERNET_TRANSACTION.ps1'
$ok=$false
try { InvokeG1EthernetChange (Get-NetAdapter) AUTOMATIC 'mock-marker';$ok=$true } catch { $failure=$_.Exception.Message }
@{ok=$ok;failure=$failure;states=$global:states;initial=$global:initial;count=$global:count;dns=$global:dns;marker=$global:marker} | ConvertTo-Json -Depth 8 -Compress
'''.replace("INITIAL", "$true" if initial_dhcp else "$false").replace("AUTOMATIC", "$true" if automatic else "$false").replace("FAULT", fault).replace("TOOLS", TOOLS.as_posix())
    result = subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", harness], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    success = fault == "none" or (fault == "marker" and automatic)
    assert data["ok"] is success, data["failure"]
    assert data["marker"] is (success and not automatic)
    if success:
        assert data["dns"] == ""
        for state in data["states"].values():
            assert state["Dhcp"] == ("Enabled" if automatic else "Disabled")
            assert len(state["Addresses"]) == (0 if automatic else 1)
            if not automatic:
                assert state["Addresses"][0]["IPAddress"] == "192.168.123.99"
    elif fault == "rollback":
        assert "ROLLBACK FAILED" in data["failure"]
        assert data["dns"] == "192.0.2.53"
    else:
        assert data["states"] == data["initial"]
        assert data["dns"] == "192.0.2.53"
        if fault in ("route", "stores"):
            assert data["count"] == 0
        else:
            assert "Previous IPv4 configuration and DNS restored" in data["failure"]
