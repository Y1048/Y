"""Path-independent helpers for the current Windows SSH teleop path."""
from pathlib import Path
import socket
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def dedicated_wired_adapter_needing_address():
    """Return a safely inferred direct-wired Ethernet index that needs the G1 PC address.

    Read-only Windows inspection. Vendor names are irrelevant. Missing Ethernet,
    an Internet-routed link, or ambiguous linked Ethernet is never changed.
    """
    selector = str(ROOT / 'tools/G1_ETHERNET_ADAPTER.ps1').replace("'", "''")
    query = (
        "$ErrorActionPreference='Stop'; "
        f". '{selector}'; "
        "$physical=@(GetG1PhysicalEthernetAdapters); "
        "$configured=@($physical | Where-Object { TestG1Ipv4Address $_ }); "
        "if($configured.Count -eq 1 -and [string]$configured[0].Status -eq 'Up'){exit 0}; "
        "if(@($configured | Where-Object { [string]$_.Status -eq 'Up' }).Count -gt 1){"
        "throw 'Ambiguous connected G1 Ethernet adapters'}; "
        "$linked=@($physical | Where-Object { [string]$_.Status -eq 'Up' }); "
        "if($linked.Count -eq 0){exit 0}; "
        "if($linked.Count -ne 1){throw 'Ambiguous connected physical Ethernet adapters'}; "
        "$default=@(Get-NetRoute -InterfaceIndex $linked[0].ifIndex -AddressFamily IPv4 "
        "-PolicyStore ActiveStore -ErrorAction SilentlyContinue | "
        "Where-Object { [string]$_.DestinationPrefix -eq '0.0.0.0/0' }); "
        "if($default.Count -gt 0){exit 0}; "
        "$ip=@(Get-NetIPAddress -InterfaceIndex $linked[0].ifIndex "
        "-AddressFamily IPv4 -PolicyStore ActiveStore -ErrorAction SilentlyContinue | "
        "Where-Object { $_.IPAddress -eq '192.168.123.99' -and $_.PrefixLength -eq 24 }); "
        "if($ip.Count -eq 0){Write-Output $linked[0].ifIndex}"
    )
    completed = subprocess.run(
        ['powershell.exe', '-NoProfile', '-Command', query],
        capture_output=True, text=True, encoding='utf-8', timeout=15,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            'Cannot infer one dedicated G1 Ethernet adapter safely; '
            'no network setting changed. Use CONFIGURE_G1_ETHERNET.bat '
            '--interface-index <ifIndex> once for an ambiguous PC.')
    result = completed.stdout.strip()
    if not result:
        return None
    if not result.isdecimal() or int(result) <= 0:
        raise RuntimeError('Invalid G1 Ethernet adapter index; no network setting changed')
    return int(result)


def select_robot_host(requested='auto'):
    """Prefer the wired-address endpoint, then the closed-network endpoint.

    TCP 22 reachability only: not a login, DDS probe, or motor command.
    """
    if requested != 'auto':
        return requested
    for host, label in (('192.168.123.164', 'wired address'),
                        ('192.168.10.165', 'closed network')):
        try:
            with socket.create_connection((host, 22), timeout=1.5):
                print('[G1 NETWORK] ' + label + ' -> ' + host, flush=True)
                print('[G1 NETWORK] SSH port reachable; UDP ACK and camera are checked separately.',
                      flush=True)
                return host
        except OSError:
            continue
    raise RuntimeError('G1 unavailable on both 192.168.123.164:22 and 192.168.10.165:22. '
                       'Connect robot Ethernet or the closed network. No workers started.')


def check_python():
    """Import the complete current IK graph and build its model; no sockets/viewer."""
    import sys
    sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
    import g1_bimanual_runtime as runtime
    runtime.load_engine()
    import websocket
    import ruckig
    import qpsolvers
    if 'daqp' not in qpsolvers.available_solvers:
        raise RuntimeError('DAQP solver is unavailable')
    from g1_bimanual_sim import BimanualSimulation
    BimanualSimulation()
    print('PASS: complete IK imports and model construction; no transport or viewer.')


if __name__ == '__main__':
    check_python()
