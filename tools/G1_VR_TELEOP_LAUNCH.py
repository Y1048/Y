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
from g1_ssh_login import ensure_login

import G1_INPUT_OBSERVATION_LAUNCH as observation
from g1_portable_environment import wsl_prefix, camera_run, select_robot_host

ROOT = Path(__file__).resolve().parents[1]
INTEGRATED_WORKERS = observation.WORKERS + ('lowstate',)
UNITY_VERSION = '6000.5.4f1'
UNITY_PROJECT = ROOT / 'Unity_G1_VR'


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
             "$_.Name -in @('python.exe','pythonw.exe','ssh.exe','Unity.exe') } | "
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


def option_casefold(argv, flag):
    folded = [arg.casefold() for arg in argv]
    try:
        return argv[folded.index(flag.casefold()) + 1]
    except (ValueError, IndexError):
        return None


def normalized_path(value):
    return str(Path(value).resolve(strict=False)).replace('\\', '/').casefold()


def unity_project_running(rows, project=UNITY_PROJECT):
    """Reuse any Unity instance that explicitly owns this exact project."""
    target = normalized_path(project)
    matches = []
    for argv in rows:
        if not argv or Path(argv[0]).name.casefold() != 'unity.exe':
            continue
        folded = [arg.casefold() for arg in argv]
        # AssetImportWorker is another Unity.exe with the same project path,
        # but it is a child worker rather than another editor window.
        if '-adb2' in folded or '-batchmode' in folded or any(
                arg.startswith('assetimportworker') for arg in folded):
            continue
        project_arg = option_casefold(argv, '-projectPath')
        if project_arg and normalized_path(project_arg) == target:
            matches.append(argv)
    return bool(matches)


def resolve_unity_editor(environment=None):
    """Match RESOLVE_UNITY_EDITOR.bat without starting Unity or Unity Hub."""
    environment = os.environ if environment is None else environment
    candidates = []
    if environment.get('UNITY_EXE'):
        candidates.append(Path(environment['UNITY_EXE']))
    if environment.get('ProgramFiles'):
        candidates.append(Path(environment['ProgramFiles']) / 'Unity/Hub/Editor' /
                          UNITY_VERSION / 'Editor/Unity.exe')
    if environment.get('USERPROFILE'):
        candidates.append(Path(environment['USERPROFILE']) / 'Unity/Hub/Editor' /
                          UNITY_VERSION / 'Editor/Unity.exe')
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError('Unity %s was not found. Install it with Unity Hub or set UNITY_EXE.' % UNITY_VERSION)


def validate_unity_project(project=UNITY_PROJECT):
    version_file = project / 'ProjectSettings/ProjectVersion.txt'
    if not version_file.is_file():
        raise RuntimeError('Unity_G1_VR project metadata is missing')
    expected = 'm_EditorVersion: ' + UNITY_VERSION
    if expected not in version_file.read_text(encoding='utf-8'):
        raise RuntimeError('Unity_G1_VR is not pinned to Unity ' + UNITY_VERSION)


def start_unity(editor, project=UNITY_PROJECT):
    """Start the editor outside the later quiet-worker job object; never enter Play."""
    subprocess.Popen([str(editor), '-projectPath', str(project.resolve())],
                     cwd=ROOT,
                     creationflags=(subprocess.DETACHED_PROCESS |
                                    subprocess.CREATE_NEW_PROCESS_GROUP))


def running_workers(rows, root, host):
    """Recognize active children, not launch windows waiting after a child exits."""
    paths = {
        'lowstate': root / 'tools/g1_lowstate_view.py',
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
                'lowstate': option(argv, '--host') == host,
                'send': 'send-live' in argv and option(argv, '--host') == host
                        and option(argv, '--send-hz') == str(observation.COMPUTE_HZ),
                'omni': '--dry-run' in argv and option(argv, '--process-hz') == str(observation.COMPUTE_HZ),
                'arm': option(argv, '--mode') == 'unity'
                       and option(argv, '--compute-hz') == str(observation.COMPUTE_HZ)
                       and '--headless' in argv,
            }[worker]
            if not valid:
                raise RuntimeError('An existing %s process has different options. '
                                   'Keep it or close its own window before starting this launcher.' % worker)
            if worker in found:
                raise RuntimeError('Duplicate %s processes found; no extra window was started.' % worker)
            found.add(worker)
    return found


def camera_running():
    # Legacy WSL diagnostic only; never called by default SSH orchestration.
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
    for executable in ('ssh.exe',):
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
        from g1_camera_ssh import check_environment
        check_environment()
    if not (ROOT / 'tools/START_G1_CAMERA_TO_UNITY.bat').is_file():
        raise RuntimeError('Existing camera BAT is missing')


def launch_plan(existing, has_camera, no_receiver=False):
    return [worker for worker in INTEGRATED_WORKERS if worker != 'receive' and worker not in existing] + ([] if has_camera else ['camera'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='auto', help='auto: wired address first, then closed network')
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--no-receiver', action='store_true',
                        help='Compatibility flag; this launcher never starts a G1 audit receiver.')
    parser.add_argument('--show-consoles', action='store_true', help='Show legacy diagnostic windows')
    parser.add_argument('--no-unity', action='store_true',
                        help='Start/reuse observation workers without opening the Unity editor.')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', args.host):
        parser.error('host must be a hostname or IPv4 address')
    if os.name != 'nt':
        raise RuntimeError('Use this launcher on Windows')
    args.host = select_robot_host(args.host)
    process_rows = process_arguments()
    has_unity = unity_project_running(process_rows)
    existing = running_workers([row for row in process_rows
                                if row and Path(row[0]).name.lower() != 'ssh.exe'], ROOT, args.host)
    camera_rows = [row for row in process_rows if any(
        arg.replace('\\','/').endswith('tools/G1_CAMERA_LAUNCH.py') for arg in row)]
    if len(camera_rows) > 1:
        raise RuntimeError('Duplicate camera launchers; preserve existing sessions')
    if camera_rows and option(camera_rows[0], '--robot-host') != args.host:
        raise RuntimeError('Existing camera targets another host; preserved')
    has_camera = bool(camera_rows)
    plan = launch_plan(existing, has_camera, args.no_receiver)
    env = observation.engine_environment()
    preflight(plan, env)
    unity_editor = None
    if not args.no_unity:
        validate_unity_project()
        if not has_unity:
            unity_editor = resolve_unity_editor()
    print('G1 VR TELEOP: bilateral IK + Omni observation + front camera. NO MOTOR OUTPUT.')
    print('[KEEP] ' + (', '.join(sorted(existing | ({'camera'} if has_camera else set()))) or 'none'))
    print('[START] ' + (', '.join(plan) or 'none; existing processes are kept'))
    if args.no_unity:
        print('[UNITY] disabled by --no-unity')
    elif has_unity:
        print('[UNITY] existing Unity_G1_VR editor kept')
    else:
        print('[UNITY] open Unity_G1_VR with Unity ' + UNITY_VERSION)
    if args.check_only:
        print('PASS: launch plan checked; no Unity, workers, camera SDK initialization or SSH login. Auto mode probes TCP 22 only.')
        return 0
    if 'lowstate' in plan:
        ensure_login(args.host)
    if unity_editor is not None:
        # This must precede run_workers(): that function binds its own process to
        # a kill-on-close job, while Unity must remain independently user-owned.
        start_unity(unity_editor)
    if not args.show_consoles:
        from g1_quiet_observation import run_workers
        if plan:
            return run_workers(ROOT, plan, args.host, env)
        print('Existing workers kept. Close their original windows to stop them.')
        return 0
    for worker in plan:
        command = (['cmd.exe', '/d', '/c', r'tools\START_G1_CAMERA_TO_UNITY.bat', '--robot-host', args.host]
                   if worker == 'camera' else
                   [sys.executable, '-u', '-B', str(ROOT / 'tools/G1_INPUT_OBSERVATION_LAUNCH.py'),
                    '--worker', worker, '--host', args.host])
        subprocess.Popen(command, cwd=ROOT, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
    print('Unity_G1_VR is open. Press Play in Unity, then use Quest and Omni Connect.')
    print('Input compute/send: 60 Hz; observation display: 100 Hz; camera: up to 20 fps.')
    print('Close each observation/camera window to stop it. Unity Play is not changed automatically.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print('G1 VR TELEOP START FAILED: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
