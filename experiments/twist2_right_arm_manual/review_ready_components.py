"""Offline decomposition of recorded readiness; never authorizes actuation."""
import argparse
import csv
import json
import math
from pathlib import Path


def Review(rows):
    names = ('current_all29', 'body_attitude_velocity_proxy',
             'waist_left_tracking', 'right_arm_tracking', 'split_proxy_and_right')
    stats = {name: dict(passing_samples=0, longest_sampled_run_s=0.0) for name in names}
    starts = {name: None for name in names}
    failures = [0] * 29
    samples = 0
    for previous, row in zip(rows, rows[1:]):
        now, before = float(row['elapsed_s']), float(previous['elapsed_s'])
        errors = [abs(float(row[f'q_{i}']) - float(previous[f'desired_target_{i}']))
                  for i in range(29)]
        speeds = [abs(float(row[f'dq_{i}'])) for i in range(29)]
        roll, pitch = float(row['roll_rad']), float(row['pitch_rad'])
        age, alpha = float(row['state_age_ms']), float(row['alpha'])
        finite = all(math.isfinite(x) for x in [now, before, roll, pitch, age, alpha] + errors + speeds)
        valid = finite and 0 < now-before <= .05 and 0 <= age <= 20 and alpha == 1
        tracking = [e <= .025 and v <= .1 for e, v in zip(errors, speeds)]
        body = abs(roll) <= .15 and abs(pitch) <= .15 and all(v <= .1 for v in speeds[:12])
        checks = dict(current_all29=all(tracking), body_attitude_velocity_proxy=body,
                      waist_left_tracking=all(tracking[12:22]),
                      right_arm_tracking=all(tracking[22:29]),
                      split_proxy_and_right=body and all(tracking[12:29]))
        if valid:
            samples += 1
            for i, error in enumerate(errors):
                failures[i] += error > .025
        for name in names:
            if not valid or not checks[name]:
                starts[name] = None
                continue
            stats[name]['passing_samples'] += 1
            if starts[name] is None:
                starts[name] = now
            stats[name]['longest_sampled_run_s'] = max(
                stats[name]['longest_sampled_run_s'], now-starts[name])
    return dict(status='offline_diagnostic_only', valid_post_blend_samples=samples,
                components=stats, position_failure_counts=failures,
                physical_ready=False, first_vr_alignment_verified=False,
                limitations=['50 Hz samples cannot prove continuous state between rows',
                             'Body proxy is not a validated balance criterion',
                             'No contact load, support force, R1, CRC or motor health proof',
                             'Previous policy target used, not same-row or writer target',
                             '50 ms gap limit is an analysis continuity rule, not a controller setting'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with args.csv.open(newline='') as stream:
        result = Review(list(csv.DictReader(stream)))
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))
