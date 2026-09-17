"""Independent generated IK audit; no transport, SDK, robot or measured data.

Acceptance values below are predeclared engineering review targets, not physical
robot tolerances or an assertion that every fixed Cartesian pose is reachable.
An independent bounded pose fit supplies a collision-checked endpoint witness.
Run: python audit_mink_precision.py --output logs/test_results/precision_audit.json
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

import mujoco
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

import replay_upstream_mink as replay
from replay_upstream_mink import base, ROOT


# Fixed BEFORE collecting the current implementation's results. These are
# proposed acceptance criteria; failed cases stay in the report unchanged.
CRITERIA = {
    "fine_translation_endpoint_mm": .5,
    "fine_translation_rotation_deg": .5,
    "fixed_rotation_endpoint_mm": 2.,
    "fixed_rotation_orientation_deg": 1.,
    "fixed_rotation_proximal_excursion_deg": 5.,
    "mixed_endpoint_mm": 2.,
    "mixed_orientation_deg": 1.,
    "roundtrip_joint_drift_deg": 3.,
    "minimum_clearance_m": .005,
    "frozen_q_tolerance": 1e-10,
    "velocity_tolerance_rad_s": 1e-6,
    "acceleration_tolerance_rad_s2": 1e-5,
    "witness_endpoint_mm": .1,
    "witness_orientation_deg": .1,
}


def pose(planner, q):
    planner.configuration.update(q)
    value = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
    return value.translation().copy(), value.rotation().as_matrix().copy()


def residual(actual, target):
    position, rotation = actual
    target_position, target_rotation = target
    return float(np.linalg.norm(position-target_position)), float(
        np.linalg.norm(Rotation.from_matrix(target_rotation.T @ rotation).as_rotvec()))


def witness(planner, q, target, wrist_only=False):
    """Find an endpoint witness, never used as controller input or command."""
    ids = planner.qpos_ids[4:] if wrist_only else planner.qpos_ids
    joint_ids = planner.joint_ids[4:] if wrist_only else planner.joint_ids
    limits = planner.model.jnt_range[joint_ids]
    candidate = q.copy()

    def error(angles):
        candidate[ids] = angles
        position, rotation = pose(planner, candidate)
        return np.r_[100.*(position-target[0]), Rotation.from_matrix(target[1].T @ rotation).as_rotvec()]

    solution = least_squares(error, q[ids], bounds=(limits[:, 0]+1e-7, limits[:, 1]-1e-7),
                             max_nfev=120, ftol=1e-11, xtol=1e-11, gtol=1e-11)
    candidate[ids] = solution.x
    pos_error, rot_error = residual(pose(planner, candidate), target)
    geometry = bool(planner.CheckConfiguration(candidate))
    verified = (geometry and pos_error*1000 < CRITERIA['witness_endpoint_mm']
                and np.degrees(rot_error) < CRITERIA['witness_orientation_deg'])
    return dict(endpoint_witness_found=bool(verified), collision_clear=geometry,
                position_error_mm=pos_error*1000, orientation_error_deg=float(np.degrees(rot_error)),
                proximal_delta_max_deg=float(np.degrees(abs(candidate[planner.qpos_ids[:4]]-q[planner.qpos_ids[:4]])).max()))


def run_case(model, planner, tracker, neutral, specification):
    q = specification['q'].copy()
    planner.ResetDetour()
    tracker.Reset(q)
    # A non-neutral arm is away from its engage reference, as in a live session.
    planner.posture_reference = neutral.copy()
    planner.posture_task.set_target(neutral)
    settle_goal = base._matrix_to_se3(pose(planner, q)[1], pose(planner, q)[0])
    settle_origin = q.copy()
    settle_frozen = np.ones(len(q), dtype=bool)
    settle_frozen[planner.qpos_ids] = False
    settle_velocity = np.zeros(7)
    settle_violations = Counter()
    for _ in range(120):
        before = q.copy()
        q = tracker.Track(q, settle_goal).q
        velocity = (q[planner.qpos_ids]-before[planner.qpos_ids])/tracker.dt_s
        if not planner.CheckConfiguration(q):
            settle_violations['geometry_or_joint_limit'] += 1
        if np.max(abs(q[settle_frozen]-settle_origin[settle_frozen])) > CRITERIA['frozen_q_tolerance']:
            settle_violations['frozen_joint'] += 1
        if np.any(abs(velocity) > np.asarray(tracker.velocity_limits)+CRITERIA['velocity_tolerance_rad_s']):
            settle_violations['velocity'] += 1
        if np.any(abs(velocity-settle_velocity)/tracker.dt_s > np.asarray(tracker.acceleration_limits)+CRITERIA['acceleration_tolerance_rad_s2']):
            settle_violations['acceleration'] += 1
        settle_velocity = velocity
    # Fixed two-second prelude is not an assertion that the posture objective
    # has converged. Keep its derivative/history and report any residual drift.
    origin = q.copy()
    start_position, start_rotation = pose(planner, q)
    if specification['kind'] == 'translation':
        target_position = start_position + specification['delta']
        target_rotation = start_rotation
    elif specification['kind'] == 'rotation':
        target_position = start_position + specification.get('target_offset', np.zeros(3))
        target_rotation = start_rotation @ Rotation.from_rotvec(specification['rotvec']).as_matrix()
    else:
        target_q = origin.copy()
        target_q[planner.qpos_ids] += specification['joint_delta']
        target_position, target_rotation = pose(planner, target_q)
        if not planner.CheckConfiguration(target_q):
            raise ValueError(f"Generated FK endpoint collides: {specification['name']}")
    target = (target_position, target_rotation)
    final_target = (target_position, start_rotation @ Rotation.from_rotvec(-specification['rotvec']).as_matrix()) if specification.get('fast_reversal') else target
    reachable = witness(planner, origin, final_target)
    wrist_witness = witness(planner, origin, final_target, True) if specification['kind'] == 'rotation' else None
    relative_rotation = Rotation.from_matrix(start_rotation.T @ target_rotation).as_rotvec()
    frozen = np.ones(len(q), dtype=bool)
    frozen[planner.qpos_ids] = False
    previous_q = q.copy()
    previous_velocity = np.asarray(tracker.acceleration_bound.previous).copy()
    statuses = Counter()
    metrics = []
    track_times_ms = []
    constraint_failures = Counter()
    endpoint = None
    max_velocity = max_acceleration = 0.
    ticks = 480 if specification.get('roundtrip') else 300
    started = time.perf_counter()
    for tick in range(ticks):
        seconds = tick*tracker.dt_s
        if specification.get('fast_reversal'):
            # Deliberately exceeds the configured reference rate: backlog must
            # remain bounded by the joint limits and eventually converge.
            factor = min(seconds/.05, 1.) if seconds < .5 else max(1.-2.*(seconds-.5)/.06, -1.)
        elif specification.get('roundtrip'):
            factor = min(seconds/1., 1.) if seconds < 4. else max(1.-(seconds-4.)/1., 0.)
        else:
            factor = min(seconds/1., 1.)
        # Smooth timing limits do not themselves guarantee joint acceleration;
        # the controller must enforce that and is checked below independently.
        if not specification.get('fast_reversal'):
            factor = .5-.5*np.cos(np.pi*factor)
        goal_position = start_position + factor*(target_position-start_position)
        goal_rotation = start_rotation @ Rotation.from_rotvec(factor*relative_rotation).as_matrix()
        before_track = time.perf_counter_ns()
        step = tracker.Track(q, base._matrix_to_se3(goal_rotation, goal_position))
        track_times_ms.append((time.perf_counter_ns()-before_track)/1e6)
        q = step.q
        statuses[step.status] += 1
        velocity = (q[planner.qpos_ids]-previous_q[planner.qpos_ids])/tracker.dt_s
        max_velocity = max(max_velocity, float(abs(velocity).max()))
        if previous_velocity is not None:
            acceleration = abs(velocity-previous_velocity)/tracker.dt_s
            max_acceleration = max(max_acceleration, float(acceleration.max()))
            if np.any(acceleration > np.asarray(tracker.acceleration_limits)+CRITERIA['acceleration_tolerance_rad_s2']):
                constraint_failures['acceleration'] += 1
        if np.any(abs(velocity) > np.asarray(tracker.velocity_limits)+CRITERIA['velocity_tolerance_rad_s']):
            constraint_failures['velocity'] += 1
        if not planner.CheckConfiguration(q):
            constraint_failures['geometry_or_joint_limit'] += 1
        if np.max(abs(q[frozen]-origin[frozen])) > CRITERIA['frozen_q_tolerance']:
            constraint_failures['frozen_joint'] += 1
        previous_q, previous_velocity = q.copy(), velocity
        pos_error, rot_error = residual(pose(planner, q), (goal_position, goal_rotation))
        proximal = np.degrees(abs(q[planner.qpos_ids[:4]]-origin[planner.qpos_ids[:4]]))
        metrics.append((pos_error*1000, np.degrees(rot_error), proximal.max(), planner.GetClearance(q)))
        if tick == 239:
            endpoint = metrics[-1][:2]
    values = np.asarray(metrics)
    end_position, end_rotation = endpoint if specification.get('roundtrip') else metrics[-1][:2]
    final_delta = float(np.degrees(abs(q[planner.qpos_ids]-origin[planner.qpos_ids])).max())
    kind = specification['kind']
    prefix = 'fine_translation' if kind == 'translation' else 'fixed_rotation' if kind == 'rotation' else 'mixed'
    failure_reasons = []
    if end_position > CRITERIA[prefix+'_endpoint_mm']:
        failure_reasons.append('endpoint_position')
    rot_key = prefix+('_rotation_deg' if kind == 'translation' else '_orientation_deg')
    if end_rotation > CRITERIA[rot_key]:
        failure_reasons.append('endpoint_orientation')
    proximal_review = kind == 'rotation' and 'target_offset' not in specification and values[:, 2].max() > CRITERIA['fixed_rotation_proximal_excursion_deg']
    if proximal_review and wrist_witness['endpoint_witness_found']:
        failure_reasons.append('proximal_excursion_with_wrist_only_endpoint_witness')
    if specification.get('roundtrip') and final_delta > CRITERIA['roundtrip_joint_drift_deg']:
        failure_reasons.append('roundtrip_joint_drift')
    if constraint_failures:
        failure_reasons.append('constraint_violation')
    if settle_violations:
        failure_reasons.append('settle_constraint_violation')
    return dict(name=specification['name'], kind=kind, ticks=ticks, timestep_s=tracker.dt_s,
                wall_seconds=time.perf_counter()-started, source='generated_model_kinematics',
                post_prelude_start_joint_deg=np.degrees(origin[planner.qpos_ids]).tolist(),
                prelude_duration_s=120*tracker.dt_s,
                prelude_drift_max_deg=float(np.degrees(abs(origin[planner.qpos_ids]-settle_origin[planner.qpos_ids])).max()),
                prelude_final_speed_max_deg_s=float(np.degrees(abs(settle_velocity)).max()),
                prelude_stationary_at_end=bool(np.degrees(abs(settle_velocity)).max() < .1),
                start_position_m=start_position.tolist(), start_rotation_matrix=start_rotation.tolist(),
                endpoint_position_m=final_target[0].tolist(), endpoint_rotation_matrix=final_target[1].tolist(),
                independent_endpoint_witness=reachable, wrist_only_endpoint_witness=wrist_witness,
                proximal_excursion_needs_review=bool(proximal_review),
                proximal_criterion_inconclusive=bool(proximal_review and not wrist_witness['endpoint_witness_found']),
                settled_prelude_constraint_failures=dict(settle_violations),
                final_position_error_mm=float(end_position), final_orientation_error_deg=float(end_rotation),
                worst_position_error_mm=float(values[:, 0].max()),
                proximal_excursion_max_deg=float(values[:, 2].max()),
                minimum_clearance_m=float(values[:, 3].min()), final_joint_delta_max_deg=final_delta,
                final_return_position_error_mm=float(metrics[-1][0]) if specification.get('roundtrip') else None,
                final_return_orientation_error_deg=float(metrics[-1][1]) if specification.get('roundtrip') else None,
                velocity_max_rad_s=max_velocity, finite_difference_acceleration_max_rad_s2=max_acceleration,
                track_ms_mean=float(np.mean(track_times_ms)), track_ms_p95=float(np.percentile(track_times_ms,95)),
                track_ms_max=float(max(track_times_ms)), track_over_timestep=sum(v > tracker.dt_s*1000 for v in track_times_ms),
                statuses=dict(statuses), constraint_failures=dict(constraint_failures),
                criterion_failures=failure_reasons,
                scope='endpoint witness does not prove path feasibility or physical safety')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case-filter', default='')
    parser.add_argument('--controller', choices=('current', 'priority'), default='current')
    args = parser.parse_args()
    source = ROOT/'MuJoCo_G1_Controller/scripts/g1_upstream_mink_tracking.py'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if args.controller == 'priority':
        from prototype_mink_task_priority import TaskPriorityPrototype
        replay.UpstreamMinkTracking = TaskPriorityPrototype
    model, planner, tracker = replay.build()
    neutral = base._initial_configuration(model)
    poses = {'neutral': neutral.copy()}
    for name, offset in [('reach', [-30,-12,20,-20,15,10,-10]), ('folded', [-15,-20,35,25,20,-20,15])]:
        q = neutral.copy()
        q[planner.qpos_ids] += np.deg2rad(offset)
        assert planner.CheckConfiguration(q), name
        poses[name] = q
    margin = poses['reach'].copy()
    margin[planner.qpos_ids[6]] = model.jnt_range[planner.joint_ids[6], 1]-np.deg2rad(10.)
    assert planner.CheckConfiguration(margin)
    poses['wrist_margin'] = margin
    cases = []
    for pose_name in ('neutral', 'reach'):
        for millimeters in (1,3,5):
            for axis in range(3):
                cases.append(dict(name=f'{pose_name}_{millimeters}mm_axis{axis}', kind='translation',
                                  q=poses[pose_name], delta=np.eye(3)[axis]*millimeters/1000.))
    for pose_name in ('reach', 'folded', 'wrist_margin'):
        for axis in range(3):
            cases.append(dict(name=f'{pose_name}_rotation_axis{axis}', kind='rotation', q=poses[pose_name],
                              rotvec=np.eye(3)[axis]*np.deg2rad(20.)))
    for pose_name in ('neutral', 'reach'):
        cases.append(dict(name=f'{pose_name}_mixed_roundtrip', kind='mixed', q=poses[pose_name], roundtrip=True,
                          joint_delta=np.deg2rad([-2., 1., 2., -1., 5., -3., 4.])))
    cases.append(dict(name='reach_rotation_lag20mm', kind='rotation', q=poses['reach'],
                      rotvec=np.array([0.,0.,np.deg2rad(20.)]), target_offset=np.array([.02,0.,0.])))
    cases.append(dict(name='reach_rotation_fast_reversal', kind='rotation', q=poses['reach'],
                      rotvec=np.array([0.,0.,np.deg2rad(30.)]), fast_reversal=True))
    results = []
    for case in cases:
        if args.case_filter and args.case_filter not in case['name']:
            continue
        results.append(run_case(model, planner, tracker, neutral, case))
        result = results[-1]
        print(json.dumps(dict(name=result['name'], failures=result['criterion_failures'],
                              position_mm=result['final_position_error_mm'],
                              orientation_deg=result['final_orientation_error_deg'],
                              proximal_deg=result['proximal_excursion_max_deg'])), flush=True)
    report = dict(schema='g1.offline.ik.precision.audit.v1', controller=args.controller, simulated_generated=True,
                  measured_g1_data=False, hardware_validation=False, source_sha256=source_hash,
                  source_changed_during_run=source_hash != hashlib.sha256(source.read_bytes()).hexdigest(),
                  mujoco_version=mujoco.__version__, predeclared_acceptance=CRITERIA, cases=results,
                  failures=sum(bool(r['criterion_failures']) for r in results))
    report['mujoco_module_path'] = mujoco.__file__
    report['audit_source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['inconclusive_cases'] = sum(bool(r['proximal_criterion_inconclusive']) and not r['criterion_failures'] for r in results)
    report['passing_cases'] = sum(not r['criterion_failures'] and not r['proximal_criterion_inconclusive'] for r in results)
    report['accepted'] = bool(results) and not report['failures'] and not report['inconclusive_cases'] and not report['source_changed_during_run']
    report['timing_scope'] = 'Wall-clock process timing on current host load; no real-time or device timing guarantee.'
    report['comparison_scope'] = ('Identical scenario construction rules, not identical numerical goals: '
                                  'each controller runs a fixed two-second prelude; goal is built '
                                  'from its resulting pose. See reported start/endpoint values.')
    if args.controller == 'priority':
        report['prototype_source_sha256'] = hashlib.sha256((Path(__file__).parent/'prototype_mink_task_priority.py').read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"REPORT {args.output}: {len(results)} cases, {report['failures']} need review", flush=True)


if __name__ == '__main__':
    main()
