"""Replay Windows receiver logs through the memory-only C++ queue harness."""
import argparse
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
EXE = ROOT / 'logs/test_results/test_queued_input.exe'


def Replay(path, executable=EXE):
    text = Path(path).read_text(encoding='utf-8')
    if not text.endswith('\n'):
        raise ValueError('incomplete log line')
    rows = [json.loads(line) for line in text.splitlines()]
    if not rows or rows[0].get('log_schema') != 'g1.twist2.receive_replay.v1':
        raise ValueError('raw replay schema required; older logs cannot be reconstructed')
    if rows[-1].get('event') != 'final':
        raise ValueError('complete final event required')
    config = rows[0]['config']
    initial = config.get('baseline')
    commands = [dict(baseline=initial, maximum_delta=config['maximum_delta_rad'],
                     capacity=config['queue_capacity'])]
    count = 0
    clock = 0
    active = 0
    depth = 0
    for row in rows[1:]:
        kind = row['event']
        now = row['received_at_s'] if kind == 'packet' else row['now_s']
        if not math.isfinite(now) or now < clock:
            raise ValueError('non-monotonic event clock')
        clock = now
        if kind == 'packet':
            count += 1
            raw = bytes.fromhex(row['payload_hex'])
            if row['packet'] != count or row['size_bytes'] != len(raw) or raw.hex() != row['payload_hex']:
                raise ValueError('packet sequence or raw encoding mismatch')
            if row['expired']:
                if now < rows[0]['duration_s']:
                    raise ValueError('premature duration stop')
                commands.append(dict(op='stop', reason='duration_limit'))
            else:
                commands.append(dict(op='push', payload_hex=row['payload_hex'], at=now))
            depth = depth + 1 if row['enqueued'] else 0
        elif kind == 'tick':
            if row['batch_size'] != depth:
                raise ValueError('batch size mismatch')
            commands.append(dict(op='tick', at=now))
            depth = 0
            active += row['mode'] == 'active'
        elif kind == 'final' and row is rows[-1]:
            # External transport failures cannot be reproduced from payloads.
            # Only duration is accepted as an externally injected stop.
            if row['reason'] == 'duration_limit' and now < rows[0]['duration_s']:
                raise ValueError('premature duration stop')
            commands.append(dict(op='stop', reason=row['reason']))
        else:
            raise ValueError('unexpected event')
        if kind != 'packet' and (row['packets'] != count or row['active_ticks'] != active):
            raise ValueError('event counters mismatch')
    result = subprocess.run([str(executable)], input=''.join(json.dumps(x)+'\n' for x in commands),
                            text=True, capture_output=True, check=True)
    actual = [json.loads(line) for line in result.stdout.splitlines()]
    if len(actual) != len(rows)-1:
        raise ValueError('replay result count')
    previous = initial
    baseline = initial
    tick_time = 0
    previous_reason = ''
    max_step = 0
    for row, got in zip(rows[1:], actual):
        kind = row['event']
        if kind == 'packet':
            if (got['mode'] == 'queued') != row['enqueued'] or got['reason'] != row['reason']:
                raise ValueError('enqueue replay mismatch')
        else:
            if kind == 'final' and not previous_reason and row['reason'] != 'duration_limit':
                raise ValueError('unreproducible external stop')
            for key in ('q', 'baseline', 'mode', 'reason', 'validated_goal'):
                if got[key] != row[key]:
                    raise ValueError(f'{key} replay mismatch')
            if got['peak'] != row['queue_peak']:
                raise ValueError('queue peak mismatch')
            q = row['q']
            if baseline is None and row['baseline'] is not None:
                baseline = row['baseline']
                previous = baseline
            if baseline != row['baseline']:
                raise ValueError('baseline changed')
            if q is not None:
                if len(q) != 29 or not all(math.isfinite(v) for v in q) or q[:22] != baseline[:22]:
                    raise ValueError('non-target or finite invariant')
                if row['mode'] == 'active':
                    goal = row['validated_goal']
                    bound = .08 * min(row['now_s']-tick_time, .02) + 1e-12
                    for old, new, target in zip(previous[22:], q[22:], goal):
                        max_step = max(max_step, abs(new-old))
                        if abs(new-old) > bound or not min(old,target)-1e-12 <= new <= max(old,target)+1e-12:
                            raise ValueError('rate or overshoot invariant')
                elif q != previous:
                    raise ValueError('inactive candidate changed')
                previous = q
            if kind == 'tick':
                tick_time = row['now_s']
        previous_reason = got['reason']
    return dict(passed=True, packets=count, active_ticks=active, reason=rows[-1]['reason'],
                maximum_step_rad=max_step, exact_candidate_replay=True, overshoot_checked=True,
                hardware_output_authorized=False, robot_safety_validated=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    args = parser.parse_args()
    print(json.dumps(Replay(args.log), indent=2))
