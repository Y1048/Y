"""IPv4 DNS recovery with mocked cmdlets and registry reads; no network changes."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

HELPER = Path(__file__).resolve().parents[2] / "tools/G1_ETHERNET_DNS.ps1"


@pytest.mark.parametrize("manual", ["", "192.0.2.1,192.0.2.2"])
@pytest.mark.parametrize("fault", ["none", "write", "verify", "rollback", "snapshot"])
def test_dns_mode_recovery(manual, fault):
    shell = shutil.which("powershell.exe")
    if not shell:
        pytest.skip("Windows PowerShell required")
    harness = r'''
$global:manual='MANUAL'
$global:calls=0
function Get-ItemProperty {
    param($LiteralPath,$ErrorAction)
    if ('FAULT' -eq 'snapshot') { throw 'registry read failed' }
    if ($LiteralPath -notlike '*\Tcpip\Parameters\Interfaces\*') { throw 'unexpected registry read' }
    [pscustomobject]@{NameServer=$global:manual}
}
function Get-DnsClientServerAddress {
    param($InterfaceIndex,$AddressFamily,$ErrorAction)
    if ($InterfaceIndex -ne 7 -or $AddressFamily -ne 'IPv4') { throw 'incorrect DNS selection' }
    [pscustomobject]@{InterfaceIndex=7;AddressFamily=2}
}
function Set-DnsClientServerAddress {
    param($InputObject,[switch]$ResetServerAddresses,$ServerAddresses,$ErrorAction)
    if ($InputObject.InterfaceIndex -ne 7 -or $InputObject.AddressFamily -ne 2) { throw 'incorrect DNS mutation scope' }
    $global:calls++
    if ('FAULT' -eq 'rollback' -and $global:calls -gt 1) { throw 'rollback write failed' }
    $global:manual=if ($ResetServerAddresses) { '' } else { $ServerAddresses -join ',' }
    if ($global:calls -eq 1) {
        if ('FAULT' -in @('write','rollback')) { throw 'partial DNS reset' }
        if ('FAULT' -eq 'verify') { $global:manual='192.0.2.99' }
    }
}
. 'HELPER'
$ok=$false
try {
    $snapshot=GetG1DnsSnapshot ([pscustomobject]@{ifIndex=7;InterfaceGuid='00000000-0000-0000-0000-000000000007'})
    ResetG1Dns $snapshot
    $ok=$true
} catch { $failure=$_.Exception.Message }
@{ok=$ok;failure=$failure;manual=$global:manual;calls=$global:calls} | ConvertTo-Json -Compress
'''.replace("MANUAL", manual).replace("FAULT", fault).replace("HELPER", str(HELPER))
    result = subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", harness], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is (fault == "none"), data["failure"]
    if fault == "none":
        assert data["manual"] == ""
        assert data["calls"] == 1
    elif fault == "rollback":
        assert "DNS ROLLBACK FAILED" in data["failure"]
    else:
        assert data["manual"] == manual
        if fault == "snapshot":
            assert data["calls"] == 0
        else:
            assert "Previous IPv4 DNS mode restored" in data["failure"]


@pytest.mark.parametrize("name", ["CONFIGURE_G1_ETHERNET_ADMIN.ps1", "RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1"])
def test_snapshot_precedes_ip_changes(name):
    source = (HELPER.parent / name).read_text(encoding="utf-8-sig")
    assert "InvokeG1EthernetChange $adapter" in source
    transaction = (HELPER.parent / "G1_ETHERNET_TRANSACTION.ps1").read_text()
    body = transaction.split("function InvokeG1EthernetChange", 1)[1]
    assert body.index("GetG1EthernetSnapshot $adapter") < body.index("SetG1Ipv4State $snapshot $desired")
    assert body.index("AssertG1Ipv4State $snapshot $desired") < body.index("ResetG1Dns $snapshot.Dns")
    assert "Set-DnsClientServerAddress" not in source
