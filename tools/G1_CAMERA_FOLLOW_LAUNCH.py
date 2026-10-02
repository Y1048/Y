"""Own an SSH-lifetime camera follower; never starts robot motion or a camera stream."""
import argparse
import base64
import re
import shlex
import subprocess
import time
from g1_ssh_login import identity_options

REMOTE = r"""
import fcntl, os, select, signal, subprocess, sys, time
from pathlib import Path
root=Path('/home/unitree/groot_onboard_runtime')
script=root/'receive_mink_ik_udp.py'
expected=['--camera-follow','--pan-sign','1','--no-camera-stream']
if not script.is_file():raise RuntimeError('Missing camera follower on G1')
# Serialize inspect/start across multiple Windows launchers.
lock=open('/tmp/g1_quest_camera_follow.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX)
owned=None
# SSH hangup/termination also runs ownership-scoped cleanup.
def stop(signum, frame):
    raise SystemExit(0)
signal.signal(signal.SIGHUP,stop)
signal.signal(signal.SIGTERM,stop)
try:
    rows=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            args=proc.joinpath('cmdline').read_bytes().decode().strip('\0').split('\0')
            if any(Path(a).name=='link2_keyboard.py' for a in args):
                raise RuntimeError('Manual keyboard PTZ is active; preserved')
            indices=[i for i,a in enumerate(args) if Path(a).name==script.name]
            if not indices:continue
            i=indices[0];actual=Path(args[i])
            if not actual.is_absolute():actual=Path(os.readlink(proc/'cwd'))/actual
            if actual.resolve()!=script.resolve() or args[i+1:]!=expected:
                raise RuntimeError('Existing camera receiver has different options; preserved')
            rows.append(int(proc.name))
        except (FileNotFoundError,PermissionError,ProcessLookupError):pass
    if len(rows)>1:raise RuntimeError('Multiple camera followers; preserved')
    if rows:
        pid=rows[0]
        print('[KEEP] Existing camera follower pid='+str(pid),flush=True)
    else:
        owned=subprocess.Popen(['python3','-B','-u',str(script)]+expected,
                               cwd=str(root),stdin=subprocess.DEVNULL)
        pid=owned.pid
        print('[START] Camera pan/tilt follower pid='+str(pid),flush=True)
    fcntl.flock(lock,fcntl.LOCK_UN)
    while True:
        if owned is not None and owned.poll() is not None:
            raise RuntimeError('Camera follower exited: '+str(owned.returncode))
        if owned is None and not Path('/proc',str(pid)).exists():
            raise RuntimeError('Reused camera follower ended')
        readable,_,_=select.select([sys.stdin],[],[],1.)
        if readable and not os.read(sys.stdin.fileno(),1024):break
finally:
    # Only our own camera child; never signal reused/manual processes.
    if owned is not None and owned.poll() is None:
        owned.send_signal(signal.SIGINT)
        try:owned.wait(timeout=4.)
        except subprocess.TimeoutExpired:
            owned.terminate()
            try:owned.wait(timeout=3.)
            except subprocess.TimeoutExpired:owned.kill();owned.wait()
    lock.close()
"""


def ssh_command(host):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}',host):
        raise ValueError('Invalid host')
    encoded=base64.b64encode(REMOTE.encode()).decode()
    command='python3 -u -c '+shlex.quote('import base64;exec(base64.b64decode('+repr(encoded)+'))')
    return ['ssh.exe',*identity_options(),'-T','-o','BatchMode=yes','-o','ConnectTimeout=5',
            '-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2','unitree@'+host,command]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    args=parser.parse_args(argv)
    child=subprocess.Popen(ssh_command(args.host),stdin=subprocess.PIPE)
    try:
        while child.poll() is None:
            try:child.stdin.write(b'.');child.stdin.flush()
            except (BrokenPipeError,OSError):break
            time.sleep(1.)
    except KeyboardInterrupt:pass
    finally:
        try:child.stdin.close()
        except (BrokenPipeError,OSError):pass
        try:child.wait(timeout=12.)
        except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=5.)
    return child.returncode

if __name__=='__main__':raise SystemExit(main())
