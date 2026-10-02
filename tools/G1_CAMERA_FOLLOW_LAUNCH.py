"""Own an SSH-lifetime camera follower; never starts robot motion or a camera stream."""
import argparse
import base64
import json
import math
import re
import select
import shlex
import socket
import subprocess
import time
from g1_ssh_login import identity_options, ssh_executable

UNITY_CAMERA_ADDRESS = ('127.0.0.1', 55075)
DIRECT_SCHEMA = 'g1.unity.quest.camera.v1'


def direct_to_observation(raw):
    if len(raw) > 1024:
        raise ValueError('camera pose packet too large')
    def reject_nonfinite(_):
        raise ValueError('nonfinite camera pose')
    packet = json.loads(raw.decode('utf-8'), parse_constant=reject_nonfinite)
    if not isinstance(packet, dict) or packet.get('schema') != DIRECT_SCHEMA:
        raise ValueError('camera pose schema')
    session = packet.get('session')
    if (not isinstance(session, str) or len(session) != 32
            or any(c not in '0123456789abcdef' for c in session)):
        raise ValueError('camera pose session')
    sequence = packet.get('sequence')
    if type(sequence) is not int or not 0 <= sequence < 2**53:
        raise ValueError('camera pose sequence')
    if packet.get('ready') is not True:
        return None
    yaw, pitch = packet.get('yaw_deg'), packet.get('pitch_deg')
    if (type(yaw) not in (int, float) or not math.isfinite(yaw)
            or type(pitch) not in (int, float) or not math.isfinite(pitch)
            or not -180.0 <= float(yaw) <= 180.0
            or not -90.0 <= float(pitch) <= 90.0):
        raise ValueError('camera pose angles')
    envelope = dict(
        schema='g1.observation.audit.v1', observation_only=True,
        session=session, sequence=sequence,
        payload=dict(omni=dict(
            status='FRESH_LIVE', source_age_s=0.0, source_receive_age_s=0.0,
            values=dict(
                calibrated=True, unity_alignment_status='READY',
                unity_alignment_age_s=0.0, unity_alignment_session=session,
                unity_quest_yaw_deg=float(yaw),
                unity_quest_pitch_deg=float(pitch)))))
    return json.dumps(envelope, allow_nan=False, separators=(',', ':')).encode('utf-8')


REMOTE = r"""
import fcntl, os, select, signal, socket, subprocess, sys, time
from pathlib import Path
root=Path('/home/unitree/groot_onboard_runtime')
script=root/'receive_mink_ik_udp.py'
expected=['--camera-follow','--pan-sign','1','--no-camera-stream','--port','15104','--quest-port','15103']
if not script.is_file():raise RuntimeError('Missing camera follower on G1')
# Serialize inspect/start across multiple Windows launchers.
lock=open('/tmp/g1_quest_camera_follow.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX)
owned=None
quest_bridge=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
input_buffer=bytearray()
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
            i=indices[0];tail=args[i+1:]
            if '--camera-follow' not in tail:
                continue  # Independent Mink receiver; dedicated PTZ ports do not conflict.
            actual=Path(args[i])
            if not actual.is_absolute():actual=Path(os.readlink(proc/'cwd'))/actual
            if actual.resolve()!=script.resolve() or tail!=expected:
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
        if readable:
            chunk=os.read(sys.stdin.fileno(),4096)
            if not chunk:break
            input_buffer.extend(chunk)
            if len(input_buffer)>8192 and b'\n' not in input_buffer:
                raise RuntimeError('Quest camera bridge input overflow')
            while b'\n' in input_buffer:
                raw,_,remaining=input_buffer.partition(b'\n')
                input_buffer=bytearray(remaining)
                if not raw:continue
                if len(raw)>6000:raise RuntimeError('Quest camera bridge packet too large')
                quest_bridge.sendto(raw,('127.0.0.1',15103))
finally:
    # Only our own camera child; never signal reused/manual processes.
    if owned is not None and owned.poll() is None:
        owned.send_signal(signal.SIGINT)
        try:owned.wait(timeout=4.)
        except subprocess.TimeoutExpired:
            owned.terminate()
            try:owned.wait(timeout=3.)
            except subprocess.TimeoutExpired:owned.kill();owned.wait()
    quest_bridge.close()
    lock.close()
"""


def ssh_command(host):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}',host):
        raise ValueError('Invalid host')
    encoded=base64.b64encode(REMOTE.encode()).decode()
    command='python3 -u -c '+shlex.quote('import base64;exec(base64.b64decode('+repr(encoded)+'))')
    return [ssh_executable(),*identity_options(),'-T','-o','BatchMode=yes','-o','ConnectTimeout=5',
            '-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2','unitree@'+host,command]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    args=parser.parse_args(argv)
    pose=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
        pose.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
    try:
        pose.bind(UNITY_CAMERA_ADDRESS)
    except OSError as error:
        pose.close()
        raise RuntimeError('Quest camera pose UDP 55075 is already owned; preserve the existing follower') from error
    pose.setblocking(False)
    child=subprocess.Popen(ssh_command(args.host),stdin=subprocess.PIPE)
    received=forwarded=waiting=rejected=0
    next_status=time.monotonic()
    try:
        while child.poll() is None:
            readable,_,_=select.select([pose],[],[],.2)
            if readable:
                for _ in range(128):
                    try:raw,peer=pose.recvfrom(2049)
                    except BlockingIOError:break
                    if peer[0]!='127.0.0.1':
                        rejected+=1;continue
                    received+=1
                    try:out=direct_to_observation(raw)
                    except (ValueError,TypeError,UnicodeError,json.JSONDecodeError):
                        rejected+=1;continue
                    if out is None:
                        waiting+=1;continue
                    try:
                        child.stdin.write(out+b'\n');child.stdin.flush()
                    except (BrokenPipeError,OSError):
                        break
                    forwarded+=1
            now=time.monotonic()
            if now>=next_status:
                print('[QUEST CAMERA BRIDGE] rx={} forwarded={} waiting={} rejected={}'.format(
                    received,forwarded,waiting,rejected),flush=True)
                next_status=now+1.
    except KeyboardInterrupt:pass
    finally:
        pose.close()
        try:child.stdin.close()
        except (BrokenPipeError,OSError):pass
        try:child.wait(timeout=12.)
        except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=5.)
    return child.returncode

if __name__=='__main__':raise SystemExit(main())
