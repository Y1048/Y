"""Per-PC OpenSSH enrollment; passwords stay in the SSH terminal, never Python/logs."""
from pathlib import Path
import shlex
import subprocess


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
    return subprocess.run(['ssh.exe'] + identity_options() +
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
        subprocess.run(['ssh-keygen.exe', '-q', '-t', 'ed25519', '-f', str(key),
                        '-N', '', '-C', 'g1-teleop'], check=True, stdin=subprocess.DEVNULL)
    if probe(host):
        print('[SSH] Key login verified; no password required.', flush=True)
        return
    print('[SSH] First setup on this PC/address: enter the G1 password once. '
          'It is not saved. A new host key is remembered; changed host keys are rejected.', flush=True)
    command = registration_command(public.read_text(encoding='ascii'))
    # Inherit the real terminal so OpenSSH handles its own password prompt.
    subprocess.run(['ssh.exe', '-o', 'StrictHostKeyChecking=accept-new',
        '-o', 'ConnectTimeout=5', '-o', 'PubkeyAuthentication=no',
        '-o', 'NumberOfPasswordPrompts=1', 'unitree@' + host, command], check=True)
    if not probe(host):
        raise RuntimeError('Public key registration finished but key login could not be verified')
    print('[SSH] This PC is enrolled. Future launches use key login.', flush=True)
