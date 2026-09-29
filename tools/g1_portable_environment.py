"""Path-independent helpers for the current Windows SSH teleop path."""
from pathlib import Path
import socket

ROOT = Path(__file__).resolve().parents[1]


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
