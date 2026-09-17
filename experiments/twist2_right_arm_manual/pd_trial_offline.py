"""Offline trajectory design and existing CSV baseline review. No robot transport."""
import argparse
import csv
import json
import math
from pathlib import Path


def duration(distance, speed, acceleration):
    if not all(math.isfinite(x) and x > 0 for x in (distance, speed, acceleration)):
        raise ValueError('distance, speed and acceleration must be finite and positive')
    # Exact extrema of the minimum-jerk quintic position polynomial.
    return max(1.875 * distance / speed,
               math.sqrt((10 / math.sqrt(3)) * distance / acceleration))


def segment(t, distance, seconds):
    s = min(1.0, max(0.0, t / seconds))
    return (distance * (10*s**3 - 15*s**4 + 6*s**5),
            distance / seconds * 30*s*s*(1-s)**2,
            distance / seconds**2 * 60*s*(1-s)*(1-2*s))


def generate(output, amplitude_deg=10.0, speed_deg_s=45.0,
             acceleration=0.32, hold=1.0, cycles=3, hz=500):
    if not math.isfinite(hold) or hold <= 0 or cycles < 1 or hz < 1:
        raise ValueError('positive hold, cycles and hz required')
    distance = math.radians(amplitude_deg)
    speed = math.radians(speed_deg_s)
    move = duration(distance, speed, acceleration)
    period = 2 * (move + hold)
    total = cycles * period
    output = Path(output)
    with output.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['elapsed_s', 'cycle', 'phase', 'offset_rad', 'dq_rad_s', 'ddq_rad_s2'])
        for n in range(math.ceil(total * hz) + 1):
            t = min(n / hz, total)
            cycle = min(int(t / period), cycles - 1)
            local = t - cycle * period
            if local < move:
                phase = 'outbound'
                q, dq, ddq = segment(local, distance, move)
            elif local < move + hold:
                phase, q, dq, ddq = 'hold_far', distance, 0, 0
            elif local < 2 * move + hold:
                phase = 'return'
                x, v, a = segment(local - move - hold, distance, move)
                q, dq, ddq = distance-x, -v, -a
            else:
                phase, q, dq, ddq = 'hold_start', 0, 0, 0
            writer.writerow([t, cycle, phase, q, dq, ddq])
    return {'offline_only': True, 'relative_offset_only': True,
            'move_seconds': move, 'total_seconds': total,
            'peak_speed_deg_s': math.degrees(1.875*distance/move),
            'peak_acceleration_rad_s2': 10/math.sqrt(3)*distance/move**2,
            'robot_joint_limits_and_collision_checked': False}


def review(path, phase, reference='desired', writer_trial_phase=None):
    if writer_trial_phase is not None and (reference != 'writer' or writer_trial_phase not in range(1, 6)):
        raise ValueError('writer trial phase 1..5 requires writer reference')
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('empty CSV')
    last = -math.inf
    errors = {i: [] for i in range(22, 29)}
    writer_sequence = 0
    writer_time = -math.inf
    for row in rows:
        t = float(row['elapsed_s'])
        if not math.isfinite(t) or t < 0 or t <= last:
            raise ValueError('invalid timestamp order')
        last = t
        if writer_trial_phase is None and row['phase'] != phase:
            continue
        if reference == 'writer':
            if row['writer_valid'] != '1':
                continue
            sequence = int(row['writer_sequence'])
            if sequence < writer_sequence or sequence <= 0:
                raise ValueError('invalid writer sequence')
            if sequence == writer_sequence:
                continue  # 50-Hz sampler may observe the same writer frame.
            received, started, returned = (float(row[k]) for k in
                ('writer_state_received_s', 'writer_cycle_started_s', 'writer_write_returned_s'))
            if (not all(math.isfinite(x) for x in (received, started, returned))
                    or received < 0 or started < 0 or received > returned
                    or started > returned or returned <= writer_time):
                raise ValueError('invalid writer timing')
            writer_sequence, writer_time = sequence, returned
            gains = [float(row[f'writer_kp_{i}']) for i in errors]
            if not all(math.isfinite(x) and x >= 0 for x in gains):
                raise ValueError('invalid writer gains')
            if any(x == 0 for x in gains):
                continue  # Damping targets are not position tracking goals.
            if writer_trial_phase is not None and int(row['writer_trial_phase']) != writer_trial_phase:
                continue
        for i in errors:
            q_key = f'writer_q_{i}' if reference == 'writer' else f'q_{i}'
            target_key = f'writer_target_{i}' if reference == 'writer' else f'desired_target_{i}'
            q, target = float(row[q_key]), float(row[target_key])
            if not all(math.isfinite(x) for x in (q, target)):
                raise ValueError('non-finite joint data')
            errors[i].append(q-target)
    if not errors[22]:
        raise ValueError('no samples for selected phase')
    return {'phase': phase if writer_trial_phase is None else None,
            'writer_trial_phase': writer_trial_phase, 'samples': len(errors[22]),
            'error_reference': ('publisher-call target vs state used by that writer cycle'
                if reference == 'writer' else 'pre-writer desired_target, NOT final transmitted target'),
            'limitation': '50-Hz samples; phase belongs to policy row, not writer frame; no device acknowledgement; not a PD optimum score',
            'joints': {str(i): {'rms_rad': math.sqrt(sum(e*e for e in es)/len(es)),
                               'max_abs_rad': max(map(abs, es))} for i, es in errors.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    gen = commands.add_parser('generate')
    gen.add_argument('--output', type=Path, required=True)
    gen.add_argument('--amplitude-deg', type=float, default=10)
    gen.add_argument('--speed-deg-s', type=float, default=45)
    gen.add_argument('--acceleration', type=float, default=.32)
    rev = commands.add_parser('review')
    rev.add_argument('csv', type=Path)
    rev.add_argument('--phase', default='udp_ready')
    rev.add_argument('--reference', choices=('desired', 'writer'), default='desired')
    rev.add_argument('--writer-trial-phase', type=int, choices=range(1, 6))
    args = parser.parse_args()
    result = (generate(args.output, args.amplitude_deg, args.speed_deg_s, args.acceleration)
              if args.command == 'generate' else review(args.csv, args.phase, args.reference, args.writer_trial_phase))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
