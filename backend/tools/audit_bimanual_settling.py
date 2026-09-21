"""Offline fixed-target settling diagnostics; no sockets or hardware output."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--without-posture', action='store_true',
                        help='Diagnostic ablation in this offline process only')
    args = parser.parse_args()
    from g1_bimanual_runtime import load_engine
    load_engine(args.engine_root)
    import numpy as np
    from g1_bimanual_sim import BimanualSimulation, mink

    report = dict(data_kind='synthetic_fixed_targets', hardware_validated=False,
                  without_posture=args.without_posture, source_sha256={}, cases=[])
    for name in ('g1_bimanual_sim.py', 'g1_bimanual_motion_policy.py'):
        report['source_sha256'][name] = hashlib.sha256(
            (ROOT/'MuJoCo_G1_Controller/scripts'/name).read_bytes()).hexdigest()
    cases = [('rotation_y_minus45', [0, 0, 0], [0, -np.pi/4, 0]),
             ('translation_y_minus50mm', [0, -.05, 0], [0, 0, 0]),
             ('translation_z_minus50mm', [0, 0, -.05], [0, 0, 0])]
    for name, shift, rotation in cases:
        sim = BimanualSimulation()
        if args.without_posture:
            sim.motion['right'].posture_task.cost[:] = 0.
        home = sim.home_targets['right']
        goal = mink.SE3.from_rotation_and_translation(
            home.rotation() @ mink.SO3.exp(np.array(rotation, dtype=float)), home.translation()+shift)
        goals = dict(sim.home_targets, right=goal)
        row = dict(name=name, checkpoints=[])
        for tick in range(1, 1201):
            sim.step(goals)
            if tick not in (360, 720, 1200):
                continue
            policy = sim.motion['right']
            pose = sim.config.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
            q = sim.config.q[policy.qpos_ids]
            lower, upper = sim.model.jnt_range[policy.joint_ids].T
            item = dict(seconds=tick*sim.dt, state=sim.state, reason=sim.reason,
                position_error_mm=float(np.linalg.norm(pose.translation()-goal.translation())*1000),
                rotation_error_deg=float(np.rad2deg(np.linalg.norm(
                    (pose.rotation().inverse() @ goal.rotation()).log()))),
                joint_angles_deg=np.rad2deg(q).tolist(),
                joint_margin_deg=np.rad2deg(np.minimum(q-lower, upper-q)).tolist(),
                speed_peak_deg_s=float(np.rad2deg(np.max(np.abs(sim.velocity[policy.dofs])))),
                clearance_mm=float(sim.clearance(sim.config.q)*1000),
                motion=policy.diagnostics())
            row['checkpoints'].append(item)
            print(json.dumps(dict(case=name, **item)), flush=True)
        report['cases'].append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2, allow_nan=False)
        output.write('\n')


if __name__ == '__main__':
    main()
