"""Read-only recorded Mink target extraction. No live modules, SDK or transport.

A send_attempt is NOT measured robot motion or proof of acceptance. A complete
idle -> active -> release -> return -> idle episode is a recorded TARGET path.
Selection uses only input integrity/coverage, never a candidate's response.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real
from pathlib import Path
import numpy as np

SCHEMA = 'g1.pd.recorded-target.v1'
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_EPISODE_S = 60.
MIN_ACTIVE_S = 1.
ALLOWED_EVENTS = ('idle', 'active', 'pinch', 'tracking_disengaged', 'return', 'fault')


def strict_json(text):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out: raise ValueError('duplicate_json_key')
            out[k] = v
        return out
    def invalid(_): raise ValueError('nonfinite_json')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


@dataclass(frozen=True)
class Capture:
    source_sha256: str
    first_line: int
    last_line: int
    profile: str
    send_time_s: np.ndarray
    sample_time_s: np.ndarray
    joints: np.ndarray
    sequence: np.ndarray
    events: tuple
    ack_count: int

    def validate(self):
        n = len(self.send_time_s)
        if n < 3 or self.joints.shape != (n, 7): raise ValueError('record_shape')
        if any(len(x) != n for x in (self.sample_time_s, self.sequence, self.events)):
            raise ValueError('record_length')
        if self.profile not in ('today', 'yesterday'): raise ValueError('record_profile')
        if not all(np.isfinite(x).all() for x in (self.send_time_s, self.sample_time_s, self.joints)):
            raise ValueError('record_nonfinite')
        ds, dt = np.diff(self.sample_time_s), np.diff(self.send_time_s)
        if self.sample_time_s[0] != 0 or self.send_time_s[0] != 0: raise ValueError('record_origin')
        if np.any(ds <= 0) or np.any(ds > .06 + 1e-9): raise ValueError('record_sample_gap')
        if np.any(dt < 0) or np.any(dt > .25 + 1e-9): raise ValueError('record_send_gap')
        if np.any(np.diff(self.sequence) != 1): raise ValueError('record_sequence_gap')
        if self.events[0] != 'idle' or self.events[-1] != 'idle': raise ValueError('incomplete_episode')
        middle = self.events[1:-1]
        releases = [i for i, e in enumerate(middle) if e in ('pinch', 'tracking_disengaged')]
        if len(releases) != 1: raise ValueError('release_count')
        split = releases[0]
        if not split or not all(e == 'active' for e in middle[:split]): raise ValueError('active_order')
        if not middle[split+1:] or not all(e == 'return' for e in middle[split+1:]): raise ValueError('return_order')
        active = np.flatnonzero(np.array(self.events) == 'active')
        if self.sample_time_s[active[-1]] - self.sample_time_s[active[0]] < MIN_ACTIVE_S:
            raise ValueError('active_too_short')
        if max(self.sample_time_s[-1], self.send_time_s[-1]) > MAX_EPISODE_S:
            raise ValueError('episode_too_long')
        if not np.allclose(self.joints[0], self.joints[-1], atol=1e-6, rtol=0):
            raise ValueError('target_not_returned')
        if np.max(np.ptp(self.joints, axis=0)) < .02: raise ValueError('no_meaningful_excitation')
        if len(self.source_sha256) != 64 or self.first_line < 1 or self.last_line <= self.first_line:
            raise ValueError('source_identity')

    def times(self, clock):
        if clock == 'send': return self.send_time_s
        if clock == 'sample': return self.sample_time_s
        raise ValueError('unknown_replay_clock')

    def at(self, elapsed, clock='send'):
        if isinstance(elapsed, bool) or not isinstance(elapsed, Real) or not math.isfinite(elapsed) or elapsed < 0: raise ValueError('invalid_replay_time')
        times = self.times(clock)
        # Original order retained; latest recorded target at a repeated logger
        # timestamp. This is a ZOH stress input, NOT replay of the DDS state machine.
        return int(np.searchsorted(times, elapsed, side='right') - 1)

    def metadata(self):
        self.validate()
        return dict(schema=SCHEMA, input_kind='recorded_send_attempt_targets',
            source_sha256=self.source_sha256, first_line=self.first_line, last_line=self.last_line,
            profile=self.profile, samples=len(self.events), ack_records_inside=self.ack_count,
            send_duration_s=float(self.send_time_s[-1]), sample_duration_s=float(self.sample_time_s[-1]),
            equal_send_timestamps=int(np.sum(np.diff(self.send_time_s) == 0)),
            max_send_gap_s=float(np.max(np.diff(self.send_time_s))),
            max_sample_gap_s=float(np.max(np.diff(self.sample_time_s))),
            excursion_deg=np.rad2deg(np.ptp(self.joints, axis=0)).tolist(),
            first_q=self.joints[0].tolist(), last_q=self.joints[-1].tolist(),
            simulation_only=True, measured_robot_response=False, delivery_verified=False)


def extract(path):
    """Return complete episodes plus exclusions. Never import or execute the log."""
    path = Path(path)
    if path.stat().st_size > MAX_FILE_BYTES: raise ValueError('recording_file_too_large')
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    sends, ack_lines = [], []
    for line, text in enumerate(raw.decode('utf-8-sig').splitlines(), 1):
        if not text.strip(): raise ValueError(f'empty_line:{line}')
        r = strict_json(text)
        if not isinstance(r, dict) or r.get('kind') not in ('send_attempt', 'ack') or not finite(r.get('time')) or r['time']<0:
            raise ValueError(f'row_schema:{line}')
        p = r.get('packet')
        if not isinstance(p, dict): raise ValueError(f'packet_schema:{line}')
        if 'relay_token' in p or 'token' in p: raise ValueError('unsanitized_secret_field')
        if r['kind'] == 'ack':
            if p.get('schema') != 'g1.mink.cycle.ack.v1': raise ValueError(f'ack_schema:{line}')
            ack_lines.append(line); continue
        if p.get('schema') != 'g1.mink.cycle.live.v1' or p.get('command_provenance') != 'live_mink' or p.get('simulation_only'):
            raise ValueError(f'not_recorded_live_mink:{line}')
        if p.get('event') not in ALLOWED_EVENTS or p.get('profile') not in ('today', 'yesterday'):
            raise ValueError(f'packet_event_profile:{line}')
        if not isinstance(p.get('session'), str) or not p['session'] or len(p['session'])>128 or p['session'].startswith('replay-'):
            raise ValueError(f'packet_session:{line}')
        for key in ('sequence', 'epoch'):
            if type(p.get(key)) is not int or not 0 <= p[key] < 2**63:
                raise ValueError(f'packet_counter:{line}')
        for key in ('sample_time_s', 'source_age_s', 'clearance_m'):
            if not finite(p.get(key)): raise ValueError(f'packet_number:{line}')
        if not isinstance(p.get('joints'), list) or len(p['joints']) != 7 or not all(finite(v) for v in p['joints']):
            raise ValueError(f'packet_joints:{line}')
        sends.append((line, r['time'], p))
    accepted, excluded = [], []
    start = None
    for i, (line, _, p) in enumerate(sends):
        if p['event'] == 'active' and start is None:
            start = i-1 if i and sends[i-1][2]['event'] == 'idle' else i
        if start is None: continue
        if p['event'] == 'fault' or (p['event'] == 'idle' and i > start):
            chunk = sends[start:i+1]
            why = None
            try:
                first = chunk[0][2]
                if any(q['session'] != first['session'] or q['profile'] != first['profile'] for _, _, q in chunk):
                    raise ValueError('session_or_profile_change')
                if any(not 0 <= q['source_age_s'] <= .25 or q['sample_time_s'] < 0 or q['clearance_m'] < .005-1e-7 for _, _, q in chunk):
                    raise ValueError('recorded_provenance_age_clearance')
                released = False
                for _, _, q in chunk:
                    expected_epoch=first['epoch']+int(released)
                    if q['epoch']!=expected_epoch: raise ValueError('recorded_epoch_transition')
                    if q['event'] in ('pinch','tracking_disengaged'): released=True
                c = Capture(digest, chunk[0][0], line, first['profile'],
                    np.array([t for _, t, _ in chunk])-chunk[0][1],
                    np.array([q['sample_time_s'] for _, _, q in chunk])-first['sample_time_s'],
                    np.array([q['joints'] for _, _, q in chunk]),
                    np.array([q['sequence'] for _, _, q in chunk], dtype=np.int64),
                    tuple(q['event'] for _, _, q in chunk),
                    sum(chunk[0][0] <= n <= line for n in ack_lines))
                c.validate(); accepted.append(c)
            except ValueError as e: why = str(e)
            if why: excluded.append(dict(first_line=chunk[0][0], last_line=line, reason=why))
            start = None
    if start is not None:
        excluded.append(dict(first_line=sends[start][0], last_line=sends[-1][0], reason='episode_no_idle_end'))
    return accepted, dict(file=path.name, source_sha256=digest, bytes=len(raw),
        send_records=len(sends), ack_records=len(ack_lines), complete_episodes=len(accepted), exclusions=excluded)
