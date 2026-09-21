"""Compare synthetic fixed targets with the preserved single-arm reference.

Offline only: no sockets, Unity, SDK, or motor command execution. A difference
is a measurement, not automatically a regression: collision sets differ.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
sys.path.insert(0, str(ROOT / 'experiments/twist2_right_arm_manual'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ticks', type=int, default=360)
    args = parser.parse_args()
    if args.ticks < 2:
        parser.error('--ticks must be at least 2')
    from g1_bimanual_runtime import load_engine
    load_engine(args.engine_root)
    import numpy as np
    from g1_bimanual_sim import BimanualSimulation, mink
    from replay_upstream_mink import build, base

    cases = [(f'rotation_{axis}_{sign:+d}', np.zeros(3), np.eye(3)[i]*sign*np.pi/4)
             for i, axis in enumerate('xyz') for sign in (-1, 1)]
    cases += [(f'translation_{axis}_{sign:+d}', np.eye(3)[i]*sign*.05, np.zeros(3))
              for i, axis in enumerate('xyz') for sign in (-1, 1)]
    report = dict(schema='g1.bimanual.single_arm.comparison.v1',
                  data_kind='synthetic_fixed_targets', hardware_validated=False,
                  ticks=args.ticks, cases=[], source_sha256={})
    for name in ('g1_bimanual_sim.py', 'g1_bimanual_motion_policy.py',
                 'g1_upstream_mink_tracking.py', 'g1_standard_mink_planner.py'):
        report['source_sha256'][name] = hashlib.sha256(
            (ROOT/'MuJoCo_G1_Controller/scripts'/name).read_bytes()).hexdigest()
    for name, shift, rotation in cases:
        sim = BimanualSimulation()
        model, planner, tracking = build()
        q = base._initial_configuration(model)
        planner.configuration.update(q)
        tracking.Reset(q)
        home = sim.home_targets['right']
        goal = mink.SE3.from_rotation_and_translation(
            home.rotation() @ mink.SO3.exp(rotation), home.translation()+shift)
        goals = dict(sim.home_targets, right=goal)
        stats = {k: dict(position_error_mm=[], rotation_error_deg=[],
                        minimum_clearance_mm=200., statuses=Counter(),
                        speed_peak_deg_s=0., acceleration_peak_deg_s2=0.)
                 for k in ('single', 'bimanual')}
        peak_difference = 0.
        previous = {k: np.zeros(7) for k in stats}
        left_peak = 0.
        for _ in range(args.ticks):
            accepted = sim.step(goals)
            result = tracking.Track(q, goal)
            q = result.q
            planner.configuration.update(q)
            peak_difference = max(peak_difference, float(np.max(np.abs(
                sim.config.q[sim.motion['right'].qpos_ids]-q[planner.qpos_ids]))))
            left_peak = max(left_peak, float(np.max(np.abs(
                sim.config.q[sim.motion['left'].qpos_ids]-sim.home[sim.motion['left'].qpos_ids]))))
            for key, configuration, velocity, clearance, status in (
                ('single', planner.configuration, np.array(result.velocity_rad_s),
                 planner.GetClearance(q), result.status),
                ('bimanual', sim.config, sim.velocity[sim.motion['right'].dofs],
                 sim.clearance(sim.config.q), sim.reason or ('tracking' if accepted else sim.state))):
                s = stats[key]
                pose = configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
                s['position_error_mm'].append(float(np.linalg.norm(pose.translation()-goal.translation())*1000))
                s['rotation_error_deg'].append(float(np.rad2deg(np.linalg.norm(
                    (pose.rotation().inverse() @ goal.rotation()).log()))))
                s['minimum_clearance_mm'] = min(s['minimum_clearance_mm'], float(clearance*1000))
                s['speed_peak_deg_s'] = max(s['speed_peak_deg_s'], float(np.rad2deg(np.max(np.abs(velocity)))))
                s['acceleration_peak_deg_s2'] = max(s['acceleration_peak_deg_s2'],
                    float(np.rad2deg(np.max(np.abs(velocity-previous[key]))/sim.dt)))
                previous[key] = velocity.copy()
                s['statuses'][status] += 1
        for s in stats.values():
            for metric in ('position_error_mm', 'rotation_error_deg'):
                values = s.pop(metric)
                s['final_'+metric] = values[-1]
                s['mean_'+metric] = float(np.mean(values))
                s['peak_'+metric] = max(values)
            s['statuses'] = dict(s['statuses'])
        row = dict(name=name, **stats, peak_joint_difference_deg=float(np.rad2deg(peak_difference)),
                   idle_left_peak_excursion_deg=float(np.rad2deg(left_peak)), final_state=sim.state)
        report['cases'].append(row)
        print(json.dumps(row), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
