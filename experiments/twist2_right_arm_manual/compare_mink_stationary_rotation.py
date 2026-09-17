"""Synthetic fixed-wrist-position rotation comparison; no transport or G1."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

import numpy as np
from scipy.spatial.transform import Rotation

import replay_upstream_mink as replay


def run(tracker_class, axis, ticks=360):
    original = replay.UpstreamMinkTracking
    try:
        replay.UpstreamMinkTracking = tracker_class
        model, planner, tracker = replay.build()
    finally:
        replay.UpstreamMinkTracking = original
    q = replay.base._initial_configuration(model)
    initial = q.copy()
    planner.configuration.update(q)
    tracker.Reset(q)
    pose = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
    position, rotation = pose.translation().copy(), pose.rotation().as_matrix().copy()
    previous = np.zeros(7)
    metrics = []
    frozen = np.ones(len(q), dtype=bool)
    frozen[planner.qpos_ids] = False
    for tick in range(ticks):
        # 30 degrees over two seconds, then hold. Position stays exactly fixed.
        phase = min(tick*tracker.dt_s/2., 1.)
        angle = np.deg2rad(30.) * .5*(1.-np.cos(np.pi*phase))
        rot = rotation @ Rotation.from_rotvec(np.eye(3)[axis]*angle).as_matrix()
        goal = replay.base._matrix_to_se3(rot, position)
        step = tracker.Track(q, goal)
        assert step.applied, step.status
        q = step.q
        assert planner.CheckConfiguration(q)
        np.testing.assert_allclose(q[frozen], initial[frozen], atol=1e-10)
        vel = np.asarray(step.velocity_rad_s)
        assert np.all(abs(vel) <= np.asarray(tracker.velocity_limits)+1e-6)
        assert np.all(abs(vel-previous)/tracker.dt_s <= np.asarray(tracker.acceleration_limits)+1e-5)
        previous = vel
        planner.configuration.update(q)
        wrist = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
        metrics.append((np.max(abs(q[planner.qpos_ids[:4]]-initial[planner.qpos_ids[:4]])),
                        np.linalg.norm(wrist.translation()-position),
                        replay.base._rotation_error_radians(rot, wrist.rotation().as_matrix())))
    data = np.asarray(metrics)
    return dict(axis=axis, ticks=ticks, proximal_excursion_max_deg=float(np.degrees(data[:, 0].max())),
                position_error_max_mm=float(data[:, 1].max()*1000),
                position_error_final_mm=float(data[-1, 1]*1000),
                rotation_error_final_deg=float(np.degrees(data[-1, 2])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    relative = 'MuJoCo_G1_Controller/scripts/g1_upstream_mink_tracking.py'
    baseline = subprocess.check_output(['git', 'show', f'{args.baseline_ref}:{relative}'], cwd=replay.ROOT)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'baseline.py'
        path.write_bytes(baseline)
        spec = importlib.util.spec_from_file_location('baseline', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        before = [run(module.UpstreamMinkTracking, axis) for axis in range(3)]
    after = [run(replay.UpstreamMinkTracking, axis) for axis in range(3)]
    report = dict(simulation_only=True, synthetic_targets=True, hardware_validation=False,
                  baseline_ref=args.baseline_ref, baseline=before, candidate=after,
                  candidate_source_sha256=hashlib.sha256((replay.ROOT/relative).read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
