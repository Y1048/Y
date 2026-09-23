"""Replay recorded Unity input offline, with no sockets or robot commands."""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
from g1_bimanual_unity_sim import BimanualSimulation, UnityCycle, decode


def yaw(q):
    w, x, y, z = q
    return np.degrees(np.arctan2(2*(w*y+x*z), 1-2*(y*y+x*x)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    records = [json.loads(line) for line in args.source.open(encoding='utf-8')]
    sim = BimanualSimulation()
    cycle = UnityCycle(sim)
    latest = None
    output = []
    for row in records:
        if row['kind'] == 'input' and row['accepted']:
            latest = json.loads(row['raw_json_text'])
            latest['base_yaw_rad'] = -np.radians(latest['omni_aligned_yaw_deg'])
            for side in ('left', 'right'):
                latest[side]['quaternion_wxyz'] = latest[side]['raw_quaternion_wxyz']
            cycle.receive(decode(json.dumps(latest)), row['receive_monotonic_s'])
        elif row['kind'] == 'state':
            cycle.tick(row['monotonic_s'])
            fb = cycle.feedback()
            result = dict(time_s=row['monotonic_s'], sequence=cycle.sequence,
                          state=cycle.state, reason=cycle.reason,
                          solver_error=sim.last_solver_error,
                          unity_yaw_deg=yaw(latest['unity_robot_root_wxyz']) if latest else 0,
                          ik_yaw_deg=yaw(fb['mujoco_base_world_wxyz']))
            for side in ('left', 'right'):
                result[side+'_error_m'] = fb.get(side+'_ik_position_error_m')
                result[side+'_recorded_error_m'] = row.get(side+'_ik_position_error_m')
                if latest and latest[side]['tracked']:
                    result[side+'_input_display_gap_m'] = float(np.linalg.norm(
                        np.array(latest[side]['position_m'])-latest[side]['raw_position_m']))
                    if fb.get(side+'_ik_target_world_wxyz') is not None:
                        qa = np.array(fb[side+'_actual_wrist_world_wxyz'])
                        qt = np.array(fb[side+'_ik_target_world_wxyz'])
                        result[side+'_orientation_error_deg'] = float(np.degrees(
                            2*np.arccos(np.clip(abs(np.dot(qa, qt)), 0, 1))))
            output.append(result)
            if len(output) % 600 == 0:
                print('replayed ticks', len(output), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for r in output for k in r))
    with args.output.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(output)
    summary = dict(robot_commands=False, ticks=len(output),
                   blocked_ticks=sum(r['state']=='blocked' for r in output),
                   solver_errors=sum(r['solver_error'] is not None for r in output),
                   max_base_yaw_error_deg=max(abs((r['unity_yaw_deg']-r['ik_yaw_deg']+180)%360-180) for r in output))
    for side in ('left', 'right'):
        angles = [r[side+'_orientation_error_deg'] for r in output
                  if side+'_orientation_error_deg' in r]
        summary[side+'_orientation_error_deg_p50_p95_max'] = np.percentile(angles,[50,95,100]).tolist()
        for key in ('error_m', 'recorded_error_m'):
            vals = [r[side+'_'+key] for r in output if r.get(side+'_'+key) is not None]
            summary[side+'_'+key+'_p50_p95_max'] = np.percentile(vals,[50,95,100]).tolist() if vals else []
    args.output.with_suffix('.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
