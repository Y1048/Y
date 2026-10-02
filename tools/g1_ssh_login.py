"""Per-PC OpenSSH enrollment; passwords stay in the SSH terminal, never Python/logs."""
from pathlib import Path
import os
import shlex
import shutil
import subprocess


def _ssh_healthy(path):
    try:
        result = subprocess.run(
            [str(path), '-V'], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', timeout=5,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and 'OpenSSH_' in (result.stdout or '')


def _ssh_candidates(environment):
    candidates = []
    seen = set()
    def add(path):
        if not path:
            return
        path = Path(path).expanduser()
        key = str(path).casefold()
        if key not in seen:
            seen.add(key)
            candidates.append(path)
    windows = environment.get('WINDIR') or environment.get('SystemRoot')
    if windows:
        add(Path(windows) / 'System32/OpenSSH/ssh.exe')
    for key in ('ProgramW6432', 'ProgramFiles', 'ProgramFiles(x86)'):
        root = environment.get(key)
        if root:
            add(Path(root) / 'Git/usr/bin/ssh.exe')
            add(Path(root) / 'Git/bin/ssh.exe')
    local = environment.get('LOCALAPPDATA')
    if local:
        add(Path(local) / 'Programs/Git/usr/bin/ssh.exe')
    for folder in environment.get('PATH', '').split(os.pathsep):
        if folder:
            add(Path(folder.strip('"')) / 'ssh.exe')
    return candidates


def ssh_executable(environment=None):
    environment = os.environ if environment is None else environment
    override = environment.get('SSH_EXE')
    if override:
        candidate = Path(override).expanduser()
        if not _ssh_healthy(candidate):
            raise RuntimeError('SSH_EXE is not a working OpenSSH client: ' + str(candidate))
        return str(candidate)
    for candidate in _ssh_candidates(environment):
        if candidate.is_file() and _ssh_healthy(candidate):
            return str(candidate)
    raise RuntimeError(
        'No working OpenSSH client found. Checked Windows OpenSSH and Git for Windows; '
        'install one or set SSH_EXE explicitly.')


def ssh_keygen_executable(environment=None):
    ssh = Path(ssh_executable(environment))
    sibling = ssh.with_name('ssh-keygen.exe' if os.name == 'nt' else 'ssh-keygen')
    if sibling.is_file():
        return str(sibling)
    fallback = shutil.which('ssh-keygen.exe' if os.name == 'nt' else 'ssh-keygen')
    if fallback:
        return fallback
    raise RuntimeError('ssh-keygen was not found beside the selected OpenSSH client')


def key_path():
    return Path.home() / '.ssh' / 'id_ed25519_g1_teleop'


def identity_options():
    return ['-i', str(key_path()), '-o', 'IdentitiesOnly=yes']


def registration_command(public_key):
    parts = public_key.strip().split()
    if len(parts) < 2 or parts[0] != 'ssh-ed25519' or '\n' in public_key.strip():
        raise RuntimeError('Invalid G1 public key')
    key = shlex.quote(' '.join(parts[:2]))
    return ("umask 077; mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
            "touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && "
            "(grep -qxF -- " + key + " ~/.ssh/authorized_keys || "
            "printf '%s\n' " + key + " >> ~/.ssh/authorized_keys)")


def probe(host):
    return subprocess.run([ssh_executable()] + identity_options() +
        ['-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
         '-o', 'ConnectTimeout=5', 'unitree@' + host, 'true'],
        stdin=subprocess.DEVNULL, capture_output=True, timeout=15).returncode == 0


def ensure_login(host):
    key = key_path()
    public = Path(str(key) + '.pub')
    if key.exists() != public.exists():
        raise RuntimeError('Incomplete G1 SSH key pair; preserve it and repair manually: ' + str(key))
    if not key.exists():
        key.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([ssh_keygen_executable(), '-q', '-t', 'ed25519', '-f', str(key),
                        '-N', '', '-C', 'g1-teleop'], check=True, stdin=subprocess.DEVNULL)
    if probe(host):
        print('[SSH] Key login verified; no password required.', flush=True)
        return
    print('[SSH] First setup on this PC/address: enter the G1 password once. '
          'It is not saved. A new host key is remembered; changed host keys are rejected.', flush=True)
    command = registration_command(public.read_text(encoding='ascii'))
    # Inherit the real terminal so OpenSSH handles its own password prompt.
    subprocess.run([ssh_executable(), '-o', 'StrictHostKeyChecking=accept-new',
        '-o', 'ConnectTimeout=5', '-o', 'PubkeyAuthentication=no',
        '-o', 'NumberOfPasswordPrompts=1', 'unitree@' + host, command], check=True)
    if not probe(host):
        raise RuntimeError('Public key registration finished but key login could not be verified')
    print('[SSH] This PC is enrolled. Future launches use key login.', flush=True)


def remote_receiver_running(host, remote_dir):
    """Reuse only the identified audit receiver; unknown UDP owners block launch."""
    import json
    code = r"""
import subprocess, re, json, os
rows=subprocess.check_output(['ss','-H','-lunp','sport = :55070']).decode()
if not rows.strip():
    print(json.dumps([]))
else:
    pids=set(re.findall(r'pid=(\d+)',rows))
    if not pids: raise RuntimeError('UDP55070 owner is not inspectable')
    result=[]
    for pid in pids:
        args=open('/proc/'+pid+'/cmdline','rb').read().decode().strip('\0').split('\0')
        result.append({'args':args,'cwd':os.readlink('/proc/'+pid+'/cwd')})
    print(json.dumps(result))
"""
    result = subprocess.run([ssh_executable()]+identity_options()+['-T','-o','BatchMode=yes',
        '-o','ConnectTimeout=5','unitree@'+host,'python3 -'],
        input=code, capture_output=True, text=True, check=True, timeout=15)
    rows=json.loads(result.stdout)
    if not rows:return False
    if len(rows)!=1:raise RuntimeError('Multiple remote UDP55070 owners; preserved')
    row=rows[0];args=row['args']
    scripts=[i for i,arg in enumerate(args) if Path(arg).name=='G1_INPUT_RECEIVE_AUDIT.py']
    if (row['cwd']!=remote_dir or len(scripts)!=1
            or args[scripts[0]+1:]!=['receive','--print-hz','100']):
        raise RuntimeError('UDP55070 belongs to another process/configuration; preserved')
    print('[KEEP] Verified existing G1 observation receiver; no duplicate SSH receiver started.')
    return True
