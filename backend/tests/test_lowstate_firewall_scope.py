"""Execute the firewall script with every external/file operation mocked."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "tools/ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1"


@pytest.mark.parametrize("count,index,existing,fault,success", [
    (0, 0, False, "none", False), (2, 0, False, "none", False),
    (1, 0, False, "none", True), (2, 2, False, "none", True),
    (2, 7, False, "none", False), (1, 0, True, "none", True),
    (1, 0, True, "write", False), (1, 0, False, "write", False),
    (1, 0, True, "verify", False), (1, 0, False, "verify", False),
    (1, 0, True, "marker", False), (1, 0, False, "marker", False),
    (1, 0, True, "rollback", False), (1, 0, False, "rollback", False),
    (1, 0, True, "snapshot", False),
])
def test_scope_without_admin_or_network(count, index, existing, fault, success):
    powershell = shutil.which("powershell.exe")
    if not powershell:
        pytest.skip("Windows PowerShell required")
    harness = r'''
$script:rule = $null
$script:initial = @{Direction='Outbound'; Protocol='TCP'; LocalPort=@('1234');
    InterfaceAlias=@('Old Ethernet'); RemoteAddress=@('10.1.0.0/16');
    Action='Block'; Enabled='False'; Profile='Private'; Program='keep.exe'}
if (EXISTING) { $script:rule=$script:initial.Clone() }
$script:writes = 0
$script:removed = 0
$script:marker = $false
function Get-NetAdapter {
    for ($i=1; $i -le COUNT; $i++) {
        [pscustomobject]@{InterfaceDescription='ASIX AX88772A USB';ifIndex=$i;Name="Ethernet $i"}
    }
}
function Get-NetFirewallRule {
    param($PolicyStore,$ErrorAction)
    if ($PolicyStore -ne 'PersistentStore') { throw 'wrong store' }
    if ('FAULT' -eq 'snapshot') { throw 'snapshot failure' }
    if ($null -ne $script:rule) {
        $copy=$script:rule.Clone(); $copy.Name='G1-LowState-to-Windows'
        [pscustomobject]$copy
    }
}
function Get-NetFirewallPortFilter { param([Parameter(ValueFromPipeline=$true)]$InputObject) $InputObject }
function Get-NetFirewallAddressFilter { param([Parameter(ValueFromPipeline=$true)]$InputObject) $InputObject }
function Get-NetFirewallInterfaceFilter { param([Parameter(ValueFromPipeline=$true)]$InputObject) $InputObject }
function Remove-NetFirewallRule {
    param($Name,$PolicyStore,$ErrorAction)
    if ('FAULT' -eq 'rollback') { throw 'rollback removal failed' }
    $script:removed++; $script:rule=$null
}
function Set-NetFirewallRule {
    param($Name,$PolicyStore,$Direction,$Protocol,$LocalPort,$InterfaceAlias,$RemoteAddress,$Action,$Enabled,$Profile)
    if ($PolicyStore -ne 'PersistentStore') { throw 'wrong store' }
    $script:writes++
    if ('FAULT' -eq 'rollback' -and $script:writes -gt 1) { throw 'rollback update failed' }
    $program=if ($null -ne $script:rule) { $script:rule.Program } else { 'Any' }
    $script:rule=@{Direction=$Direction;Protocol=$Protocol;LocalPort=$LocalPort;
        InterfaceAlias=$InterfaceAlias;RemoteAddress=$RemoteAddress;Action=$Action;
        Enabled=$Enabled;Profile=$Profile;Program=$program}
    if ($script:writes -eq 1) {
        if ('FAULT' -in @('write','rollback')) { throw 'partial write failure' }
        if ('FAULT' -eq 'verify') { $script:rule.RemoteAddress='Any' }
    }
}
function New-NetFirewallRule {
    param($Name,$PolicyStore,$DisplayName,$Direction,$Protocol,$LocalPort,$InterfaceAlias,$RemoteAddress,$Action,$Enabled,$Profile)
    $PSBoundParameters.Remove('DisplayName') | Out-Null
    Set-NetFirewallRule @PSBoundParameters
}
function New-Item { param($ItemType,$Path,[switch]$Force) }
function Test-Path { param($LiteralPath) return $script:marker }
function Remove-Item { param($LiteralPath,[switch]$Force) $script:marker=$false }
function Set-Content {
    param($LiteralPath,$Encoding,[Parameter(ValueFromPipeline=$true)]$Value)
    $script:marker=$true
    if ('FAULT' -eq 'marker') { throw 'partial marker failure' }
}
$ok=$false
try { & 'SCRIPT' -InterfaceIndex INDEX; $ok=$true } catch { $failure=$_.Exception.Message }
@{ok=$ok;failure=$failure;rule=$script:rule;initial=$script:initial;writes=$script:writes;removed=$script:removed;marker=$script:marker} | ConvertTo-Json -Depth 4 -Compress
'''.replace("$script:", "$global:").replace("COUNT", str(count)).replace("INDEX", str(index)).replace("SCRIPT", str(SCRIPT)).replace("EXISTING", "$true" if existing else "$false").replace("FAULT", fault)
    result = subprocess.run([powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", harness],
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is success, data["failure"]
    assert data["marker"] is success
    if success:
        assert data["removed"] == 0
        assert data["rule"]["LocalPort"] == [5007, 5009]
        assert data["rule"]["InterfaceAlias"] == f"Ethernet {index or 1}"
        assert data["rule"]["RemoteAddress"] == "192.168.123.0/24"
        assert data["rule"]["Protocol"] == "UDP"
        assert data["rule"]["Program"] == ("keep.exe" if existing else "Any")
    elif fault == "none":
        assert data["writes"] == 0
        assert "Expected one G1 ASIX adapter" in data["failure"]
    elif fault == "rollback":
        assert "ROLLBACK FAILED" in data["failure"]
    else:
        assert data["rule"] == (data["initial"] if existing else None)
        if fault == "snapshot":
            assert data["writes"] == 0
            assert "snapshot failure" in data["failure"]
        else:
            assert "Previous local rule state restored" in data["failure"]
