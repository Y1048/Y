"""Read Insta360 Link 2 Pro MJPEG on G1 and forward framed JPEG over SSH."""
import os
from pathlib import Path
import socket
import struct
import subprocess
import time
from g1_ssh_login import ensure_login, identity_options, ssh_executable

HEADER = struct.Struct('!4sIIQI')
MAX_JPEG = 4 * 1024 * 1024
REMOTE = r"""
import os, struct, subprocess, sys, time
from pathlib import Path
HEADER = struct.Struct('!4sIIQI')
MAX_JPEG = 4 * 1024 * 1024
BY_ID = Path('/dev/v4l/by-id')
wire = os.fdopen(os.dup(1), 'wb', 0)
os.dup2(2, 1)

def which(name):
    for folder in os.environ.get('PATH', '').split(os.pathsep):
        path = Path(folder) / name
        if path.is_file() and os.access(str(path), os.X_OK):
            return str(path)
    return None

def find_camera():
    candidates = sorted(BY_ID.glob('usb-Insta360_Insta360_Link_2_Pro-video-index0'))
    if not candidates:
        candidates = sorted(BY_ID.glob('*Insta360*video-index0'))
    for candidate in candidates:
        try:
            target = candidate.resolve(strict=True)
        except (FileNotFoundError, OSError):
            continue
        if target.name.startswith('video'):
            return str(candidate), str(target)
    return None, None
def start_capture(device):
    if not which('v4l2-ctl'):
        raise RuntimeError('v4l2-ctl is required on G1')
    return subprocess.Popen([
        'v4l2-ctl', '--silent', '-d', device,
        '--set-fmt-video=width=1920,height=1080,pixelformat=MJPG',
        '--set-parm=30', '--stream-mmap=4',
        '--stream-to=/dev/stdout',
    ], stdout=subprocess.PIPE, stdin=subprocess.DEVNULL, bufsize=0)

def jpeg_frames(stream):
    buffer = bytearray()
    while True:
        chunk = stream.read(65536)
        if not chunk:
            return
        buffer.extend(chunk)
        while True:
            start = buffer.find(b'\xff\xd8')
            if start < 0:
                if len(buffer) > 1:
                    del buffer[:-1]
                break
            if start:
                del buffer[:start]
            end = buffer.find(b'\xff\xd9', 2)
            if end < 0:
                if len(buffer) > MAX_JPEG:
                    raise RuntimeError('Insta360 MJPEG frame exceeds maximum size')
                break
            end += 2
            jpeg = bytes(buffer[:end])
            del buffer[:end]
            if 4 <= len(jpeg) <= MAX_JPEG:
                yield jpeg

sequence = 0
last_wait_log = 0.0
while True:
    device, resolved = find_camera()
    if device is None:
        now = time.monotonic()
        if now - last_wait_log >= 1.0:
            print('[CAMERA WAIT] Insta360 Link 2 Pro video-index0 not found',
                  file=sys.stderr, flush=True)
            last_wait_log = now
        time.sleep(1.0)
        continue
    print('[CAMERA] Insta360 Link 2 Pro %s -> %s; 1920x1080 MJPEG 30 fps'
          % (device, resolved), file=sys.stderr, flush=True)
    child = start_capture(device)
    frames = 0
    try:
        for data in jpeg_frames(child.stdout):
            packet = memoryview(HEADER.pack(
                b'G1CM', 1, sequence, time.time_ns(), len(data)) + data)
            while packet:
                written = wire.write(packet)
                if not written:
                    raise RuntimeError('SSH pipe closed')
                packet = packet[written:]
            sequence = (sequence + 1) & 0xffffffff
            frames += 1
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        if child.stdout is not None:
            child.stdout.close()
    print('[CAMERA LOST] stream ended after %d frames; rediscovering' % frames,
          file=sys.stderr, flush=True)
    time.sleep(1.0)
"""

def read_exact(stream, size):
    chunks = bytearray()
    while len(chunks) < size:
        part = stream.read(size - len(chunks))
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
    client = ssh_executable()
    print('[CAMERA CHECK] SSH ready (' + client + '); Insta360/v4l2 checked on G1 at runtime.',
          flush=True)

def run(host):
    ensure_login(host)
    command = [ssh_executable()] + identity_options() + [
        '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
        '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
        'unitree@' + host, 'python3 -u -']
    logdir = Path(__file__).resolve().parents[1] / 'logs/test_results/camera_ssh'
    logdir.mkdir(parents=True, exist_ok=True)
    log = (logdir / (time.strftime('%Y%m%d_%H%M%S') + '_' + str(os.getpid()) + '.log')).open(
        'a', encoding='utf-8')
    def status(message):
        print(message, flush=True)
        log.write(message + '\n')
        log.flush()
    status('[CAMERA SSH] %s Insta360 Link 2 Pro MJPEG 1920x1080@30 -> SSH -> Unity 127.0.0.1:5011' % host)
    child = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    connection = None
    frames = 0
    last_status = 0.0
    next_connect = 0.0
    try:
        child.stdin.write(REMOTE.encode('utf-8'))
        child.stdin.close()
        while True:
            packet = read_packet(child.stdout)
            if connection is None:
                if time.monotonic() < next_connect:
                    continue
                next_connect = time.monotonic() + 1.0
                try:
                    connection = socket.create_connection(('127.0.0.1', 5011), timeout=.2)
                    connection.settimeout(.2)
                    connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except OSError:
                    status('[WAIT] Unity TCP5011 unavailable; enter Play')
                    continue
            try:
                connection.sendall(packet)
                frames += 1
            except OSError:
                connection.close()
                connection = None
                continue
            if time.monotonic() - last_status >= 1.0:
                status('[STREAMING] frames=%d latest_bytes=%d' % (
                    frames, len(packet) - HEADER.size))
                last_status = time.monotonic()
    except KeyboardInterrupt:
        pass
    finally:
        if connection is not None:
            connection.close()
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=10)
        status('[STOPPED] frames=' + str(frames))
        log.close()
