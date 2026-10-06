"""Start integrated VR teleop observation, camera, and confirmed GROOT actuation."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import sys
from g1_ssh_login import ensure_login, ssh_executable
from g1_camera_ssh import check_environment as check_camera_environment

import G1_INPUT_OBSERVATION_LAUNCH as observation
from g1_portable_environment import select_robot_host

ROOT = Path(__file__).resolve().parents[1]
INTEGRATED_WORKERS = observation.WORKERS + ('lowstate',)
GROOT_LAUNCHER = ROOT / 'tools/G1_GROOT_REMOTE_LAUNCH.py'
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
    return [windows_arguments(row['CommandLine']) for row in rows
            if row.get('CommandLine')]

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


def groot_launcher_running(rows, host):
    """Reuse only the exact integrated GROOT supervisor for this robot host."""
    target = normalized_path(GROOT_LAUNCHER)
    matches = []
    for argv in rows:
        if not argv or Path(argv[0]).name.casefold() not in ('python.exe', 'pythonw.exe'):
            continue
        normalized = [normalized_path(arg) for arg in argv[1:] if not arg.startswith('-')]
        if target not in normalized:
            continue
        if option(argv, '--host') != host or '--confirmed' not in argv:
            raise RuntimeError(
                'An existing GROOT supervisor has different options; preserved.')
        matches.append(argv)
    if len(matches) > 1:
        raise RuntimeError('Duplicate GROOT supervisors found; preserved.')
    return bool(matches)


def confirm_groot_actuation():
    print('[GROOT] Remote motor actuation will be enabled on the G1.', flush=True)
    print('[GROOT] Required remote flags include --supervisor-off and --accept-handoff-risk.',
          flush=True)
    answer = input('Type ACTUATE to start the integrated GROOT heading/controller pair: ').strip()
    if answer != 'ACTUATE':
        raise RuntimeError('GROOT actuation was not confirmed; nothing new was started.')


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


def unity_environment(environment=None):
    """Fill only process-local Windows variables Unity/UPM expects."""
    env = dict(os.environ if environment is None else environment)
    system_drive = env.get('SystemDrive', 'C:').rstrip('\/')
    program_data = Path(system_drive + '\\') / 'ProgramData'
    if not env.get('PROGRAMDATA') and program_data.is_dir():
        env['PROGRAMDATA'] = str(program_data)
    if not env.get('ALLUSERSPROFILE') and env.get('PROGRAMDATA'):
        env['ALLUSERSPROFILE'] = env['PROGRAMDATA']
    local_temp = Path(env.get('LOCALAPPDATA', '')) / 'Temp'
    if not env.get('TEMP') and local_temp.is_dir():
        env['TEMP'] = str(local_temp)
    if not env.get('TMP') and env.get('TEMP'):
        env['TMP'] = env['TEMP']
    return env


def unity_project_version(project=UNITY_PROJECT):
    """Read the editor version declared by the Unity project itself."""
    version_file = project / 'ProjectSettings/ProjectVersion.txt'
    if not version_file.is_file():
        raise RuntimeError('Unity_G1_VR project metadata is missing')
    match = re.search(
        r'^m_EditorVersion:\s*([^\s]+)\s*$',
        version_file.read_text(encoding='utf-8'),
        flags=re.MULTILINE)
    if not match:
        raise RuntimeError('Unity_G1_VR ProjectVersion.txt has no m_EditorVersion')
    version = match.group(1)
    if not re.fullmatch(r'[0-9A-Za-z][0-9A-Za-z._-]{0,63}', version):
        raise RuntimeError('Unity_G1_VR declares an invalid editor version')
    return version


def resolve_unity_editor(environment=None, project=UNITY_PROJECT):
    """Resolve the editor declared by ProjectVersion.txt without launching Unity Hub."""
    environment = unity_environment(environment)
    version = unity_project_version(project)
    candidates = []
    if environment.get('UNITY_EXE'):
        candidates.append(Path(environment['UNITY_EXE']))

    suffix = Path('Unity/Hub/Editor') / version / 'Editor/Unity.exe'
    for key in ('ProgramW6432', 'ProgramFiles'):
        value = environment.get(key)
        if value:
            candidates.append(Path(value) / suffix)

    system_drive = environment.get('SystemDrive', 'C:').rstrip('\/')
    candidates.append(Path(system_drive + '\\') / 'Program Files' / suffix)

    if environment.get('USERPROFILE'):
        candidates.append(Path(environment['USERPROFILE']) / suffix)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError(
        'Unity %s declared by ProjectVersion.txt was not found. '
        'Install it with Unity Hub or set UNITY_EXE.' % version)


def validate_unity_project(project=UNITY_PROJECT):
    return unity_project_version(project)


def start_unity(editor, project=UNITY_PROJECT):
    """Start the editor outside the later quiet-worker job object; never enter Play."""
    subprocess.Popen([str(editor), '-projectPath', str(project.resolve())],
                     cwd=ROOT, env=unity_environment(),
                     creationflags=(subprocess.DETACHED_PROCESS |
                                    subprocess.CREATE_NEW_PROCESS_GROUP))


def running_workers(rows, root, host):
    """Recognize active children, not launch windows waiting after a child exits."""
    paths = {
        'camera_follow': root / 'tools/G1_CAMERA_FOLLOW_LAUNCH.py',
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
                'camera_follow': option(argv, '--host') == host,
                'lowstate': option(argv, '--host') == host,
                'send': 'send-live' in argv and option(argv, '--host') == host
                        and option(argv, '--send-hz') == str(observation.COMPUTE_HZ),
                'omni': '--dry-run' in argv
                        and option(argv, '--process-hz') == str(observation.COMPUTE_HZ)
                        and option(argv, '--unity-alignment-port')
                            == str(observation.UNITY_ALIGNMENT_PORT),
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



def preflight(missing, env):
    ssh_executable()
    for worker, port in (
            ('send', 55071),
            ('arm', 5020),
            ('omni', observation.UNITY_ALIGNMENT_PORT),
            ('camera_follow', 55075)):
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
        check_camera_environment()


def launch_plan(existing, has_camera, has_groot=False,
                no_receiver=False, no_groot_actuation=False):
    plan = [
        worker for worker in INTEGRATED_WORKERS
        if worker != 'receive' and worker not in existing
    ]
    if not has_camera:
        plan.append('camera')
    if not no_groot_actuation and not has_groot:
        plan.append('groot')
    if 'camera_follow' not in existing:
        plan.append('camera_follow')
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='auto', help='auto: wired address first, then closed network')
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--no-receiver', action='store_true',
                        help='Compatibility flag; this launcher never starts a G1 audit receiver.')
    parser.add_argument('--show-consoles', action='store_true', help='Show legacy diagnostic windows')
    parser.add_argument('--no-unity', action='store_true',
                        help='Start/reuse observation workers without opening the Unity editor.')
    parser.add_argument('--no-groot-actuation', action='store_true',
                        help='Keep the integrated launch observation-only; do not start GROOT motor output.')
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
    has_groot = groot_launcher_running(process_rows, args.host)
    plan = launch_plan(
        existing, has_camera, has_groot,
        args.no_receiver, args.no_groot_actuation)
    env = observation.engine_environment()
    preflight(plan, env)
    unity_editor = None
    if not args.no_unity:
        validate_unity_project()
        if not has_unity:
            unity_editor = resolve_unity_editor()
    if args.no_groot_actuation:
        print('G1 VR TELEOP: observation + camera; this invocation will not start GROOT motor output.')
    else:
        print('G1 VR TELEOP: observation + camera + confirmed onboard GROOT actuation.')
    kept = set(existing)
    if has_camera:
        kept.add('camera')
    if has_groot:
        kept.add('groot')
    print('[KEEP] ' + (', '.join(sorted(kept)) or 'none'))
    print('[START] ' + (', '.join(plan) or 'none; existing processes are kept'))
    if args.no_unity:
        print('[UNITY] disabled by --no-unity')
    elif has_unity:
        print('[UNITY] existing Unity_G1_VR editor kept')
    else:
        print('[UNITY] open Unity_G1_VR with Unity ' + unity_project_version())
    print('[QUEST CAMERA] Automatic pan/tilt follower via independent Unity->SSH pose bridge:')
    print('  Unity 127.0.0.1:55075 -> camera_follow SSH stdin -> G1 loopback:15103')
    print('  receive_mink_ik_udp.py --camera-follow --pan-sign 1 --no-camera-stream --port 15104 --quest-port 15103')
    print('  Camera PTZ no longer depends on the GROOT heading controller or UDP 55070 ownership.')
    if args.check_only:
        print('PASS: launch plan checked; no Unity, workers, camera SDK initialization, SSH login, or GROOT actuation. Auto mode probes TCP 22 only.')
        return 0
    if 'groot' in plan:
        confirm_groot_actuation()
    if 'lowstate' in plan or 'camera_follow' in plan:
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
        if worker == 'camera':
            command = [
                sys.executable, '-I', '-u', '-B',
                str(ROOT / 'tools/G1_CAMERA_LAUNCH.py'),
                '--robot-host', args.host,
            ]
        elif worker == 'camera_follow':
            command = [sys.executable, '-I', '-u', '-B',
                       str(ROOT / 'tools/G1_CAMERA_FOLLOW_LAUNCH.py'), '--host', args.host]
        elif worker == 'groot':
            command = [
                sys.executable, '-I', '-u', '-B', str(GROOT_LAUNCHER),
                '--host', args.host, '--confirmed',
            ]
        else:
            command = [
                sys.executable, '-I', '-u', '-B',
                str(ROOT / 'tools/G1_INPUT_OBSERVATION_LAUNCH.py'),
                '--worker', worker, '--host', args.host,
            ]
        subprocess.Popen(
            command, cwd=ROOT, env=env,
            creationflags=subprocess.CREATE_NEW_CONSOLE)
    print('Unity_G1_VR is open. Press Play in Unity, then use Quest and Omni Connect.')
    print('Input compute/send: 60 Hz; observation display: 100 Hz; camera: 30 fps target.')
    print('Close owned worker/GROOT windows to stop them. Unity Play is not changed automatically.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print('G1 VR TELEOP START FAILED: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
