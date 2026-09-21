"""Read camera on G1 eth0 and forward framed JPEG over SSH to Unity loopback."""
import os
from pathlib import Path
import socket
import shutil
import struct
import subprocess
import sys
import time
from g1_ssh_login import ensure_login, identity_options

HEADER = struct.Struct('!4sIIQI')
MAX_JPEG = 4 * 1024 * 1024
REMOTE = r"""
import os, sys, struct, time
wire = os.fdopen(os.dup(1), 'wb', 0)
os.dup2(2, 1)  # SDK diagnostics must never contaminate binary stdout.
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.go2.video.video_client import VideoClient
ChannelFactoryInitialize(0, 'eth0')
c = VideoClient(); c.SetTimeout(3.0); c.Init()
sequence = 0
frame_period_s = 0.5  # 2 fps: prioritize joint/velocity transport over video.
while True:
    start = time.monotonic()
    code, data = c.GetImageSample()
    if code or not data:
        print('Camera read error', code, file=sys.stderr, flush=True)
        time.sleep(.1)
        continue
    data = bytes(data)
    if not 4 <= len(data) <= 4*1024*1024 or not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
        continue
    packet = memoryview(struct.pack('!4sIIQI', b'G1CM', 1, sequence, int(time.time()*1e9), len(data)) + data)
    while packet:
        written = wire.write(packet)
        if not written: raise RuntimeError('SSH pipe closed')
        packet = packet[written:]
    sequence = (sequence+1) & 0xffffffff
    time.sleep(max(0, frame_period_s-(time.monotonic()-start)))
"""


def read_exact(stream, size):
    chunks = bytearray()
    while len(chunks) < size:
        part = stream.read(size-len(chunks))
        if not part:
            raise RuntimeError('SSH camera stream ended; inspect camera/SSH error above')
        chunks.extend(part)
    return bytes(chunks)


def read_packet(stream):
    raw = read_exact(stream, HEADER.size)
    magic, version, sequence, stamp, size = HEADER.unpack(raw)
    if magic != b'G1CM' or version != 1 or not 4 <= size <= MAX_JPEG:
        raise RuntimeError('Invalid camera frame header')
    jpeg = read_exact(stream, size)
    if not jpeg.startswith(b'\xff\xd8') or not jpeg.endswith(b'\xff\xd9'):
        raise RuntimeError('Invalid JPEG frame')
    return raw + jpeg


def check_environment():
    if not shutil.which('ssh.exe'):
        raise RuntimeError('Windows OpenSSH client (ssh.exe) is required')
    print('[CAMERA CHECK] SSH transport ready locally; WSL is not required. G1 images not tested.', flush=True)


def run(host):
    ensure_login(host)
    command = ['ssh.exe'] + identity_options() + ['-T', '-o', 'BatchMode=yes',
        '-o', 'ConnectTimeout=5', '-o', 'ServerAliveInterval=5',
        '-o', 'ServerAliveCountMax=2', 'unitree@'+host, 'python3 -u -']
    logdir = Path(__file__).resolve().parents[1]/'logs/test_results/camera_ssh'
    logdir.mkdir(parents=True, exist_ok=True)
    log = (logdir/(time.strftime('%Y%m%d_%H%M%S')+'_'+str(os.getpid())+'.log')).open('a', encoding='utf-8')
    def status(message):
        print(message, flush=True); log.write(message+'\n'); log.flush()
    status('[CAMERA SSH] '+host+' eth0 -> SSH -> Unity 127.0.0.1:5011; camera only; low bandwidth 2 fps')
    child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    connection = None
    frames = 0
    last_status = 0
    next_connect = 0
    try:
        child.stdin.write(REMOTE.encode('utf-8')); child.stdin.close()
        while True:
            packet = read_packet(child.stdout)
            if connection is None:
                if time.monotonic() < next_connect:
                    continue  # Drain and discard while Unity is unavailable.
                next_connect = time.monotonic() + 1
                try:
                    connection = socket.create_connection(('127.0.0.1',5011),timeout=.2)
                    connection.settimeout(.2)
                    connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
                except OSError:
                    status('[WAIT] Unity TCP5011 unavailable; enter Play');continue
            try:
                connection.sendall(packet);frames+=1
            except OSError:
                connection.close();connection=None;continue
            if time.monotonic()-last_status >= 1:
                status('[STREAMING] frames='+str(frames)+' latest_bytes='+str(len(packet)-HEADER.size))
                last_status=time.monotonic()
    except KeyboardInterrupt:
        pass
    finally:
        if connection is not None:connection.close()
        if child.poll() is None:child.terminate()
        child.wait(timeout=10)
        status('[STOPPED] frames='+str(frames));log.close()
