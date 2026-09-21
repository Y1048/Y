"""Start input observation and the existing read-only camera, without motor control."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
from g1_ssh_login import ensure_login, remote_receiver_running

import G1_INPUT_OBSERVATION_LAUNCH as observation
from g1_portable_environment import wsl_prefix, camera_run, select_robot_host

ROOT = Path(__file__).resolve().parents[1]


def windows_arguments(command_line):
    argc = ctypes.c_int()
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
    argv = parse(command_line, ctypes.byref(argc))
    if not argv:
        raise RuntimeError('Cannot inspect an existing process command line')
    try:
        return [argv[i] for i in range(argc.value)]
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(ctypes.cast(argv, ctypes.c_void_p))


def process_arguments():
    # Restrict inspection to relevant executables; never dump unrelated tokens.
    query = ("$ErrorActionPreference='Stop'; "
             "[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
             "@(Get-CimInstance Win32_Process | Where-Object { "
             "$_.Name -in @('python.exe','pythonw.exe','ssh.exe') } | "
             "Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine) | ConvertTo-Json -Compress")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', query],
                            capture_output=True, text=True, encoding='utf-8',
                            check=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    rows = json.loads(result.stdout or '[]') or []
    if isinstance(rows, dict):
        rows = [rows]
    return collapse_venv_redirectors(rows, ROOT)


def collapse_venv_redirectors(rows, root):
    """Count a Windows venv redirector + its identical child once, not unrelated copies."""
    parsed = [(row, windows_arguments(row['CommandLine'])) for row in rows
              if row.get('CommandLine')]
    by_pid = {row['ProcessId']: (row, argv) for row, argv in parsed}
    normalize = lambda value: str(value).replace('\\', '/').casefold()
    redirector = normalize(root / '.venv-teleop/Scripts/python.exe')
    suppressed = set()
    for row, argv in parsed:
        parent = by_pid.get(row.get('ParentProcessId'))
        if parent is None:
            continue
        parent_row, parent_argv = parent
        if (normalize(parent_row.get('ExecutablePath') or '') == redirector
                and Path(row.get('ExecutablePath') or '').name.casefold() == 'python.exe'
                and normalize(row.get('ExecutablePath') or '') != redirector
                and argv[1:] == parent_argv[1:]):
            suppressed.add(parent_row['ProcessId'])
    return [argv for row, argv in parsed if row['ProcessId'] not in suppressed]


def option(argv, flag):
    try:
        return argv[argv.index(flag) + 1]
    except (ValueError, IndexError):
        return None


def running_workers(rows, root, host):
    """Recognize active children, not launch windows waiting after a child exits."""
    paths = {
        'send': root / 'tools/G1_INPUT_RECEIVE_AUDIT.py',
        'omni': root / 'hardware/g1_arm_bridge/g1_omni_velocity_gateway.py',
        'arm': root / 'MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py',
    }
    normalize = lambda value: str(value).replace('\\', '/').casefold()
    found = set()
    remote = observation.worker_command('receive', host, '')[-1]
    for argv in rows:
        if not argv:
            continue
        if Path(argv[0]).name.lower() == 'ssh.exe':
            if 'unitree@' + host in argv and remote in argv:
                if 'receive' in found:
                    raise RuntimeError('Duplicate receive processes found; no extra window was started.')
                found.add('receive')
            continue
        for worker, path in paths.items():
            if normalize(path) not in [normalize(arg) for arg in argv[1:]]:
                continue
            valid = {
                'send': 'send-live' in argv and option(argv, '--host') == host
                        and option(argv, '--send-hz') == str(observation.COMPUTE_HZ),
                'omni': '--dry-run' in argv and option(argv, '--process-hz') == str(observation.COMPUTE_HZ),
                'arm': option(argv, '--mode') == 'unity'
                       and option(argv, '--compute-hz') == str(observation.COMPUTE_HZ),
            }[worker]
            if not valid:
                raise RuntimeError('An existing %s process has different options. '
                                   'Keep it or close its own window before starting this launcher.' % worker)
            if worker in found:
                raise RuntimeError('Duplicate %s processes found; no extra window was started.' % worker)
            found.add(worker)
    return found


def camera_running():
    result = subprocess.run(
        wsl_prefix() + ['bash', '-lc',
         "pgrep -af '[p]ython.*g1_camera_tcp_bridge[.]py'"],
        capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode not in (0, 1):
        raise RuntimeError('Cannot inspect the WSL camera bridge; no windows were started.')
    if result.returncode == 1:
        return False
    rows = result.stdout.decode('utf-8').splitlines()
    for row in rows:
        argv = shlex.split(row)
        if (not any(arg.endswith('g1_camera_tcp_bridge.py') for arg in argv)
                or option(argv, '--port') not in (None, '5011')
                or option(argv, '--host') not in (None, 'localhost', '127.0.0.1')):
            raise RuntimeError('Existing camera process has different options; no extra camera was started.')
    if not rows:
        raise RuntimeError('Camera process inspection returned no details')
    # TCP 5011 belongs to Unity's listener, not this outgoing camera client.
    return True


def preflight(missing, env):
    for executable in ('ssh.exe', 'wsl.exe'):
        if not shutil.which(executable):
            raise RuntimeError(executable + ' is missing')
    for worker, port in (('send', 55071), ('arm', 5020)):
        if worker not in missing:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                sock.bind(('127.0.0.1', port))
            except OSError as error:
                raise RuntimeError('UDP %d is occupied by another process; nothing was stopped.' % port) from error
    if 'omni' in missing:
        subprocess.run([sys.executable, '-B', '-c', 'import websocket'], check=True, env=env)
    if 'arm' in missing:
        subprocess.run([sys.executable, '-B', str(ROOT / 'tools/g1_portable_environment.py')], cwd=ROOT, env=env, check=True)
    if 'camera' in missing:
        camera_run('--check-only', '192.168.123.164')
    if not (ROOT / 'tools/START_G1_CAMERA_TO_UNITY.bat').is_file():
        raise RuntimeError('Existing camera BAT is missing')


def launch_plan(existing, has_camera, no_receiver=False):
    return [worker for worker in observation.WORKERS if worker not in existing
            and not (worker == 'receive' and no_receiver)] + ([] if has_camera else ['camera'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='auto', help='auto: wired address first, then closed network')
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--no-receiver', action='store_true',
                        help='Keep a G1 receive window started separately, e.g. on another PC.')
    parser.add_argument('--show-consoles', action='store_true', help='Show legacy diagnostic windows')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', args.host):
        parser.error('host must be a hostname or IPv4 address')
    if os.name != 'nt':
        raise RuntimeError('Use this launcher on Windows')
    args.host = select_robot_host(args.host)
    process_rows = process_arguments()
    existing = running_workers(process_rows, ROOT, args.host)
    camera_rows = [row for row in process_rows if any(
        arg.replace('\\','/').endswith('tools/G1_CAMERA_LAUNCH.py') for arg in row)]
    if len(camera_rows) > 1:
        raise RuntimeError('Duplicate camera launchers; preserve existing sessions')
    if camera_rows and option(camera_rows[0], '--robot-host') != args.host:
        raise RuntimeError('Existing camera targets another host; preserved')
    has_camera = bool(camera_rows) or camera_running()
    plan = launch_plan(existing, has_camera, args.no_receiver)
    env = observation.engine_environment()
    preflight(plan, env)
    print('G1 VR TELEOP: bilateral IK + Omni observation + front camera. NO MOTOR OUTPUT.')
    print('[KEEP] ' + (', '.join(sorted(existing | ({'camera'} if has_camera else set()))) or 'none'))
    print('[START] ' + (', '.join(plan) or 'none; existing processes are kept'))
    if args.check_only:
        print('PASS: launch plan checked; no workers, camera SDK initialization or SSH login. Auto mode probes TCP 22 only.')
        return 0
    if 'receive' in plan:
        ensure_login(args.host)
        if remote_receiver_running(args.host, observation.REMOTE_DIR):
            plan.remove('receive')
    if not args.show_consoles:
        from g1_quiet_observation import run_workers
        if 'camera' in plan:
            subprocess.Popen(['cmd.exe', '/d', '/c', r'tools\START_G1_CAMERA_TO_UNITY.bat',
                              '--robot-host', args.host], cwd=ROOT, env=env,
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
        workers = [worker for worker in plan if worker != 'camera']
        if workers:
            return run_workers(ROOT, workers, args.host, env)
        print('Existing workers kept. Close their original windows to stop them.')
        return 0
    for worker in plan:
        command = (['cmd.exe', '/d', '/c', r'tools\START_G1_CAMERA_TO_UNITY.bat', '--robot-host', args.host]
                   if worker == 'camera' else
                   [sys.executable, '-u', '-B', str(ROOT / 'tools/G1_INPUT_OBSERVATION_LAUNCH.py'),
                    '--worker', worker, '--host', args.host])
        subprocess.Popen(command, cwd=ROOT, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
    print('Use Unity Play and Omni Connect. Log in in the receive window if opened.')
    print('Input compute/send: 60 Hz; observation display: 100 Hz; camera: up to 20 fps.')
    print('Close each observation/camera window to stop it. Unity Play is not changed automatically.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print('G1 VR TELEOP START FAILED: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
