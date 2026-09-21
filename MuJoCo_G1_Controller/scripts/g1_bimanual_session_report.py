"""Read-only report for bimanual Unity simulation JSONL sessions.

Static analysis does not replay control. --replay uses the validated simulator
selected by g1_bimanual_runtime.py. No Unity, G1, DDS, SSH or motor output.
"""
from g1_bimanual_limits import JOINT_VELOCITY_LIMITS_RAD_S
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from g1_bimanual_limits import (
    JOINT_ACCELERATION_LIMIT_RAD_S2, JOINT_VELOCITY_LIMIT_RAD_S)

ROOT = Path(__file__).resolve().parents[2]
SIM_DT = 1.0 / 60.0
LEGACY_CAPS_DEG_S = np.asarray([90.0] * 4 + [180.0] * 3 + [90.0] * 4 + [180.0] * 3)
# Match the established controller regression tolerance: +1e-4 rad/s^2 is
# numerical comparison slack only, applied to the relevant recorded/current cap.
LEGACY_ACCELERATION_LIMIT_DEG_S2 = 60.0
ACCELERATION_NUMERICAL_TOLERANCE_DEG_S2 = float(np.rad2deg(1e-4))
SOURCE_FILES = (
    'g1_bimanual_runtime.py', 'g1_bimanual_sim.py',
    'g1_bimanual_unity_sim.py', 'g1_bimanual_motion_policy.py',
    'g1_bimanual_return.py', 'g1_bimanual_limits.py')


def _recorded_motion_limits(run):
    """Keep historical output validation independent of today's controller caps."""
    legacy = dict(
        source='legacy_defaults',
        velocity_rad_s=np.deg2rad(LEGACY_CAPS_DEG_S).tolist(),
        acceleration_rad_s2=[math.radians(LEGACY_ACCELERATION_LIMIT_DEG_S2)] * 14)
    if run is None or 'motion_limits' not in run:
        return legacy, False
    metadata = run['motion_limits']
    try:
        limits = dict(source='run.motion_limits')
        for key in ('velocity_rad_s', 'acceleration_rad_s2'):
            raw = np.asarray(metadata[key])
            if raw.dtype.kind not in 'fiu':
                raise ValueError('Motion limits must be numeric')
            values = np.asarray(raw, dtype=float)
            if values.ndim == 0:
                values = np.full(14, float(values))
            if values.shape != (14,) or not np.isfinite(values).all() or np.any(values <= 0.0):
                raise ValueError('Motion limits must be positive finite scalars or 14-joint arrays')
            limits[key] = values.tolist()
        return limits, False
    except (KeyError, TypeError, ValueError, OverflowError):
        # Keep the summary available, but never pass an invalid limit record.
        legacy['source'] = 'invalid_metadata_legacy_fallback'
        return legacy, True


def _current_motion_limits():
    return dict(
        source='current_code',
        velocity_rad_s=list(JOINT_VELOCITY_LIMITS_RAD_S),
        acceleration_rad_s2=[JOINT_ACCELERATION_LIMIT_RAD_S2] * 14)


def _open_text(path):
    return gzip.open(path, 'rt', encoding='utf-8') if path.suffix == '.gz' else path.open(encoding='utf-8')


def _percentiles(values):
    if not values:
        return None
    a = np.asarray(values, dtype=float)
    return {name: float(np.percentile(a, value))
            for name, value in [('p50', 50), ('p95', 95), ('p99', 99), ('max', 100)]}

def _current_source_hashes():
    scripts = Path(__file__).resolve().parent
    return {name: hashlib.sha256((scripts / name).read_bytes()).hexdigest()
            for name in SOURCE_FILES}


def _update_return_metadata(active_return, motion):
    if not active_return or not motion:
        return
    active_return['near_hands_recovery'] = (
        active_return['near_hands_recovery']
        or bool(motion.get('near_hands_recovery')))
    side = str(motion.get('separation_side') or '')
    if side:
        active_return['separation_side'] = side
    for key in ('return_start_clearance_m', 'near_hands_start_clearance_m'):
        value = motion.get(key)
        if isinstance(value, (int, float)) and math.isfinite(value):
            active_return[key] = float(value)


def _quest_cycle_failures(report):
    failures = []
    summary = report.get('operator_summary') or {}
    if report.get('accepted_inputs', 0) <= 0:
        failures.append('quest_cycle_no_operator_input')
    if report.get('tracking_starts', 0) < 2:
        failures.append('quest_cycle_no_reengage')
    if summary.get('pinch_returns', 0) < 1:
        failures.append('quest_cycle_no_completed_pinch_return')
    if report.get('final_state') not in ('ready', 'tracking'):
        failures.append('quest_cycle_final_state_not_ready_or_tracking')
    return failures


def _latest_session():
    folder = ROOT / 'logs/test_results/bimanual'
    candidates = sorted(folder.glob('unity_*.jsonl'),
                        key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f'No bimanual Unity log found under {folder}')
    # Short headless smoke runs have no input and should not hide the latest
    # operator session. Scan the stream to EOF: an operator can engage after
    # more than 5,000 READY rows, and this path does not retain rows in memory.
    for path in candidates:
        try:
            with path.open(encoding='utf-8') as stream:
                for line in stream:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if row.get('kind') == 'input' and row.get('accepted'):
                        return path
        except (OSError, UnicodeError):
            continue
    return candidates[0]


def analyze_session(path):
    path = Path(path).resolve()
    counts = Counter()
    reject_reasons = Counter()
    braking_reasons = Counter()
    transitions = []
    input_edges = []
    control_ticks = []
    tracking_ticks = []
    loop_periods = []
    run = None
    previous_state_key = None
    previous_state = None
    previous_input_flags = None
    previous_q = None
    previous_velocity = None
    max_speed = 0.0
    max_acceleration = 0.0
    max_speed_excess = 0.0
    max_acceleration_excess = 0.0
    motion_limits, invalid_motion_limits = _recorded_motion_limits(None)
    speed_caps_deg_s = np.rad2deg(motion_limits['velocity_rad_s'])
    acceleration_caps_deg_s2 = np.rad2deg(motion_limits['acceleration_rad_s2'])
    tracking_starts = 0
    active_return = None
    returns = []
    blocked_rows = 0
    nonfinite_q_rows = 0
    malformed_joint_rows = 0
    accepted_inputs = 0
    malformed_json_rows = 0

    with _open_text(path) as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                malformed_json_rows += 1
                continue
            kind = row.get('kind')
            counts[kind] += 1
            if kind == 'run' and run is None:
                run = row
                motion_limits, invalid_motion_limits = _recorded_motion_limits(run)
                speed_caps_deg_s = np.rad2deg(motion_limits['velocity_rad_s'])
                acceleration_caps_deg_s2 = np.rad2deg(motion_limits['acceleration_rad_s2'])
                continue
            if kind == 'reject':
                reject_reasons[str(row.get('reason', 'unknown'))] += 1
                continue
            if kind == 'input':
                if not row.get('accepted'):
                    continue
                accepted_inputs += 1
                try:
                    packet = json.loads(row['raw_json_text'])
                    flags = (bool(packet['engage']), bool(packet['return_home']),
                             bool(packet['left']['tracked']), bool(packet['right']['tracked']))
                except (KeyError, TypeError, json.JSONDecodeError):
                    continue
                if flags != previous_input_flags:
                    input_edges.append(dict(sequence=packet.get('sequence'), engage=flags[0],
                                            return_home=flags[1], left_tracked=flags[2],
                                            right_tracked=flags[3]))
                    previous_input_flags = flags
                continue
            if kind != 'state':
                continue
            state = str(row.get('state', ''))
            reason = str(row.get('reason', ''))
            state_key = (state, reason)
            if state_key != previous_state_key:
                transitions.append(dict(index=counts['state'] - 1,
                                        monotonic_s=row.get('monotonic_s'),
                                        sequence=row.get('sequence'), state=state,
                                        reason=reason, tick_action=row.get('tick_action'),
                                        return_stage=(row.get('return_motion') or {}).get('stage')))
            if state != previous_state:
                if state == 'tracking':
                    tracking_starts += 1
                if state == 'returning':
                    active_return = dict(
                        reason=reason, start_monotonic_s=row.get('monotonic_s'),
                        start_sequence=row.get('sequence'), stages=[], replans=0,
                        near_hands_recovery=False, separation_side='',
                        return_start_clearance_m=None,
                        near_hands_start_clearance_m=None)
                elif state == 'ready' and active_return is not None:
                    final_motion = row.get('return_motion') or {}
                    _update_return_metadata(active_return, final_motion)
                    final_stage = final_motion.get('stage')
                    if final_stage and (not active_return['stages'] or active_return['stages'][-1] != final_stage):
                        active_return['stages'].append(final_stage)
                    active_return['end_monotonic_s'] = row.get('monotonic_s')
                    active_return['end_sequence'] = row.get('sequence')
                    if active_return['start_monotonic_s'] is not None and row.get('monotonic_s') is not None:
                        active_return['wall_s'] = row['monotonic_s'] - active_return['start_monotonic_s']
                    active_return['internal_simulation_s'] = (row.get('return_motion') or {}).get('elapsed_simulation_s')
                    returns.append(active_return)
                    active_return = None
                previous_state = state
            previous_state_key = state_key

            motion = row.get('return_motion') or {}
            if active_return is not None:
                _update_return_metadata(active_return, motion)
                stage = motion.get('stage')
                if stage and (not active_return['stages'] or active_return['stages'][-1] != stage):
                    active_return['stages'].append(stage)
                active_return['replans'] = max(active_return['replans'], int(motion.get('replans') or 0))
            tick_ms = row.get('control_tick_ms')
            if isinstance(tick_ms, (int, float)) and math.isfinite(tick_ms):
                control_ticks.append(float(tick_ms))
                if state == 'tracking':
                    tracking_ticks.append(float(tick_ms))
            period_ms = row.get('loop_period_ms')
            if isinstance(period_ms, (int, float)) and math.isfinite(period_ms):
                loop_periods.append(float(period_ms))
            ik_reason = row.get('ik_reason')
            if ik_reason:
                braking_reasons[str(ik_reason)] += 1
            if state == 'blocked':
                blocked_rows += 1

            q = row.get('q_rad')
            if not isinstance(q, list) or len(q) != 14:
                malformed_joint_rows += 1
                previous_q = previous_velocity = None
                continue
            q = np.asarray(q, dtype=float)
            if not np.isfinite(q).all():
                nonfinite_q_rows += 1
                previous_q = previous_velocity = None
                continue
            if previous_q is not None:
                velocity = (q - previous_q) / SIM_DT
                speed_deg = np.rad2deg(np.abs(velocity))
                max_speed = max(max_speed, float(np.max(speed_deg)))
                max_speed_excess = max(max_speed_excess, float(np.max(speed_deg - speed_caps_deg_s)))
                if previous_velocity is not None:
                    acceleration = (velocity - previous_velocity) / SIM_DT
                    acceleration_deg = np.rad2deg(np.abs(acceleration))
                    max_acceleration = max(max_acceleration,
                                           float(np.max(acceleration_deg)))
                    max_acceleration_excess = max(max_acceleration_excess, float(np.max(
                        acceleration_deg - acceleration_caps_deg_s2)))
                previous_velocity = velocity
            previous_q = q
    current_hashes = _current_source_hashes()
    logged_hashes = {} if run is None else dict(run.get('source_sha256') or {})
    source_match = {name: (logged_hashes.get(name) == digest)
                    for name, digest in current_hashes.items()}
    failures = []
    warnings = []
    if run is None:
        failures.append('missing_run_metadata')
    if invalid_motion_limits:
        failures.append('invalid_motion_limits_metadata')
    if blocked_rows:
        failures.append('blocked_state_observed')
    if nonfinite_q_rows or malformed_joint_rows:
        failures.append('invalid_joint_output')
    if malformed_json_rows:
        failures.append('malformed_json_rows_present')
    if max_speed_excess > 1e-4:
        failures.append('output_speed_limit_exceeded')
    if max_acceleration_excess > ACCELERATION_NUMERICAL_TOLERANCE_DEG_S2:
        failures.append('output_acceleration_limit_exceeded')
    if reject_reasons:
        warnings.append('rejected_packets_present')
    if any(not matched for matched in source_match.values()):
        warnings.append('logged_source_differs_from_current')
    tracking_percentiles = _percentiles(tracking_ticks)
    if tracking_percentiles and tracking_percentiles['p95'] > 1000.0 / 60.0:
        warnings.append('tracking_tick_p95_exceeds_nominal_60hz_period')
    if active_return is not None:
        warnings.append('return_incomplete_at_log_end')

    return_reasons = Counter(item['reason'] for item in returns)
    separation_sides = Counter(
        item['separation_side'] for item in returns if item.get('separation_side'))
    operator_summary = dict(
        completed_returns=len(returns),
        pinch_returns=return_reasons.get('pinch', 0),
        tracking_lost_returns=return_reasons.get('tracking_lost', 0),
        input_timeout_returns=return_reasons.get('input_timeout', 0),
        session_changed_returns=return_reasons.get('session_changed', 0),
        near_hands_recoveries=sum(
            bool(item.get('near_hands_recovery')) for item in returns),
        separation_sides=dict(separation_sides),
        reengage_count=max(0, tracking_starts - 1))

    return dict(schema='g1.bimanual.session.report.v1', simulation_only=True,
                source_log=str(path), source_log_bytes=path.stat().st_size,
                run=run, counts=dict(counts), accepted_inputs=accepted_inputs,
                transitions=transitions, input_edges=input_edges,
                tracking_starts=tracking_starts,
                reengage_count=max(0, tracking_starts - 1), returns=returns,
                operator_summary=operator_summary,
                reject_reasons=dict(reject_reasons), braking_reasons=dict(braking_reasons),
                control_tick_ms=_percentiles(control_ticks),
                tracking_tick_ms=tracking_percentiles,
                loop_period_ms=_percentiles(loop_periods),
                output_fixed_dt=dict(max_speed_deg_s=max_speed,
                                     max_speed_excess_deg_s=max_speed_excess,
                                     max_acceleration_deg_s2=max_acceleration,
                                     max_acceleration_excess_deg_s2=max_acceleration_excess),
                validation_motion_limits=motion_limits,
                blocked_rows=blocked_rows, nonfinite_joint_rows=nonfinite_q_rows,
                malformed_joint_rows=malformed_joint_rows,
                malformed_json_rows=malformed_json_rows,
                current_source_sha256=current_hashes,
                logged_source_matches_current=source_match,
                failures=failures, warnings=warnings,
                final_state=None if not transitions else transitions[-1]['state'],
                final_reason=None if not transitions else transitions[-1]['reason'])


def replay_session(path):
    from g1_bimanual_sim import BimanualSimulation
    from g1_bimanual_unity_sim import UnityCycle, decode

    sim = BimanualSimulation()
    cycle = UnityCycle(sim)
    accepted_mismatches = 0
    state_mismatches = 0
    reason_mismatches = 0
    q_mismatch_max = 0.0
    minimum_clearance = 0.2
    maximum_speed = 0.0
    maximum_speed_ratio = 0.0
    maximum_acceleration = 0.0
    state_rows = 0
    input_rows = 0
    blocked_rows = 0
    run = None
    motion_limits = _current_motion_limits()
    flows = {name: dict(previous_state=None, tracking_starts=0,
                        completed_returns=Counter(), active_return_reason=None)
             for name in ('logged', 'current')}

    with _open_text(Path(path)) as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get('kind') == 'run' and run is None:
                run = row
                continue
            if row.get('kind') == 'input':
                input_rows += 1
                try:
                    packet = decode(row['raw_json_text'].encode('utf-8'))
                    accepted = cycle.receive(packet, row['receive_monotonic_s'])
                except (ValueError, UnicodeError, KeyError, TypeError):
                    accepted = False
                if accepted != bool(row.get('accepted')):
                    accepted_mismatches += 1
                continue
            if row.get('kind') != 'state':
                continue
            state_rows += 1
            before_velocity = sim.velocity[sim.dofs].copy()
            cycle.tick(row['monotonic_s'])
            blocked_rows += cycle.state == 'blocked'
            for name, state, reason in (
                    ('logged', row.get('state'), row.get('reason', '')),
                    ('current', cycle.state, cycle.reason)):
                flow = flows[name]
                if state != flow['previous_state']:
                    if state == 'tracking':
                        flow['tracking_starts'] += 1
                    if state == 'returning':
                        flow['active_return_reason'] = reason
                    elif state == 'ready' and flow['active_return_reason'] is not None:
                        flow['completed_returns'][flow['active_return_reason']] += 1
                        flow['active_return_reason'] = None
                    flow['previous_state'] = state
            if cycle.state != row.get('state'):
                state_mismatches += 1
            if cycle.reason != row.get('reason', ''):
                reason_mismatches += 1
            logged_q = row.get('q_rad')
            if isinstance(logged_q, list) and len(logged_q) == 14:
                q_mismatch_max = max(q_mismatch_max, float(np.max(np.abs(
                    sim.config.q[sim.qids] - np.asarray(logged_q, dtype=float)))))
            acceleration = np.rad2deg(np.abs(
                (sim.velocity[sim.dofs] - before_velocity) / sim.dt))
            maximum_speed_ratio = max(maximum_speed_ratio, float(np.max(np.abs(sim.velocity[sim.dofs]) / sim.caps)))
            maximum_speed = max(maximum_speed, float(np.max(np.rad2deg(np.abs(
                sim.velocity[sim.dofs])))))
            maximum_acceleration = max(maximum_acceleration, float(np.max(acceleration)))
            if (cycle.state in ('tracking', 'returning', 'blocked')
                    or row.get('tick_action') in ('tracking', 'tracking_braking', 'returning')):
                minimum_clearance = min(minimum_clearance, sim.clearance(sim.config.q))

    recorded_limits, invalid_motion_limits = _recorded_motion_limits(run)
    comparable = not invalid_motion_limits and all(
        np.allclose(recorded_limits[key], motion_limits[key], rtol=0.0, atol=1e-12)
        for key in ('velocity_rad_s', 'acceleration_rad_s2'))
    comparison = ('invalid_recorded_motion_limits' if invalid_motion_limits else
                  'same_motion_limits' if comparable else 'different_motion_limits')
    exact_match = (accepted_mismatches == 0 and state_mismatches == 0
                   and reason_mismatches == 0 and q_mismatch_max <= 5e-6)
    current_failures = []
    if invalid_motion_limits:
        current_failures.append('invalid_motion_limits_metadata')
    if accepted_mismatches:
        current_failures.append('input_acceptance_mismatch')
    if blocked_rows:
        current_failures.append('blocked_state_observed')
    if minimum_clearance < sim.clearance_m:
        current_failures.append('clearance_limit_exceeded')
    if maximum_speed_ratio > 1.0 + 1e-6:
        current_failures.append('output_speed_limit_exceeded')
    if maximum_acceleration > (math.degrees(JOINT_ACCELERATION_LIMIT_RAD_S2)
                               + ACCELERATION_NUMERICAL_TOLERANCE_DEG_S2):
        current_failures.append('output_acceleration_limit_exceeded')
    logged_flow, current_flow = flows['logged'], flows['current']
    if current_flow['tracking_starts'] < logged_flow['tracking_starts']:
        current_failures.append('recorded_tracking_or_reengage_not_observed')
    if any(current_flow['completed_returns'][reason] < count
           for reason, count in logged_flow['completed_returns'].items()):
        current_failures.append('recorded_return_completion_not_observed')
    if (logged_flow['previous_state'] in ('ready', 'tracking')
            and cycle.state not in ('ready', 'tracking')):
        current_failures.append('final_state_not_ready_or_tracking')
    current_passed = not current_failures

    return dict(state_rows=state_rows, input_rows=input_rows,
                accepted_mismatches=accepted_mismatches,
                state_mismatches=state_mismatches,
                reason_mismatches=reason_mismatches,
                maximum_logged_q_difference_rad=q_mismatch_max,
                minimum_sampled_clearance_mm=minimum_clearance * 1000.0,
                max_output_speed_deg_s=maximum_speed,
                max_output_acceleration_deg_s2=maximum_acceleration,
                validation_motion_limits=motion_limits,
                recorded_motion_limits=recorded_limits,
                comparison=comparison,
                exact_replay_passed=exact_match if comparable else None,
                current_validation=dict(
                    passed=current_passed, failures=current_failures,
                    blocked_rows=blocked_rows,
                    tracking_starts=current_flow['tracking_starts'],
                    completed_returns=dict(current_flow['completed_returns']),
                    expected_tracking_starts=logged_flow['tracking_starts'],
                    expected_completed_returns=dict(logged_flow['completed_returns'])),
                final_state=cycle.state, final_reason=cycle.reason,
                return_stage=sim.return_motion.stage,
                return_replans=sim.return_motion.replans,
                # A different profile can pass current validation without being
                # evidence that the original joint trajectory was reproduced.
                passed=(exact_match and current_passed) if comparable else None)

def markdown_report(report):
    tick = report.get('tracking_tick_ms') or {}
    output = report.get('output_fixed_dt') or {}
    operator = report.get('operator_summary') or {}
    limits = report.get('validation_motion_limits') or _recorded_motion_limits(None)[0]
    lines = [
        '# Bimanual session report', '',
        f"- Log: `{report['source_log']}`",
        f"- Final state: `{report.get('final_state')}` / `{report.get('final_reason')}`",
        f"- Tracking starts: {report.get('tracking_starts', 0)}; re-engages: {report.get('reengage_count', 0)}",
        f"- Returns completed: {operator.get('completed_returns', 0)}; pinch: {operator.get('pinch_returns', 0)}",
        f"- Near-hands recoveries: {operator.get('near_hands_recoveries', 0)}; separation sides: {operator.get('separation_sides', {})}",
        f"- Tracking tick p95/max: {tick.get('p95', float('nan')):.3f} / {tick.get('max', float('nan')):.3f} ms",
        f"- Fixed-dt max speed: {output.get('max_speed_deg_s', float('nan')):.3f} deg/s",
        f"- Fixed-dt max acceleration: {output.get('max_acceleration_deg_s2', float('nan')):.3f} deg/s^2",
        f"- Validation limit source: `{limits['source']}`; velocity caps: "
        f"{min(limits['velocity_rad_s']):.6g} to {max(limits['velocity_rad_s']):.6g} rad/s; "
        f"acceleration caps: {min(limits['acceleration_rad_s2']):.6g} to "
        f"{max(limits['acceleration_rad_s2']):.6g} rad/s^2",
        f"- Blocked rows: {report.get('blocked_rows', 0)}",
        f"- Warnings: {', '.join(report.get('warnings', [])) or 'none'}",
        f"- Failures: {', '.join(report.get('failures', [])) or 'none'}",
    ]
    if 'quest_cycle_check' in report:
        quest = report['quest_cycle_check']
        lines.extend(['', '## Quest cycle',
            f"- Passed: {quest['passed']}",
            f"- Failures: {', '.join(quest['failures']) or 'none'}"])
    if 'replay' in report:
        replay = report['replay']
        lines.extend(['', '## Replay',
            f"- Comparison: `{replay['comparison']}`",
            f"- Exact replay passed: {replay['exact_replay_passed'] if replay['exact_replay_passed'] is not None else 'not comparable'}",
            f"- Current validation passed: {replay['current_validation']['passed']}",
            f"- Current validation failures: {', '.join(replay['current_validation']['failures']) or 'none'}",
            f"- Validation limits: current code, shoulder/elbow 90 deg/s, wrist 180 deg/s and "
            f"{JOINT_ACCELERATION_LIMIT_RAD_S2:g} rad/s^2",
            f"- Max logged-q difference: {replay['maximum_logged_q_difference_rad']:.9g} rad",
            f"- Minimum sampled clearance: {replay['minimum_sampled_clearance_mm']:.6f} mm",
            f"- Max output speed: {replay['max_output_speed_deg_s']:.6f} deg/s",
            f"- Max output acceleration: {replay['max_output_acceleration_deg_s2']:.6f} deg/s^2"])
    return '\n'.join(lines) + '\n'

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', type=Path,
                        help='JSONL or .json.gz session; omit with --latest')
    parser.add_argument('--latest', action='store_true',
                        help='Use newest logs/test_results/bimanual/unity_*.jsonl')
    parser.add_argument('--replay', action='store_true',
                        help='Replay accepted input through the current validated simulator')
    parser.add_argument('--json-output', type=Path)
    parser.add_argument('--markdown-output', type=Path)
    parser.add_argument('--require-quest-cycle', action='store_true',
                        help='Require engage, pinch return, and a subsequent re-engage')
    parser.add_argument('--strict', action='store_true',
                        help='Nonzero exit for static/current validation failures or comparable replay mismatch')
    args = parser.parse_args(argv)
    if args.latest == (args.input is not None):
        parser.error('Specify exactly one input path or --latest')
    path = _latest_session() if args.latest else args.input.resolve()
    if not path.is_file():
        parser.error(f'Input session does not exist: {path}')

    report = analyze_session(path)
    if args.require_quest_cycle:
        quest_failures = _quest_cycle_failures(report)
        report['quest_cycle_check'] = dict(
            required=True, passed=not quest_failures, failures=quest_failures)
        for failure in quest_failures:
            if failure not in report['failures']:
                report['failures'].append(failure)
    if args.replay:
        report['replay'] = replay_session(path)
        if (not report['replay']['current_validation']['passed']
                or report['replay']['exact_replay_passed'] is False):
            report['failures'].append('replay_mismatch_or_safety_failure')
        if report['replay']['comparison'] == 'different_motion_limits':
            report['warnings'].append('replay_not_comparable_motion_limits')
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(payload, encoding='utf-8')
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(markdown_report(report), encoding='utf-8')
    print(payload, end='')
    return 1 if args.strict and report['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
