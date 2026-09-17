"""Run the DDS firewall transaction only against in-process mock cmdlets."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "tools/ALLOW_G1_DDS_WSL_ADMIN.ps1"


@pytest.mark.parametrize("existing", [0, 1, 2, 3])
@pytest.mark.parametrize("fault", ["none", "hyper_write", "host_write", "verify", "marker", "rollback", "snapshot"])
def test_transaction(existing, fault):
    data = run_mock(existing, fault)
    assert data["ok"] is (fault == "none"), data["failure"]
    assert data["marker"] is (fault == "none")
    if fault == "none":
        for name, rule in data["rules"].items():
            assert rule["Action"] == "Allow"
            assert rule["Protocol"] == "Any"
            assert rule["RemoteAddresses" if name == "G1-DDS-to-WSL" else "RemoteAddress"] == "192.168.123.0/24"
        assert data["rules"]["G1-DDS-to-WSL-Host"]["InterfaceAlias"] == "Ethernet 1"
        assert data["removed"] == []
        for name in data["initial"]:
            assert data["rules"][name]["Untouched"] == "preserve"
    elif fault == "rollback":
        assert "ROLLBACK FAILED" in data["failure"]
        # A failed Host rollback must not prevent the Hyper-V rollback.
        assert data["rules"].get("G1-DDS-to-WSL") == data["initial"].get("G1-DDS-to-WSL")
    else:
        assert data["rules"] == data["initial"]
        if fault == "snapshot":
            assert data["writes"] == 0
        else:
            assert "Previous local rule states restored" in data["failure"]


@pytest.mark.parametrize("count,index,success", [(0, 0, False), (2, 0, False), (2, 2, True), (2, 8, False)])
def test_adapter_selection(count, index, success):
    data = run_mock(0, "none", count, index)
    assert data["ok"] is success, data["failure"]
    if not success:
        assert data["writes"] == 0
        assert "Expected one G1 ASIX adapter" in data["failure"]
    else:
        assert data["rules"]["G1-DDS-to-WSL-Host"]["InterfaceAlias"] == "Ethernet 2"


def run_mock(existing, fault, count=1, index=0):
    shell = shutil.which("powershell.exe")
    if not shell:
        pytest.skip("Windows PowerShell required")
    harness = r'''
$global:rules=@{}
$global:initial=@{}
$global:writes=0
$global:removed=@()
$global:marker=$false
$names=@('G1-DDS-to-WSL','G1-DDS-to-WSL-Host')
for ($i=0; $i -lt 2; $i++) {
    if ((EXISTING -band (1 -shl $i)) -ne 0) {
        $state=@{Direction='Outbound';Action='Block';Enabled='False';Protocol='TCP';Untouched='preserve'}
        if ($i -eq 0) { $state.VMCreatorId='old-id';$state.RemoteAddresses=@('10.0.0.0/8');$state.Profiles='Private' }
        else { $state.RemoteAddress=@('10.0.0.0/8');$state.InterfaceAlias=@('Old Ethernet');$state.Profile='Private' }
        $global:rules[$names[$i]]=$state.Clone(); $global:initial[$names[$i]]=$state.Clone()
    }
}
function Get-NetAdapter {
    for ($i=1; $i -le COUNT; $i++) { [pscustomobject]@{InterfaceDescription='ASIX AX88772A';ifIndex=$i;Name="Ethernet $i"} }
}
function ReadRule($name, $store) {
    if ($store -ne 'PersistentStore') { throw 'wrong store' }
    if ('FAULT' -eq 'snapshot' -and $name -eq 'G1-DDS-to-WSL-Host') { throw 'snapshot failed' }
    if ($global:rules.ContainsKey($name)) {
        $copy=$global:rules[$name].Clone();$copy.Name=$name
        if ($copy.Protocol -eq 'Any') { $copy.Protocol='256' }
        if ($copy.ContainsKey('VMCreatorId')) { $copy.VMCreatorId=$copy.VMCreatorId.Trim('{}') }
        [pscustomobject]$copy
    }
}
function Get-NetFirewallHyperVRule { param($PolicyStore,$ErrorAction) ReadRule 'G1-DDS-to-WSL' $PolicyStore }
function Get-NetFirewallRule { param($PolicyStore,$ErrorAction) ReadRule 'G1-DDS-to-WSL-Host' $PolicyStore }
function Get-NetFirewallPortFilter { param([Parameter(ValueFromPipeline=$true)]$InputObject) $InputObject }
function Get-NetFirewallAddressFilter { param([Parameter(ValueFromPipeline=$true)]$InputObject) $InputObject }
function Get-NetFirewallInterfaceFilter { param([Parameter(ValueFromPipeline=$true)]$InputObject) $InputObject }
function WriteRule($values) {
    if ($values.PolicyStore -ne 'PersistentStore') { throw 'wrong store' }
    $name=$values.Name
    $global:writes++
    if ('FAULT' -eq 'rollback' -and $global:writes -gt 2 -and $name -eq 'G1-DDS-to-WSL-Host') { throw 'restore failed' }
    if (-not $global:rules.ContainsKey($name)) { $global:rules[$name]=@{} }
    foreach ($key in $values.Keys) {
        if ($key -notin @('Name','PolicyStore','ErrorAction','DisplayName')) { $global:rules[$name][$key]=$values[$key] }
    }
    if ('FAULT' -eq 'hyper_write' -and $global:writes -eq 1) { throw 'hyper partial write' }
    if ('FAULT' -in @('host_write','rollback') -and $global:writes -eq 2) { throw 'host partial write' }
    if ('FAULT' -eq 'verify' -and $global:writes -eq 2) { $global:rules[$name].Action='Block' }
}
WRAPPERS
function DeleteRule($name) {
    if ('FAULT' -eq 'rollback' -and $name -eq 'G1-DDS-to-WSL-Host') { throw 'removal failed' }
    $global:removed+= $name; $global:rules.Remove($name)
}
function Remove-NetFirewallHyperVRule { param($Name,$PolicyStore,$ErrorAction) DeleteRule $Name }
function Remove-NetFirewallRule { param($Name,$PolicyStore,$ErrorAction) DeleteRule $Name }
function New-Item { param($ItemType,$Path,[switch]$Force) }
function Test-Path { param($LiteralPath) return $global:marker }
function Remove-Item { param($LiteralPath,[switch]$Force) $global:marker=$false }
function Set-Content { param($LiteralPath,$Encoding,[Parameter(ValueFromPipeline=$true)]$Value)
    $global:marker=$true; if ('FAULT' -eq 'marker') { throw 'marker write failed' }
}
$ok=$false
try { & 'SCRIPT' -InterfaceIndex INDEX; $ok=$true } catch { $failure=$_.Exception.Message }
@{ok=$ok;failure=$failure;rules=$global:rules;initial=$global:initial;writes=$global:writes;removed=$global:removed;marker=$global:marker} | ConvertTo-Json -Depth 6 -Compress
'''
    wrappers = []
    for kind in ("NetFirewallRule", "NetFirewallHyperVRule"):
        fields = "VMCreatorId,RemoteAddresses,Profiles" if kind.endswith("HyperVRule") else "InterfaceAlias,RemoteAddress,Profile"
        for action in ("New", "Set"):
            params = "Name,PolicyStore,ErrorAction,Direction,Action,Enabled,Protocol," + fields
            if action == "New":
                params += ",DisplayName"
            wrappers.append(f"function {action}-{kind} {{ param({','.join('$' + p for p in params.split(','))}) WriteRule $PSBoundParameters }}")
    harness = harness.replace("WRAPPERS", "\n".join(wrappers)).replace("EXISTING", str(existing)).replace("FAULT", fault).replace("COUNT", str(count)).replace("INDEX", str(index)).replace("SCRIPT", str(SCRIPT))
    result = subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", harness], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)
