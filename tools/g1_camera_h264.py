"""Camera-only H264/SSH receiver; PC converts to the existing Unity JPEG protocol.

No SDK, motor commands, control ports, or PTZ changes. Only complete decoded
images may be superseded. Encoded H264 chunks are never dropped independently.
"""
import json
import math
import socket
import struct
import subprocess
import threading
import time
from fractions import Fraction
from pathlib import Path

from g1_ssh_login import ensure_login, identity_options, ssh_executable

HEADER = struct.Struct('!4sIIQI')
MAX_CHUNK = 65536
MAX_JPEG = 4 * 1024 * 1024
MAX_LOCAL_FRAME_AGE = .25

# stdin supplies this program, not a file copied to G1. A stalled capture or
# closed SSH pipe ends capture. The previous format/FPS is restored on exit.
REMOTE = r'''
import os, re, select, signal, struct, subprocess, sys, time
from pathlib import Path
HEADER=struct.Struct('!4sIIQI')
wire=os.fdopen(os.dup(1),'wb',0)
os.dup2(2,1)
devices={str(p.resolve()):str(p) for p in Path('/dev/v4l/by-id').glob('*Insta360*video-index0') if p.exists()}
if len(devices)!=1: raise RuntimeError('Expected one Insta360 capture device')
device=next(iter(devices.values()))
busy=subprocess.run(['fuser',device],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
if busy.returncode==0: raise RuntimeError('Camera is already owned; existing capture preserved')
if busy.returncode!=1: raise RuntimeError('Cannot verify camera ownership')
def ctl(*args):
 return subprocess.check_output(['v4l2-ctl','-d',device,*args],stderr=subprocess.STDOUT,text=True,timeout=5)
old=ctl('--get-fmt-video','--get-parm')
size=re.search(r'Width/Height\s*:\s*(\d+)/(\d+)',old)
fmt=re.search(r"Pixel Format\s*:\s*'([^']+)'",old)
fps=re.search(r'Frames per second\s*:\s*([0-9.]+)',old)
if not all((size,fmt,fps)): raise RuntimeError('Cannot preserve camera format')
restore='--set-fmt-video=width=%s,height=%s,pixelformat=%s'%(size[1],size[2],fmt[1])
def interrupted(*args): raise KeyboardInterrupt()
signal.signal(signal.SIGTERM,interrupted)
signal.signal(signal.SIGHUP,interrupted)
child=None
try:
 caps=ctl('--list-formats-ext')
 if "'H264'" not in caps: raise RuntimeError('Camera H264 unsupported; use --camera-codec mjpeg')
 ctl('--set-fmt-video=width=1920,height=1080,pixelformat=H264','--set-parm=30')
 actual=ctl('--get-fmt-video','--get-parm')
 if not (re.search(r'Width/Height\s*:\s*1920/1080',actual) and
         re.search(r"Pixel Format\s*:\s*'H264'",actual) and
         re.search(r'Frames per second\s*:\s*30\.0',actual)):
  raise RuntimeError('Camera did not accept H264 1920x1080 30fps')
 print('[H264 CAPTURE] 1920x1080 30fps; camera compressed, no G1 re-encoding',file=sys.stderr,flush=True)
 child=subprocess.Popen(['v4l2-ctl','--silent','-d',device,'--stream-mmap=4','--stream-to=/dev/stdout'],stdout=subprocess.PIPE,bufsize=0)
 started=time.monotonic();sequence=0
 while CAPTURE_SECONDS==0 or time.monotonic()-started<CAPTURE_SECONDS:
  if not select.select([child.stdout],[],[],5)[0]: raise RuntimeError('Camera capture timeout')
  data=os.read(child.stdout.fileno(),65536)
  if not data: raise RuntimeError('Camera capture ended: %s'%child.poll())
  # Timestamp is compressed-chunk read time, NOT sensor exposure time.
  packet=memoryview(HEADER.pack(b'G1H4',1,sequence,time.time_ns(),len(data))+data)
  while packet:
   n=wire.write(packet)
   if not n: raise BrokenPipeError('SSH output closed')
   packet=packet[n:]
  sequence=(sequence+1)&0xffffffff
finally:
 if child is not None and child.poll() is None:
  child.terminate()
  try: child.wait(timeout=2)
  except subprocess.TimeoutExpired: child.kill();child.wait()
 if child is not None: child.stdout.close()
 ctl(restore,'--set-parm='+fps[1])
 print('[H264 CAPTURE STOPPED] original format/FPS restored',file=sys.stderr,flush=True)
'''


def check_decoder():
    import av
    av.CodecContext.create('h264', 'r')
    av.CodecContext.create('mjpeg', 'w')


def remote_source(seconds=0):
    if not math.isfinite(seconds) or not 0 <= seconds <= 300:
        raise ValueError('probe seconds must be finite and between 0 and 300')
    return 'CAPTURE_SECONDS=' + repr(float(seconds)) + '\n' + REMOTE


def read_exact(stream, count, allow_eof=False):
    data = bytearray()
    while len(data) < count:
        chunk = stream.read(count-len(data))
        if not chunk:
            if allow_eof and not data:
                return None
            raise RuntimeError('Truncated H264 transport packet')
        data.extend(chunk)
    return bytes(data)


def read_chunk(stream):
    header = read_exact(stream, HEADER.size, allow_eof=True)
    if header is None:
        return None
    magic, version, seq, stamp, size = HEADER.unpack(header)
    if magic != b'G1H4' or version != 1 or not 1 <= size <= MAX_CHUNK:
        raise RuntimeError('Invalid H264 chunk header')
    return seq, stamp, read_exact(stream, size)


class Decoder:
    def __init__(self):
        import av
        self.decoder = av.CodecContext.create('h264', 'r')
        self.decoder.thread_count = 2
        self.decoder.thread_type = 'SLICE'  # no additional frame-thread queue
        self.encoder = av.CodecContext.create('mjpeg', 'w')
        self.encoder.width, self.encoder.height = 1920, 1080
        self.encoder.pix_fmt = 'yuvj420p'
        self.encoder.time_base = Fraction(1, 30)
        self.encoder.qmin = self.encoder.qmax = 3
        self.encoder.thread_count = 2
        self.sequence = 0

    def feed(self, raw):
        for packet in self.decoder.parse(raw):
            for frame in self.decoder.decode(packet):
                if (frame.width, frame.height) != (1920, 1080):
                    raise RuntimeError('Unexpected camera resolution')
                frame = frame.reformat(format='yuvj420p')
                frame.pts = self.sequence
                frame.time_base = Fraction(1, 30)
                for encoded in self.encoder.encode(frame):
                    jpeg = bytes(encoded)
                    if not (4 <= len(jpeg) <= MAX_JPEG and
                            jpeg.startswith(b'\xff\xd8') and jpeg.endswith(b'\xff\xd9')):
                        raise RuntimeError('Invalid converted JPEG')
                    yield self.sequence, jpeg
                self.sequence += 1


class LatestFrame:
    """One image slot; blocked/disconnected Unity must not stall SSH decoding."""
    def __init__(self):
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.item = None
        self.overwritten = 0

    def put(self, item):
        with self.lock:
            if self.item is not None:
                self.overwritten += 1
            self.item = item
            self.ready.set()

    def take(self, now):
        with self.lock:
            item, self.item = self.item, None
            self.ready.clear()
        if item is None or now-item[0] > MAX_LOCAL_FRAME_AGE:
            return None
        return item


def receive(stream, latest, done, metrics, log_path):
    previous = None
    started = time.monotonic()
    try:
        decoder = Decoder()
        with log_path.open('w', encoding='utf-8') as log:
            while True:
                chunk = read_chunk(stream)
                if chunk is None:
                    break
                sequence, stamp, raw = chunk
                if sequence != (0 if previous is None else (previous+1) & 0xffffffff):
                    raise RuntimeError('H264 chunk sequence gap; cannot skip encoded chunks')
                previous = sequence
                metrics['wire_bytes'] += HEADER.size + len(raw)
                received = time.monotonic()
                before = time.perf_counter()
                for frame_seq, jpeg in decoder.feed(raw):
                    now = time.monotonic()
                    packet = HEADER.pack(b'G1CM', 1, frame_seq & 0xffffffff, stamp, len(jpeg))+jpeg
                    latest.put((now, packet))
                    metrics['frames'] += 1
                    metrics['last_frame_monotonic_s'] = now
                    if metrics['first_frame_monotonic_s'] is None:
                        metrics['first_frame_monotonic_s'] = now
                    log.write(json.dumps(dict(sequence=frame_seq,pc_received_monotonic_s=received,
                        pc_decoded_monotonic_s=now,remote_chunk_read_unix_ns=stamp,
                        local_jpeg_bytes=len(jpeg)))+'\n')
                metrics['decode_encode_s'] += time.perf_counter()-before
    except Exception as error:
        metrics['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        metrics['elapsed_s'] = time.monotonic()-started
        done.set()


def run(host, probe_seconds=0, output_address=('127.0.0.1', 5011), stop_event=None):
    if output_address[0] != '127.0.0.1' or not 1 <= output_address[1] <= 65535:
        raise ValueError('Camera preview output must be loopback')
    check_decoder()
    source = remote_source(probe_seconds)
    ensure_login(host)
    folder = Path(__file__).resolve().parents[1]/'logs/test_results/camera_h264'
    folder.mkdir(parents=True, exist_ok=True)
    stem = time.strftime('%Y%m%d_%H%M%S')
    path = folder/(stem+'_summary.json')
    metrics = dict(codec='h264',resolution=[1920,1080],target_fps=30,wire_bytes=0,
        frames=0,sent_to_unity=0,decode_encode_s=0.,first_frame_monotonic_s=None,
        last_frame_monotonic_s=None,error=None,probe_seconds=probe_seconds,
        timestamp_semantics='remote compressed chunk read time; not exposure or end-to-end latency')
    command = [ssh_executable(), *identity_options(), '-T', '-o','BatchMode=yes',
        '-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no','-o','ConnectTimeout=5',
        '-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2','unitree@'+host,'python3 -u -']
    latest = LatestFrame()
    done = threading.Event()
    connection = None
    next_connect = next_status = 0.
    error_log = (folder/(stem+'_remote.log')).open('wb')
    child = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=error_log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    thread = None
    started = time.monotonic()
    try:
        child.stdin.write(source.encode()); child.stdin.close()
        thread = threading.Thread(target=receive,args=(child.stdout,latest,done,metrics,
            folder/(stem+'_frames.jsonl')),daemon=True)
        thread.start()
        print('[CAMERA H264] 1920x1080@30 -> SSH -> PC decode -> local JPEG TCP%d'%output_address[1],flush=True)
        print('[CAMERA H264] '+('bounded camera-only probe; no Unity connection' if probe_seconds else
            'latest decoded image only; no G1 re-encoding'),flush=True)
        while not done.is_set() and not (stop_event and stop_event.is_set()):
            latest.ready.wait(.05)
            now = time.monotonic()
            last = metrics['last_frame_monotonic_s'] or started
            if now-last > 10:
                raise RuntimeError('No decoded H264 image for 10 seconds')
            if probe_seconds and now-started > probe_seconds+12:
                raise RuntimeError('Bounded H264 probe timed out')
            item = latest.take(now)
            if item is not None and not probe_seconds:
                if connection is None and now >= next_connect:
                    next_connect = now+1
                    try:
                        connection = socket.create_connection(output_address,timeout=.2)
                        connection.settimeout(.2)
                        connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
                    except OSError:
                        connection = None
                if connection is not None:
                    try:
                        # A connect attempt can consume the entire freshness lease.
                        if time.monotonic()-item[0] <= MAX_LOCAL_FRAME_AGE:
                            connection.sendall(item[1]);metrics['sent_to_unity'] += 1
                    except OSError:
                        connection.close();connection=None
            if now >= next_status:
                print('[H264] decoded=%d unity=%d wire_MB=%.2f latest_overwritten=%d'%(
                    metrics['frames'],metrics['sent_to_unity'],metrics['wire_bytes']/1e6,latest.overwritten),flush=True)
                next_status = now+2
        if stop_event and stop_event.is_set():
            metrics['stop_reason'] = 'preview_stop'
            return
        child.wait(timeout=5)
        if metrics['error']:
            raise RuntimeError(metrics['error'])
        if child.returncode or not probe_seconds:
            raise RuntimeError('H264 SSH stream ended (exit %s); see %s'%(child.returncode,error_log.name))
        if metrics['frames'] == 0:
            raise RuntimeError('H264 probe produced no decoded frames')
    except KeyboardInterrupt:
        metrics['stop_reason'] = 'operator_interrupt'
    except Exception as error:
        metrics['error'] = str(error)
        raise
    finally:
        if connection is not None:connection.close()
        if child.poll() is None:child.terminate()
        try:child.wait(timeout=8)
        except subprocess.TimeoutExpired:child.kill();child.wait()
        if thread is not None:thread.join(timeout=3)
        error_log.close()
        metrics['ssh_exit_code'] = child.returncode
        metrics['latest_overwritten'] = latest.overwritten
        if metrics['frames']>1:
            span=metrics['last_frame_monotonic_s']-metrics['first_frame_monotonic_s']
            metrics['decoded_fps']=(metrics['frames']-1)/span
        metrics['payload_mbps_over_receiver_lifetime']=metrics['wire_bytes']*8/max(.001,metrics.get('elapsed_s',time.monotonic()-started))/1e6
        path.write_text(json.dumps(metrics,indent=2)+'\n',encoding='utf-8')
        print('[CAMERA H264 SUMMARY] '+str(path),flush=True)
