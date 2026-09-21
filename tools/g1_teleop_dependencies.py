"""Validate/repair this checkout's Python dependencies before any teleop startup."""
import argparse
import importlib
from importlib import metadata
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = {'websocket-client': 'websocket', 'absl-py': 'absl', 'pyopengl': 'OpenGL'}


def requirements(path):
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        name, separator, version = line.partition('==')
        if not separator or not name or not version:
            raise RuntimeError('Expected exact dependency pin: ' + line)
        result[name] = version
    if not result:
        raise RuntimeError('Dependency list is empty')
    return result


def probe():
    errors = []
    if sys.version_info[:2] != (3, 11) or struct.calcsize('P') != 8:
        errors.append('Python 3.11 x64 required')
    if Path(sys.prefix).resolve() != (ROOT / '.venv-teleop').resolve():
        errors.append('Wrong interpreter prefix: ' + sys.prefix)
    for name, expected in requirements(ROOT / 'tools/requirements-teleop.txt').items():
        try:
            actual = metadata.version(name)
            if actual != expected:
                errors.append(name + ': expected ' + expected + ', found ' + actual)
            importlib.import_module(MODULES.get(name, name.replace('-', '_')))
        except Exception as error:
            errors.append(name + ': ' + type(error).__name__ + ': ' + str(error))
    print(json.dumps(dict(python=sys.executable, errors=errors)), flush=True)
    return not errors


def validate(python):
    if not python.is_file():
        return False
    command = [str(python), '-I', '-B', str(ROOT / 'tools/g1_teleop_dependencies.py'), '--probe']
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=120)
        if result.returncode:
            print(result.stdout or result.stderr, flush=True)
            return False
        return subprocess.run([str(python), '-I', '-m', 'pip', 'check'],
                              capture_output=True, timeout=120).returncode == 0
    except (OSError, subprocess.TimeoutExpired) as error:
        print('[DEPENDENCIES] ' + str(error), flush=True)
        return False


def ensure(repair):
    python = ROOT / '.venv-teleop/Scripts/python.exe'
    if validate(python):
        print('[DEPENDENCIES] All pinned packages/imports and pip check passed.', flush=True)
        return
    if not repair:
        raise RuntimeError('Incomplete environment. Run tools/START_G1_VR_TELEOP.bat to repair.')
    if sys.version_info[:2] != (3, 11) or struct.calcsize('P') != 8:
        raise RuntimeError('Install Python 3.11 x64; existing environment was preserved.')
    # Serialize repairs with a non-blocking OS lock, released even on interruption.
    import msvcrt
    lock_path = ROOT / 'logs/setup/dependencies.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as lock:
        lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError('Dependency repair already running. Wait and launch again.') from error
        if not python.is_file():
            subprocess.run([sys.executable, '-m', 'venv', str(python.parent.parent)], check=True)
        print('[DEPENDENCIES] Installing project requirements; no teleop workers started.', flush=True)
        subprocess.run([str(python), '-I', '-m', 'ensurepip', '--upgrade'], check=True)
        subprocess.run([str(python), '-I', '-m', 'pip', 'install', '--disable-pip-version-check',
                        '-r', str(ROOT / 'tools/requirements-teleop.txt')], check=True)
        if not validate(python):
            raise RuntimeError('Dependency repair incomplete. No teleop workers started; retry with network available.')
    print('[DEPENDENCIES] Repair verified.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if args.probe:
        return 0 if probe() else 1
    ensure(repair=not args.check_only)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print('[DEPENDENCIES FAILED] ' + str(error), file=sys.stderr)
        raise SystemExit(1)
