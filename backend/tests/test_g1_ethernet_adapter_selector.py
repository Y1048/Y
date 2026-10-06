"""Offline tests for vendor-neutral G1 Ethernet adapter selection."""

import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
SELECTOR = ROOT / "tools/G1_ETHERNET_ADAPTER.ps1"
CONFIGURE = ROOT / "tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1"
RESTORE = ROOT / "tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1"


@unittest.skipUnless(os.name == "nt", "PowerShell adapter selector is Windows-only")
class EthernetAdapterSelectorTests(unittest.TestCase):
    def test_mock_selection_matrix(self):
        selector = str(SELECTOR).replace("'", "''")
        script = rf"""
$ErrorActionPreference='Stop'
$selector='{selector}'
function New-A($i,$name,$status,$media,$physical,$virtual=$false,$hardware=$true,$connector=$true){{
 [pscustomobject]@{{ifIndex=$i;Name=$name;InterfaceDescription=$name;Status=$status;MediaType=$media;PhysicalMediaType=$physical;Virtual=$virtual;HardwareInterface=$hardware;ConnectorPresent=$connector}}
}}
function New-IP($i,$ip,$prefix){{[pscustomobject]@{{InterfaceIndex=$i;IPAddress=$ip;PrefixLength=$prefix}}}}
function Run-Case($name,$mode,$index,$adapters,$ips,$expectIndex,$expectError){{
  $global:MockAdapters=$adapters
  $global:MockIps=$ips
  function global:Get-NetAdapter {{ param([switch]$IncludeHidden) return @($global:MockAdapters) }}
  function global:Get-NetIPAddress {{ param([int]$InterfaceIndex,[string]$AddressFamily,[object]$ErrorAction) return @($global:MockIps|Where-Object{{$_.InterfaceIndex -eq $InterfaceIndex}}) }}
  . $selector
  try{{
    $x=GetG1EthernetAdapter -InterfaceIndex $index -Mode $mode
    if($expectError){{throw "$name expected error but selected $($x.ifIndex)"}}
    if($x.ifIndex -ne $expectIndex){{throw "$name selected $($x.ifIndex), expected $expectIndex"}}
    Write-Output "$name PASS"
  }}catch{{
    if(-not $expectError){{throw}}
    Write-Output "$name PASS"
  }}
}}
$wifi=New-A 21 'WiFi' 'Up' 'Native 802.11' 'Native 802.11'
$realtek=New-A 19 'Realtek' 'Up' '802.3' '802.3'
$intel=New-A 18 'Intel' 'Disconnected' '802.3' '802.3'
Run-Case 'single-linked-ethernet' 'Configure' 0 @($wifi,$realtek) @() 19 $false
Run-Case 'prefer-existing-g1-ip' 'Configure' 0 @($realtek,$intel) @((New-IP 18 '192.168.123.99' 24)) 18 $false
Run-Case 'ambiguous-two-linked' 'Configure' 0 @($realtek,(New-A 17 'USB-LAN' 'Up' '802.3' '802.3')) @() 0 $true
Run-Case 'restore-disconnected-configured' 'Restore' 0 @($realtek,$intel) @((New-IP 18 '192.168.123.99' 24)) 18 $false
Run-Case 'explicit-disconnected' 'Configure' 18 @($realtek,$intel) @() 18 $false
Run-Case 'explicit-wifi-rejected' 'Configure' 21 @($wifi,$realtek) @() 0 $true
"""
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=True,
        )
        for name in (
            "single-linked-ethernet",
            "prefer-existing-g1-ip",
            "ambiguous-two-linked",
            "restore-disconnected-configured",
            "explicit-disconnected",
            "explicit-wifi-rejected",
        ):
            self.assertIn(name + " PASS", result.stdout)

    def test_admin_scripts_use_shared_vendor_neutral_selector(self):
        selector = SELECTOR.read_text(encoding="utf-8-sig")
        configure = CONFIGURE.read_text(encoding="utf-8-sig")
        restore = RESTORE.read_text(encoding="utf-8-sig")
        self.assertNotIn("ASIX AX88772A", selector)
        self.assertNotIn("ASIX AX88772A", configure)
        self.assertNotIn("ASIX AX88772A", restore)
        self.assertIn("HardwareInterface", selector)
        self.assertIn("MediaType", selector)
        self.assertIn("GetG1EthernetAdapter", configure)
        self.assertIn("-Mode Configure", configure)
        self.assertIn("GetG1EthernetAdapter", restore)
        self.assertIn("-Mode Restore", restore)


if __name__ == "__main__":
    unittest.main()
