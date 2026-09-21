"""Explicit first-run setup. Installs local dependencies; never starts teleop."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from g1_portable_environment import ROOT, camera_run, configure_mirrored_network


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--pc-only', action='store_true', help='Prepare IK/Omni without WSL camera')
    args = parser.parse_args()
    if os.name != 'nt' or sys.version_info[:2] != (3, 11):
        raise RuntimeError('Use Windows x64 Python 3.11: py -3.11')
    venv = ROOT / '.venv-teleop'
    python = venv / 'Scripts/python.exe'
    if not args.check_only:
        if not python.is_file():
            subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check',
                        '-r', str(ROOT / 'tools/requirements-teleop.txt')], check=True)
    if not python.is_file():
        raise RuntimeError('Run tools/SETUP_G1_VR_TELEOP.bat once to create the local environment')
    subprocess.run([str(python), '-m', 'pip', 'check'], check=True)
    env = os.environ.copy()
    env['G1_BIMANUAL_ENGINE_ROOT'] = str(venv / 'Lib/site-packages')
    subprocess.run([str(python), '-B', str(ROOT / 'tools/g1_portable_environment.py')],
                   env=env, cwd=ROOT, check=True)
    if not args.pc_only:
        if not args.check_only:
            if sys.getwindowsversion().build < 22621:
                raise RuntimeError('Camera mirrored networking requires Windows 11 22H2 or newer')
            if configure_mirrored_network(Path.home() / '.wslconfig'):
                print('WSL mirrored setting saved with backup. Close WSL jobs, then run wsl --shutdown', flush=True)
                print('before camera use. Setup will NOT interrupt running WSL jobs.', flush=True)
        camera_run('--check-only' if args.check_only else '--setup', '192.168.123.164')
    print('DEPENDENCIES READY. Open Unity_G1_VR with its recorded Unity version, enable Play,')
    print('and connect Meta Link / Omni Connect. Setup has NOT tested camera images or robot receipt.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print('SETUP FAILED: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
