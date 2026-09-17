"""One-second sampled upper-body motion metrics; no ready decision or robot I/O."""
import argparse
import csv
import json
import math
from collections import deque
from pathlib import Path


def Windows(rows):
    window = deque()
    previous_time = None
    result = []
    for row in rows:
        t = float(row['elapsed_s'])
        q = [float(row[f'q_{i}']) for i in range(12,29)]
        dq = [float(row[f'dq_{i}']) for i in range(12,29)]
        target = [float(row[f'desired_target_{i}']) for i in range(12,29)]
        attitude = [float(row['roll_rad']), float(row['pitch_rad'])]
        age, alpha = float(row['state_age_ms']), float(row['alpha'])
        finite = all(math.isfinite(x) for x in [t,age,alpha]+q+dq+target+attitude)
        continuous = previous_time is None or 0 < t-previous_time <= .05
        previous_time = t if math.isfinite(t) else None
        if not finite or not continuous or not 0 <= age <= 20 or alpha != 1:
            window.clear()
            continue
        window.append((t,q,dq,target,attitude))
        # Keep the last sample at/before t-1; actual span may exceed 1 s by one interval.
        while len(window)>1 and window[1][0] <= t-1:
            window.popleft()
        if t-window[0][0] < 1:
            continue
        excursions = [max(r[1][i] for r in window)-min(r[1][i] for r in window) for i in range(17)]
        command_excursions = [max(r[3][i] for r in window)-min(r[3][i] for r in window) for i in range(17)]
        # Same-row target error is descriptive, not replay of adapter's previous-target gate.
        offsets = [max(abs(r[3][i]-r[1][i]) for r in window) for i in range(17)]
        result.append(dict(end_s=t,span_s=t-window[0][0],sample_count=len(window),
            maximum_upper_excursion_rad=max(excursions),
            maximum_command_excursion_rad=max(command_excursions),
            maximum_upper_speed_rad_s=max(abs(v) for r in window for v in r[2]),
            maximum_attitude_excursion_rad=max(max(r[4][i] for r in window)-min(r[4][i] for r in window) for i in range(2)),
            maximum_target_offset_rad=max(offsets),
            upper_excursions_rad=excursions,upper_target_offsets_rad=offsets))
    return result


def Review(rows):
    windows = Windows(rows)
    keys = ('maximum_upper_excursion_rad','maximum_command_excursion_rad',
            'maximum_upper_speed_rad_s','maximum_attitude_excursion_rad','maximum_target_offset_rad')
    return dict(status='offline_motion_observation',physical_ready=False,
        complete_windows=len(windows),
        metric_ranges={k:dict(min=min(w[k] for w in windows),max=max(w[k] for w in windows)) for k in keys} if windows else {},
        windows=windows,
        limitations=['No physical stability threshold is set',
                     'Samples cannot establish continuous stability or load support',
                     'Target offsets are same-row descriptive values',
                     'No torque margin, R1, contact, motor health or input alignment decision'])


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with args.csv.open(newline='') as stream: result=Review(list(csv.DictReader(stream)))
    with args.output.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='windows'}))
