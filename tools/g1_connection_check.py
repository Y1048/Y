"""Read-only teleop prerequisites. Never start workers, capture, SDK/DDS or motors."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shlex
import socket
import subprocess

from g1_ssh_login import identity_options, ssh_executable

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ('192.168.123.164', '192.168.10.165')
# File/system queries only. No SDK import, controller execution or camera stream.
REMOTE_INSPECT = r'''
import importlib.util, json, os, shutil
from pathlib import Path
root = Path('/home/unitree/groot_onboard_runtime')
by_id = Path('/dev/v4l/by-id')
cameras = {}
for path in sorted(by_id.glob('*Insta360*video-index0')):
    try:
        target = path.resolve(strict=True)
    except OSError:
        continue
    if target.name.startswith('video'):
        cameras[str(target)] = dict(name=path.name, device=str(target),
                                   readable=os.access(target, os.R_OK),
                                   writable=os.access(target, os.W_OK))
print(json.dumps(dict(schema='g1.connection.prerequisites.v1',
    hostname=os.uname().nodename,
    eth0=Path('/sys/class/net/eth0').is_dir(),
    sdk_present=importlib.util.find_spec('unitree_sdk2py') is not None,
    actuator=(root/'build/groot_balance_actuator').is_file() and os.access(root/'build/groot_balance_actuator',os.X_OK),
    heading=(root/'tools/g1_omni_heading_controller.py').is_file(),
    camera_follow=(root/'receive_mink_ik_udp.py').is_file(),
    v4l2_ctl=shutil.which('v4l2-ctl'), cameras=list(cameras.values()))))
'''


def tcp_probe(host):
    try:
        with socket.create_connection((host, 22), timeout=1.5) as connection:
            return dict(host=host, reachable=True, local_ip=connection.getsockname()[0])
    except OSError as error:
        return dict(host=host, reachable=False, error=str(error))


def inspect_remote(host, ssh):
    return subprocess.run(
        [ssh] + identity_options() + [
            '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UpdateHostKeys=no', '-o', 'ConnectTimeout=5',
            '-o', 'ClearAllForwardings=yes', '-o', 'PermitLocalCommand=no',
            '-o', 'ConnectionAttempts=1', 'unitree@' + host,
            'python3 -c ' + shlex.quote(REMOTE_INSPECT)],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=15, check=False)


def ssh_failure(stderr, code):
    text = stderr.lower()
    if 'remote host identification has changed' in text:
        return 'SSH_IDENTITY_CHANGED', 'Verify the replacement G1 identity before updating its known_hosts entry.'
    if 'host key verification failed' in text:
        return 'SSH_HOST_NOT_TRUSTED', 'Verify and enroll this G1 host identity first; no trust settings were changed.'
    if 'permission denied' in text or 'no supported authentication' in text:
        return 'SSH_LOGIN_FAILED', 'Register this PC key for unitree on this G1; no password or key was changed.'
    if code == 255:
        return 'SSH_CONNECTION_FAILED', 'Check the network/SSH server and review the diagnostic below.'
    return 'REMOTE_INSPECTION_FAILED', 'Check that remote python3 is available; no robot program was started.'


def check_connections(host='auto', output_dir=None):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', host):
        raise ValueError('host must be a hostname or IPv4 address')
    report = dict(schema='g1.connection.check.v1', checked_at=datetime.now(timezone.utc).isoformat(),
                  read_only=True, requested_host=host, selected_host=None, checks=[],
                  not_tested=['UDP delivery/ACK', 'live camera frames/PTZ', 'Quest hand tracking',
                              'policy/library compatibility', 'motor operation'])

    def record(name, status, detail, **data):
        report['checks'].append(dict(name=name, status=status, detail=detail, **data))
        print('[%s] %s: %s' % (status, name, detail), flush=True)

    print('READ-ONLY CONNECTION CHECK: no IP repair, login enrollment, capture or actuation.', flush=True)
    endpoints = [tcp_probe(candidate) for candidate in (CANDIDATES if host == 'auto' else (host,))]
    report['endpoints'] = endpoints
    selected = next((entry for entry in endpoints if entry['reachable']), None)
    if selected is None:
        record('network', 'FAIL', 'No candidate answers TCP 22. Check G1 power, cable, PC subnet or closed network. '
               'A different G1 IP requires --host <address>; auto only probes the two documented addresses.')
    else:
        host = report['selected_host'] = selected['host']
        record('network', 'PASS', 'PC %s -> %s:22 reachable; this alone does not identify a G1.' %
               (selected['local_ip'], host))

    remote = None
    try:
        ssh = ssh_executable()
        record('ssh_client', 'PASS', ssh)
    except RuntimeError as error:
        ssh = None
        record('ssh_client', 'FAIL', str(error))
    if selected and ssh:
        try:
            result = inspect_remote(host, ssh)
            if result.returncode:
                kind, action = ssh_failure(result.stderr, result.returncode)
                record(kind, 'FAIL', action, diagnostic=result.stderr[-2000:])
                if result.stderr.strip():
                    print(result.stderr[-2000:].strip(), flush=True)
            else:
                record('ssh_login', 'PASS', 'Existing host trust and unitree key login succeeded.')
                remote = json.loads(result.stdout)
                if (not isinstance(remote, dict) or remote.get('schema') != 'g1.connection.prerequisites.v1'
                        or any(type(remote.get(key)) is not bool for key in
                               ('eth0', 'sdk_present', 'actuator', 'heading', 'camera_follow'))
                        or not isinstance(remote.get('cameras'), list)):
                    raise ValueError('invalid remote inspection schema')
                for camera in remote['cameras']:
                    if (not isinstance(camera, dict) or not isinstance(camera.get('device'), str)
                            or type(camera.get('readable')) is not bool
                            or type(camera.get('writable')) is not bool):
                        raise ValueError('invalid camera inspection schema')
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            remote = None
            record('remote_inspection', 'FAIL', str(error))
    else:
        record('ssh_login', 'SKIP', 'Needs a reachable endpoint and working SSH client.')

    if remote is not None:
        report['remote'] = remote
        for key, label in [('eth0', 'G1 eth0 interface'), ('sdk_present', 'unitree_sdk2py installed'),
                           ('actuator', 'GROOT actuator executable'), ('heading', 'heading receiver source'),
                           ('camera_follow', 'camera follow helper')]:
            record(key, 'PASS' if remote[key] else 'FAIL', label + (' found.' if remote[key] else ' missing.'))
        cameras = remote['cameras']
        if len(cameras) != 1:
            record('camera_device', 'FAIL', 'Expected one Insta360 capture device; found %d. '
                   'Connect one intended camera and check its USB enumeration.' % len(cameras))
        else:
            camera = cameras[0]
            record('camera_device', 'PASS' if camera['readable'] and camera['writable'] else 'FAIL',
                   camera['device'] + '; read/write permissions checked, no stream opened.')
        record('camera_tool', 'PASS' if remote.get('v4l2_ctl') else 'FAIL',
               'v4l2-ctl ' + ('found.' if remote.get('v4l2_ctl') else 'missing on G1.'))
    else:
        record('onboard_and_camera', 'SKIP', 'Remote inspection was unavailable.')

    report['prerequisites_ok'] = all(row['status'] == 'PASS' for row in report['checks'])
    folder = Path(output_dir) if output_dir else ROOT / 'logs/test_results/connection_checks'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ('connection_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json')
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('REPORT: ' + str(path.resolve()), flush=True)
    print('PREREQUISITES ' + ('PASS' if report['prerequisites_ok'] else 'INCOMPLETE') +
          '; UDP, live video, hands and motor operation are NOT validated.', flush=True)
    return 0 if report['prerequisites_ok'] else 1
