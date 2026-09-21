"""Open four observation consoles; no controller or motor command is launched."""
import argparse
import ctypes
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
from g1_portable_environment import select_robot_host

ROOT = Path(__file__).resolve().parents[1]
REMOTE_DIR = '/home/unitree/g1_input_audit_20260921_7e83c4'
WORKERS = ('receive', 'send', 'omni', 'arm')
COMPUTE_HZ = 60
DISPLAY_HZ = 100


def worker_command(worker, host, stamp):
    python = [sys.executable, '-u', '-B']
    if worker == 'receive':
        return ['ssh.exe', '-t', 'unitree@'+host,
                'cd '+REMOTE_DIR+' && python3 -u G1_INPUT_RECEIVE_AUDIT.py receive --print-hz '+str(DISPLAY_HZ)]
    if worker == 'send':
        return python + [str(ROOT/'tools/G1_INPUT_RECEIVE_AUDIT.py'),
                         'send-live', '--host', host, '--send-hz', str(COMPUTE_HZ),
                         '--print-hz', str(DISPLAY_HZ)]
    if worker == 'omni':
        return python + [str(ROOT/'hardware/g1_arm_bridge/g1_omni_velocity_gateway.py'),
                         '--dry-run', '--process-hz', str(COMPUTE_HZ), '--csv',
                         str(ROOT/'logs/test_results/omni_gateway_readonly'/('omni_observation_'+stamp+'.csv'))]
    if worker == 'arm':
        return python + [str(ROOT/'MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py'),
                         '--mode', 'unity', '--compute-hz', str(COMPUTE_HZ), '--output',
                         str(ROOT/'logs/test_results/bimanual'/('unity_'+stamp+'.jsonl'))]
    raise ValueError('worker')


def engine_environment():
    env = os.environ.copy()
    # Only children started by this launcher receive the opt-in observation tap.
    env['G1_OBSERVATION_TAP'] = '1'
    if not env.get('G1_BIMANUAL_ENGINE_ROOT'):
        candidates = [ROOT/'.venv-teleop/Lib/site-packages',
                      ROOT/'logs/diagnostics/mujoco_versions/3.12.0']
        for candidate in candidates:
            if (candidate/'mujoco/__init__.py').is_file():
                env['G1_BIMANUAL_ENGINE_ROOT'] = str(candidate)
                break
    return env


def preflight(env):
    if not shutil.which('ssh.exe'):
        raise RuntimeError('ssh.exe is missing')
    for port in (5020, 55071):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                sock.bind(('127.0.0.1', port))
            except OSError as error:
                raise RuntimeError('UDP %d is occupied. Close the old simulation/observation console you started; '
                                   'no process was stopped automatically.' % port) from error
    subprocess.run([sys.executable, '-B', '-c', 'import websocket'], check=True, env=env)
    subprocess.run([sys.executable, '-B', str(ROOT/'tools/g1_portable_environment.py')], check=True, env=env, cwd=str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='auto', help='auto: wired address first, then closed network')
    parser.add_argument('--worker', choices=WORKERS)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--no-receiver', action='store_true',
                        help='Start PC sources/sender only; keep your existing G1 receive console.')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', args.host):
        parser.error('host must be a hostname or IPv4 address')
    args.host = select_robot_host(args.host)
    env = engine_environment()
    if args.worker:
        if os.name == 'nt':
            ctypes.windll.kernel32.SetConsoleTitleW('G1 OBSERVATION - '+args.worker+' - NO MOTOR OUTPUT')
        print('OBSERVATION ONLY. Closing this window does not operate G1 motors.', flush=True)
        print('IK / Omni processing / observation send: %d Hz; PC / G1 display: %d Hz.' %
              (COMPUTE_HZ, DISPLAY_HZ), flush=True)
        print('ARM order: left 15..21, right 22..28; angles rad. Omni vx/vy m/s, yaw_rate rad/s.', flush=True)
        result = 0
        try:
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            result = subprocess.run(worker_command(args.worker, args.host, stamp),
                                    cwd=str(ROOT), env=env).returncode
        except KeyboardInterrupt:
            pass
        finally:
            if sys.stdin.isatty():
                try:
                    input('Observation process ended. Press Enter to close. ')
                except (KeyboardInterrupt, EOFError):
                    pass
        return result
    preflight(env)
    if args.check_only:
        print('PASS: dependencies and local ports checked; no workers or SSH started.')
        return 0
    if os.name != 'nt':
        raise RuntimeError('Visible-console launcher is for Windows; use the individual Python commands elsewhere.')
    for worker in WORKERS:
        if args.no_receiver and worker == 'receive':
            continue
        subprocess.Popen([sys.executable, '-u', '-B', str(Path(__file__).resolve()),
                          '--worker', worker, '--host', args.host], cwd=str(ROOT), env=env,
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
    print(('Three PC' if args.no_receiver else 'Four')+
          ' observation windows opened. Use Unity Play / Quest and Omni Connect; log in in receive if opened.')
    print('FRESH_LIVE + ACK_CONFIRMED proves observation receipt, not motor acceptance.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print('OBSERVATION START FAILED: '+str(error), file=sys.stderr)
        raise SystemExit(1)
