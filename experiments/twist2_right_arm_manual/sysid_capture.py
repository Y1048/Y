"""Offline/file-only observation sink. Never imports a transport or controller.

Caller supplies immutable JSON bytes, already copied from observations. Offer is
nonblocking and never raises for bad samples/full queue: loss invalidates capture.
Encoding/copy cost belongs outside the hard real-time path; this Python reference
is not a hard real-time adapter and is deliberately not wired into the robot.
"""
import hashlib
import json
import math
from pathlib import Path
import queue
import threading

SCHEMA = 'g1.sysid.observation.v2'
JOINT_NAMES = tuple(
    [f'{side}_{name}' for side in ('left', 'right') for name in
     ('hip_pitch', 'hip_roll', 'hip_yaw', 'knee', 'ankle_pitch', 'ankle_roll')]
    + ['waist_yaw', 'waist_roll', 'waist_pitch']
    + [f'{side}_{name}' for side in ('left', 'right') for name in
       ('shoulder_pitch', 'shoulder_roll', 'shoulder_yaw', 'elbow',
        'wrist_roll', 'wrist_pitch', 'wrist_yaw')])
UNITS = {'q': 'rad', 'dq': 'rad/s', 'tau': 'Nm', 'kp': 'Nm/rad',
         'kd': 'Nm*s/rad', 'time': 'ns', 'temperature': 'degC',
         'imu_rpy': 'rad', 'imu_gyro': 'rad/s', 'imu_accel': 'm/s^2'}
VECTORS = ('target_q', 'command_q', 'command_dq', 'kp', 'kd', 'tau_ff',
           'measured_q', 'measured_dq')
TIMES = ('target_ns', 'write_begin_ns', 'write_end_ns', 'state_receive_ns')


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()


def decode(raw):
    def pairs(xs):
        d = {}
        for k, v in xs:
            if k in d:
                raise ValueError('duplicate_key')
            d[k] = v
        return d
    def bad(x):
        raise ValueError('nonfinite')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def finite_tree(x):
    if isinstance(x, float) and not math.isfinite(x):
        raise ValueError('nonfinite')
    if isinstance(x, dict):
        for v in x.values(): finite_tree(v)
    if isinstance(x, list):
        for v in x: finite_tree(v)


def vector(x, n):
    if not isinstance(x, list) or len(x) != n or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in x):
        raise ValueError('invalid_vector')


def validate(r):
    required = {'schema', 'session', 'episode', 'sequence', 'state', 'mode',
                'provenance', 'clock', 'joint_indices', 'joint_names', 'units',
                'acceptance', 'dropped_samples', *VECTORS, *TIMES}
    optional = {'torque_estimate', 'imu_rpy', 'imu_gyro', 'imu_accel',
                'temperature', 'motor_status'}
    if not isinstance(r, dict) or set(r) - required - optional or required - set(r):
        raise ValueError('fields')
    finite_tree(r)
    if r['schema'] != SCHEMA or r['joint_indices'] != list(range(29)) or \
            r['joint_names'] != list(JOINT_NAMES) or r['units'] != UNITS:
        raise ValueError('schema_joint_order_units')
    for k in ('session', 'episode', 'state'):
        if not isinstance(r[k], str) or not r[k]: raise ValueError(k)
    if r['mode'] is not None and not isinstance(r['mode'], str): raise ValueError('mode')
    if r['acceptance'] != 'unknown': raise ValueError('unproven_acceptance')
    p = r['provenance']
    if not isinstance(p, dict) or p.get('kind') not in ('generated', 'measured', 'replay') \
            or not isinstance(p.get('source'), str) or not p['source']:
        raise ValueError('provenance')
    c = r['clock']
    if not isinstance(c, dict) or set(c) != {'source', 'domain'} or not all(
            isinstance(v, str) and v for v in c.values()): raise ValueError('clock')
    for k in (*TIMES, 'sequence', 'dropped_samples'):
        if type(r[k]) is not int or r[k] < 0: raise ValueError(k)
    if not r['target_ns'] <= r['write_begin_ns'] <= r['write_end_ns']:
        raise ValueError('write_order')
    for k in VECTORS: vector(r[k], 29)
    for k in ('torque_estimate', 'temperature', 'motor_status'):
        if r.get(k) is not None: vector(r[k], 29)
    for k in ('imu_rpy', 'imu_gyro', 'imu_accel'):
        if r.get(k) is not None: vector(r[k], 3)
    return r


class Capture:
    """Single producer; no waits, file I/O or JSON work in offer().

    Consumer validates/writes exact bytes. Must close outside control thread.
    Missing/incomplete receipt always means unusable, including crash/power loss.
    """
    def __init__(self, path, capacity=4096):
        if type(capacity) is not int or capacity < 1: raise ValueError('capacity')
        self.path = Path(path)
        if self.path.exists() or self.path.with_suffix('.receipt.json').exists():
            raise FileExistsError(self.path)
        self.q = queue.Queue(capacity)
        self.closed = threading.Event()
        self.failed = threading.Event()
        self.offered = self.dropped = self.written = 0
        self.error = None
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def offer(self, raw):
        self.offered += 1
        if type(raw) is not bytes or self.closed.is_set() or self.failed.is_set():
            self.dropped += 1
            return False
        try:
            self.q.put_nowait(raw)
            return True
        except queue.Full:
            self.dropped += 1
            return False

    def _run(self):
        try:
            with self.path.open('xb') as f:
                while not self.closed.is_set() or not self.q.empty():
                    try: raw = self.q.get(timeout=.02)
                    except queue.Empty: continue
                    if b'\n' in raw or b'\r' in raw: raise ValueError('one_line_required')
                    validate(decode(raw))
                    f.write(raw + b'\n')
                    self.written += 1
        except Exception as exc:
            self.error = type(exc).__name__ + ': ' + str(exc)
            self.failed.set()

    def close(self):
        self.closed.set()
        self.worker.join(timeout=5)
        status = {'complete': not self.worker.is_alive() and not self.failed.is_set()
                  and self.dropped == 0 and self.written == self.offered,
                  'offered': self.offered, 'written': self.written,
                  'dropped': self.dropped, 'error': self.error}
        if not self.worker.is_alive() and self.path.exists():
            status['sha256'] = hashlib.sha256(self.path.read_bytes()).hexdigest()
        with self.path.with_suffix('.receipt.json').open('xb') as f: f.write(canonical(status))
        return status


def read_episode(path):
    path = Path(path)
    raw = path.read_bytes()
    receipt = decode(path.with_suffix('.receipt.json').read_bytes())
    if receipt.get('complete') is not True or receipt.get('sha256') != hashlib.sha256(raw).hexdigest():
        raise ValueError('incomplete_or_modified_capture')
    rows = [validate(decode(line)) for line in raw.splitlines()]
    if not rows or len(rows) != receipt.get('written'): raise ValueError('empty_or_missing')
    first = rows[0]
    for i, r in enumerate(rows):
        if r['dropped_samples']: raise ValueError('reported_drop')
        for k in ('session', 'episode', 'clock', 'provenance'):
            if r[k] != first[k]: raise ValueError('mixed_episode_metadata')
        if i:
            a = rows[i-1]
            if r['sequence'] != a['sequence'] + 1: raise ValueError('sequence_gap_or_reverse')
            if any(r[k] < a[k] for k in TIMES) or r['write_begin_ns'] == a['write_begin_ns']:
                raise ValueError('nonmonotonic_timestamp')
            if r['state_receive_ns'] == a['state_receive_ns'] and any(
                    r[k] != a[k] for k in ('measured_q', 'measured_dq')):
                raise ValueError('conflicting_same_state')
    return rows
