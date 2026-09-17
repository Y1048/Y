"""Offline A/B replay of one active episode; no sockets, SDK or robot output.

Recorded CSV targets are held on the controller's fixed timestep using their
send_monotonic_s timestamps. This reconstructs targets, not unlogged IK ticks.
"""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
from collections import Counter
from pathlib import Path
import subprocess
import tempfile

import numpy as np

import replay_upstream_mink as replay


def read_episode(path):
    raw = path.read_bytes()
    samples = []
    ended = False
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
        packet = json.loads(row['raw_json_text'])
        arm = packet['right_arm']
        if not arm['active']:
            ended = ended or bool(samples)
            continue
        if ended:
            raise ValueError('Select a CSV with one active episode for this comparison')
        if not packet.get('simulation_only'):
            raise ValueError('This replay requires simulation-only targets')
        time = float(row['send_monotonic_s'])
        pos = np.asarray(arm['target_position'], dtype=float)
        rot = np.asarray(arm['target_rotation_matrix_robot'], dtype=float)
        joints = np.asarray(packet['all_joint_q_rad'], dtype=float)
        if (pos.shape != (3,) or rot.shape != (3, 3) or joints.shape != (29,)
                or not all(np.isfinite(x).all() for x in (time, pos, rot, joints))):
            raise ValueError('Invalid or nonfinite sample')
        if samples and time <= samples[-1][0]:
            raise ValueError('Non-monotonic timestamp')
        samples.append((time, pos, rot, joints))
    if not samples:
        raise ValueError('No active samples')
    return samples, hashlib.sha256(raw).hexdigest()


def run(samples, tracker_class):
    original = replay.UpstreamMinkTracking
    try:
        replay.UpstreamMinkTracking = tracker_class
        model, planner, tracker = replay.build()
    finally:
        replay.UpstreamMinkTracking = original
    q = replay.base._initial_configuration(model)
    for name, value in zip(replay.base.g1.G1_29_JOINTS, samples[0][3]):
        jid = replay.base._joint_id(model, name)
        q[model.jnt_qposadr[jid]] = value
    initial = q.copy()
    planner.configuration.update(q)
    tracker.Reset(q)
    frozen = np.ones(len(q), dtype=bool)
    frozen[planner.qpos_ids] = False
    index = 0
    metrics = []
    statuses = Counter()
    previous = np.zeros(7)
    acceleration_violations = 0
    for elapsed in np.arange(0., samples[-1][0]-samples[0][0], tracker.dt_s):
        while index+1 < len(samples) and samples[index+1][0]-samples[0][0] <= elapsed:
            index += 1
        _, pos, rot, _ = samples[index]
        goal = replay.base._matrix_to_se3(rot, pos)
        step = tracker.Track(q, goal)
        q = step.q
        statuses[step.status] += 1
        assert planner.CheckConfiguration(q), 'Geometry/joint limit violation'
        np.testing.assert_allclose(q[frozen], initial[frozen], atol=1e-10)
        vel = np.asarray(step.velocity_rad_s)
        assert np.all(abs(vel) <= np.asarray(tracker.velocity_limits)+1e-6)
        acceleration_violations += int(np.any(
            abs(vel-previous)/tracker.dt_s > np.asarray(tracker.acceleration_limits)+1e-5))
        previous = vel
        planner.configuration.update(q)
        pose = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
        angle = np.degrees(replay.base._rotation_error_radians(rot, pose.rotation().as_matrix()))
        metrics.append((elapsed, angle, np.linalg.norm(pos-pose.translation()),
                        planner.GetClearance(q), q[planner.qpos_ids[2]],
                        tracker.target_projected))
    m = np.asarray(metrics)
    return {
        'ticks': len(m), 'statuses': dict(statuses),
        'rotation_median_deg': float(np.median(m[:, 1])),
        'rotation_p95_deg': float(np.percentile(m[:, 1], 95)),
        'rotation_max_deg': float(max(m[:, 1])),
        'final_two_seconds_rotation_median_deg': float(np.median(m[m[:, 0] >= m[-1, 0]-2, 1])),
        'position_p95_cm': float(np.percentile(m[:, 2], 95)*100),
        'clearance_min_mm': float(min(m[:, 3])*1000),
        'shoulder_yaw_min_deg': float(np.degrees(min(m[:, 4]))),
        'shoulder_yaw_max_deg': float(np.degrees(max(m[:, 4]))),
        'acceleration_violations_including_hard_stops': acceleration_violations,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--baseline-ref', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    samples, digest = read_episode(args.csv)
    relative = 'MuJoCo_G1_Controller/scripts/g1_upstream_mink_tracking.py'
    baseline_source = subprocess.check_output(
        ['git', 'show', f'{args.baseline_ref}:{relative}'], cwd=replay.ROOT)
    with tempfile.TemporaryDirectory() as directory:
        module_path = Path(directory)/'baseline_tracking.py'
        module_path.write_bytes(baseline_source)
        spec = importlib.util.spec_from_file_location('baseline_tracking', module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        baseline = run(samples, module.UpstreamMinkTracking)
    candidate = run(samples, replay.UpstreamMinkTracking)
    report = {'simulation_only': True, 'hardware_validation': False,
              'sampling': 'send timestamps, zero-order hold at fixed controller dt; one active episode',
              'csv': str(args.csv), 'csv_sha256': digest, 'active_samples': len(samples),
              'baseline_ref': args.baseline_ref,
              'baseline_source_sha256': hashlib.sha256(baseline_source).hexdigest(),
              'candidate_source_sha256': hashlib.sha256((replay.ROOT/relative).read_bytes()).hexdigest(),
              'baseline': baseline, 'candidate': candidate}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
