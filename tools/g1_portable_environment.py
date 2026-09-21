"""Path-independent Windows/WSL helpers. No SDK initialization or robot traffic."""
import os
from pathlib import Path
import subprocess
import socket
import re
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
CAMERA_SOURCES = (
    ('cyclonedds', 'https://github.com/eclipse-cyclonedds/cyclonedds.git',
     '9995905bce6c4cf9f740d6438bbf7fcfd1c83dfd'),
    ('sdk', 'https://github.com/unitreerobotics/unitree_sdk2_python.git',
     '9c519023d188bfe4643d326868474878ab515ed8'),
)


def select_robot_host(requested='auto'):
    """Prefer the wired-address endpoint, then closed-network endpoint.

    TCP 22 reachability only: not a login, DDS probe, or motor command.
    """
    if requested != 'auto':
        return requested
    for host, label in (('192.168.123.164', 'wired address'),
                        ('192.168.10.165', 'closed network')):
        try:
            with socket.create_connection((host, 22), timeout=1.5):
                print('[G1 NETWORK] ' + label + ' -> ' + host, flush=True)
                print('[G1 NETWORK] SSH port reachable; UDP ACK and camera are checked separately.', flush=True)
                return host
        except OSError:
            continue
    raise RuntimeError('G1 unavailable on both 192.168.123.164:22 and 192.168.10.165:22. '
                       'Connect robot Ethernet or the closed network. No workers started.')


def prepare_camera_sources():
    # Download on Windows, where corporate/VPN proxy settings already work.
    # WSL receives a pinned archive; it does not need GitHub connectivity.
    cache = ROOT / 'logs/setup/camera_sources'
    cache.mkdir(parents=True, exist_ok=True)
    for name, url, revision in CAMERA_SOURCES:
        source = cache / name
        if not source.exists():
            subprocess.run(['git', 'init', str(source)], check=True)
            subprocess.run(['git', '-C', str(source), 'remote', 'add', 'origin', url], check=True)
        actual_url = subprocess.check_output(['git', '-C', str(source), 'remote', 'get-url', 'origin'], text=True).strip()
        if actual_url != url:
            raise RuntimeError('Unexpected camera source origin; existing files preserved: ' + str(source))
        dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True)
        if dirty.strip():
            raise RuntimeError('Modified camera source cache; existing files preserved: ' + str(source))
        head = subprocess.run(['git', '-C', str(source), 'rev-parse', '--verify', 'HEAD'], capture_output=True, text=True)
        if head.returncode:
            subprocess.run(['git', '-C', str(source), 'fetch', '--depth', '1', 'origin', revision], check=True)
            subprocess.run(['git', '-C', str(source), 'checkout', '--detach', revision], check=True)
        elif head.stdout.strip() != revision:
            raise RuntimeError('Unexpected camera source revision; existing files preserved')
        subprocess.run(['git', '-C', str(source), 'archive', '--format=tar',
                        '-o', str(cache / (name + '-' + revision + '.tar')), revision], check=True)


def configure_mirrored_network(path):
    """Merge only networkingMode, keeping other WSL settings and a byte backup.

    Never shuts down WSL; the operator applies it after closing existing jobs.
    """
    path = Path(path)
    raw = path.read_bytes() if path.exists() else b''
    encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    lines = raw.decode(encoding).splitlines()
    section = None
    sections, keys = [], []
    for index, line in enumerate(lines):
        header = re.fullmatch(r'\s*\[([^]]+)\]\s*', line)
        if header:
            section = header.group(1).casefold()
            if section == 'wsl2':
                sections.append(index)
        elif section == 'wsl2' and re.match(r'\s*networkingmode\s*=', line, re.I):
            keys.append(index)
    if len(sections) > 1 or len(keys) > 1:
        raise RuntimeError('Ambiguous .wslconfig; preserved. Merge networkingMode=mirrored manually.')
    if keys:
        if lines[keys[0]].split('=', 1)[1].strip().casefold() == 'mirrored':
            return False
        lines[keys[0]] = 'networkingMode=mirrored'
    elif sections:
        lines.insert(sections[0] + 1, 'networkingMode=mirrored')
    else:
        lines += ['', '[wsl2]', 'networkingMode=mirrored']
    if path.exists():
        backup = path.with_name(path.name + '.g1-backup-' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        backup.write_bytes(raw)
    path.write_text('\n'.join(lines).lstrip('\n') + '\n', encoding='utf-8')
    return True


def wsl_prefix():
    distro = os.environ.get('G1_WSL_DISTRO')
    return ['wsl.exe'] + (['-d', distro] if distro else []) + ['--']


def wsl_path(path):
    result = subprocess.run(wsl_prefix() + ['wslpath', '-a', '-u', str(path).replace('\\', '/')],
                            capture_output=True, text=True, encoding='utf-8', check=True)
    value = result.stdout.strip()
    if not value.startswith('/') or '\n' in value:
        raise RuntimeError('WSL path conversion failed')
    return value


def camera_command(*args):
    # Read the script on Windows and pass LF text via stdin: Git CRLF checkout is OK.
    script = ROOT / 'hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh'
    command = wsl_prefix() + ['bash', '-s', '--', wsl_path(ROOT), *args]
    return command, script.read_text(encoding='utf-8')


def camera_run(*args):
    if args and args[0] == '--setup':
        prepare_camera_sources()
    command, script = camera_command(*args)
    return subprocess.run(command, input=script.encode('utf-8'), check=True)


def check_python():
    """Import the entire IK graph and build its model, with no sockets/viewer."""
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
