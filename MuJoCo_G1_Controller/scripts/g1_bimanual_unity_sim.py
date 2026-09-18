"""Loopback-only Unity paired wrist input for the isolated kinematic simulator."""
import argparse
import json
import math
import socket
import time
import uuid
from pathlib import Path

import numpy as np
import mink
from g1_bimanual_sim import BimanualSimulation
from g1_bimanual_runtime import runtime_metadata, startup_stage

SCHEMA = 'g1.bimanual.unity.sim.v1'
BASIS = np.array([[0., 0., 1.], [-1., 0., 0.], [0., 1., 0.]])


def decode(raw):
    if len(raw) > 8192:
        raise ValueError('packet_size')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_key')
            result[key] = value
        return result
    # Bound work before JSON constructs large integers or deep containers.
    text = raw.decode('utf-8') if isinstance(raw, (bytes, bytearray)) else raw
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            if depth > 8:
                raise ValueError('json_depth')
        elif char in ']}':
            depth -= 1
    def integer(value):
        if len(value.lstrip('-')) > 18:
            raise ValueError('integer_range')
        return int(value)
    def floating(value):
        if len(value) > 64:
            raise ValueError('number_length')
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('nonfinite_number')
        return result
    def constant(value):
        raise ValueError('nonfinite_number')
    try:
        x = json.loads(text, object_pairs_hook=unique, parse_int=integer,
                       parse_float=floating, parse_constant=constant)
    except (RecursionError, OverflowError) as error:
        raise ValueError('json_numeric_or_depth') from error
    if not isinstance(x, dict) or x.get('schema') != SCHEMA or x.get('simulation_only') is not True:
        raise ValueError('provenance')
    if not isinstance(x.get('session'), str) or not 1 <= len(x['session']) <= 64:
        raise ValueError('session')
    if type(x.get('sequence')) is not int or not 0 <= x['sequence'] <= 2**53:
        raise ValueError('sequence')
    if type(x.get('sender_time_s')) not in (int, float) or not math.isfinite(x['sender_time_s']) or x['sender_time_s'] < 0:
        raise ValueError('sender_time')
    for field in ('engage', 'return_home'):
        if type(x.get(field)) is not bool:
            raise ValueError(field)
    for side in ('left', 'right'):
        hand = x.get(side)
        if not isinstance(hand, dict) or type(hand.get('tracked')) is not bool:
            raise ValueError('hand')
        for key, length in (('position_m', 3), ('quaternion_wxyz', 4)):
            values = hand.get(key)
            if not isinstance(values, list) or len(values) != length or any(
                    type(v) not in (int, float) or not math.isfinite(v) for v in values):
                raise ValueError(key)
        if abs(np.linalg.norm(hand['quaternion_wxyz']) - 1) > 1e-4:
            raise ValueError('quaternion')
        if np.max(np.abs(hand['position_m'])) > 10:
            raise ValueError('position')
    return x


class PairedHandFilter:
    """Calibrated per-hand pose filtering; never turns invalid input into tracking.

    The old right-arm sender used 60ms position / 50ms rotation constants.
    Here filtering lives in Python so both arms share tested reset behavior;
    Unity raw input and validity bits remain unchanged in the input log.
    """
    position_tau_s = .060
    rotation_tau_s = .050

    def __init__(self):
        self.hands = None
        self.sender_time = None

    def reset(self, packet):
        self.hands = {side: dict(position_m=np.array(packet[side]['position_m'], dtype=float),
            quaternion_wxyz=np.array(packet[side]['quaternion_wxyz'], dtype=float))
            for side in ('left', 'right')}
        for hand in self.hands.values():
            hand['quaternion_wxyz'] /= np.linalg.norm(hand['quaternion_wxyz'])
        self.sender_time = packet['sender_time_s']

    def update(self, packet):
        if self.hands is None:
            self.reset(packet)
            return
        dt = packet['sender_time_s']-self.sender_time
        if dt <= 0:
            return
        self.sender_time = packet['sender_time_s']
        if not all(packet[side]['tracked'] for side in ('left', 'right')):
            return
        # A tracking/packet gap must not bypass smoothing with alpha almost 1.
        dt = min(dt, .10)
        position_alpha = -math.expm1(-dt/self.position_tau_s)
        rotation_alpha = -math.expm1(-dt/self.rotation_tau_s)
        for side, filtered in self.hands.items():
            hand = packet[side]
            filtered['position_m'] += position_alpha*(np.asarray(hand['position_m'])-filtered['position_m'])
            previous = mink.SO3(filtered['quaternion_wxyz'])
            raw_q = np.asarray(hand['quaternion_wxyz'], dtype=float)
            desired = mink.SO3(raw_q/np.linalg.norm(raw_q))
            filtered['quaternion_wxyz'] = (previous @ mink.SO3.exp(
                rotation_alpha*(previous.inverse() @ desired).log())).wxyz.copy()


class UnityCycle:
    """Receipt freshness is local monotonic time, never a cross-host subtraction."""
    def __init__(self, sim):
        self.sim = sim
        self.backend_id = uuid.uuid4().hex
        # Ordering only among Python processes on this loopback host. Never
        # subtract from Unity's clock or use it as cross-host input freshness.
        self.backend_started_ns = time.perf_counter_ns()
        self.feedback_sequence = 0
        self.state = 'ready'
        self.session = None
        self.sequence = -1
        self.sender_time = -1.
        self.received = None
        self.packet = None
        self.armed = False
        self.origins = None
        self.loss_since = None
        self.reason = ''
        self.pose_filter = PairedHandFilter()
        self.last_tick_action = 'idle'
        self.checked_braking_applied = False

    def receive(self, packet, now):
        if packet['session'] != self.session:
            if self.state == 'tracking':
                self.start_return('session_changed')
            self.session = packet['session']
            self.sequence = -1
            self.sender_time = -1.
            self.armed = False
        if packet['sequence'] <= self.sequence or packet['sender_time_s'] <= self.sender_time:
            return False
        self.sequence = packet['sequence']
        self.sender_time = packet['sender_time_s']
        self.received = now
        self.packet = packet
        if packet['return_home'] and self.state == 'tracking':
            self.start_return('pinch')
        if self.state == 'ready':
            if not packet['engage']:
                self.armed = True
            elif self.armed and not packet['return_home'] and all(packet[s]['tracked'] for s in ('left', 'right')):
                self.pose_filter.reset(packet)
                self.origins = {s: (hand['position_m'].copy(),
                    mink.SO3(hand['quaternion_wxyz']).as_matrix())
                    for s, hand in self.pose_filter.hands.items()}
                self.armed = False
                self.state = 'tracking'
                self.reason = ''
        if self.state == 'tracking':
            self.pose_filter.update(packet)
        return True

    def start_return(self, reason):
        self.state = 'returning'
        self.reason = reason
        self.armed = False
        self.loss_since = None

    def tick(self, now):
        self.last_tick_action = 'idle'
        self.checked_braking_applied = False
        braking_before = getattr(self.sim, 'braking_steps', 0)
        if self.state == 'tracking':
            if self.received is None or now - self.received > .75:
                self.start_return('input_timeout')
            elif not self.packet['engage']:
                self.start_return('disengaged')
            elif not all(self.packet[s]['tracked'] for s in ('left', 'right')):
                if self.loss_since is None:
                    self.loss_since = now
                if now - self.loss_since >= .35:
                    self.start_return('tracking_lost')
                else:
                    self.last_tick_action = 'tracking_braking'
                    self.sim.brake('tracking_unavailable')
            else:
                self.loss_since = None
                goals = {}
                for side in ('left', 'right'):
                    origin_p, origin_r = self.origins[side]
                    hand = self.pose_filter.hands[side]
                    home = self.sim.home_targets[side]
                    delta_r = mink.SO3(np.array(hand['quaternion_wxyz'])).as_matrix() @ origin_r.T
                    robot_r = BASIS @ delta_r @ BASIS.T @ home.rotation().as_matrix()
                    position = home.translation() + BASIS @ (np.array(hand['position_m']) - origin_p)
                    goals[side] = mink.SE3.from_rotation_and_translation(mink.SO3.from_matrix(robot_r), position)
                self.last_tick_action = 'tracking'
                self.sim.step(goals)
        if self.state == 'returning':
            self.last_tick_action = 'returning'
            self.sim.step(returning=True)
            if self.sim.state == 'ready':
                self.state = 'ready'
                self.armed = False  # Require a new inactive packet, then engage.
        if isinstance(self.sim, BimanualSimulation):
            self.checked_braking_applied = self.sim.braking_steps > braking_before
        if self.sim.state == 'blocked':
            self.state = 'blocked'
            self.reason = self.sim.reason

    def diagnostics(self, now):
        result = dict(tick_action=self.last_tick_action,
            input_age_s=None if self.received is None else max(0., now-self.received),
            checked_braking_applied=self.checked_braking_applied)
        if isinstance(self.sim, BimanualSimulation):
            result.update(ik_state=self.sim.state, ik_reason=self.sim.reason,
                braking_steps_total=self.sim.braking_steps,
                solver_error=self.sim.last_solver_error,
                return_motion=self.sim.return_motion.diagnostics(),
                checked_tail_steps_remaining=len(self.sim.brake_plan),
                motion={s:p.diagnostics() for s,p in self.sim.motion.items()}
                    if self.last_tick_action == 'tracking' else None)
        return result

    def feedback(self):
        result = dict(schema='g1.bimanual.unity.sim.state.v1', simulation_only=True,
                    backend_id=self.backend_id, backend_started_ns=self.backend_started_ns,
                    feedback_sequence=self.feedback_sequence,
                    session=self.session, sequence=self.sequence, state=self.state, reason=self.reason)
        self.feedback_sequence += 1
        if isinstance(self.sim, BimanualSimulation):
            result.update(joint_names=self.sim.names,
                          q_rad=self.sim.config.q[self.sim.qids].tolist())
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5020)
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--seconds', type=float, default=0, help='0: until viewer closes/Ctrl+C')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or not math.isfinite(args.seconds) or args.seconds < 0:
        parser.error('Invalid port/duration')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    startup_stage('model_begin')
    sim = BimanualSimulation()
    startup_stage('model_ready')
    cycle = UnityCycle(sim)
    viewer = None
    if not args.headless:
        import mujoco.viewer
        viewer = mujoco.viewer.launch_passive(sim.model, sim.config.data)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock, args.output.open('x', encoding='utf-8') as log:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind(('127.0.0.1', args.port))
            sock.setblocking(False)
            if hasattr(socket, 'SIO_UDP_CONNRESET'):
                sock.ioctl(socket.SIO_UDP_CONNRESET, False)
            log.write(json.dumps(dict(kind='run', simulation_dt_s=sim.dt,
                motion_policy='bimanual_motion_v1', boundary_policy='bimanual_boundary_v1',
                return_policy=sim.return_motion.policy,
                return_profile=dict(waypoint_rad=sim.return_motion.waypoint.tolist(),
                    velocity_rad_s=sim.caps.tolist(),
                    acceleration_rad_s2=sim.return_motion.acceleration_limits.tolist(),
                    jerk_rad_s3=sim.return_motion.jerk_limits.tolist(),
                    settle_s=sim.return_motion.settle_s),
                backend_id=cycle.backend_id, backend_started_ns=cycle.backend_started_ns,
                input_filter_time_constants_s=[.060, .050],
                **runtime_metadata('unity_loopback')), allow_nan=False)+'\n')
            log.flush()
            startup_stage('listener_ready')
            print(f'SIMULATION ONLY: Unity -> 127.0.0.1:{args.port}; no G1 output', flush=True)
            start = time.monotonic()
            peer = None
            previous_state = None
            previous_tick = None
            first_feedback = True
            while not viewer or viewer.is_running():
                now = time.monotonic()
                if args.seconds and now - start >= args.seconds:
                    break
                for _ in range(64):
                    try:
                        raw, address = sock.recvfrom(8193)
                    except (BlockingIOError, ConnectionResetError):
                        break
                    try:
                        packet = decode(raw)
                        # One Unity socket owns a running cycle. A different
                        # source may acquire only after ready + timeout.
                        if peer is not None and address != peer and not (
                                cycle.state == 'ready' and (cycle.received is None or now-cycle.received > .75)):
                            raise ValueError('source_busy')
                        accepted = cycle.receive(packet, now)
                        if accepted:
                            peer = address
                        log.write(json.dumps(dict(kind='input', receive_monotonic_s=now,
                            accepted=accepted, raw_json_text=raw.decode('utf-8')), allow_nan=False)+'\n')
                    except (ValueError, KeyError, TypeError, UnicodeError) as error:
                        log.write(json.dumps(dict(kind='reject', receive_monotonic_s=now, reason=str(error)))+'\n')
                tick_started = time.perf_counter()
                cycle.tick(now)
                control_tick_ms = (time.perf_counter()-tick_started)*1000
                feedback = cycle.feedback()
                if peer:
                    try:
                        sock.sendto(json.dumps(feedback).encode(), peer)
                        if first_feedback:
                            startup_stage('first_feedback')
                            first_feedback = False
                    except (ConnectionResetError, BlockingIOError):
                        pass
                log.write(json.dumps(dict(kind='state', monotonic_s=now,
                    control_tick_ms=control_tick_ms,
                    loop_period_ms=None if previous_tick is None else (now-previous_tick)*1000,
                    **feedback, **cycle.diagnostics(now)), allow_nan=False)+'\n')
                previous_tick = now
                if cycle.state != previous_state:
                    print(f'[BIMANUAL SIM] {cycle.state}: {cycle.reason}', flush=True)
                    previous_state = cycle.state
                    log.flush()
                if viewer:
                    viewer.sync()
                time.sleep(max(0, sim.dt - (time.monotonic()-now)))
            log.write(json.dumps(dict(kind='shutdown', simulation_only=True,
                backend_id=cycle.backend_id, state=cycle.state))+'\n')
            log.flush()
            startup_stage('normal_exit')
    except KeyboardInterrupt:
        print('Simulation closed; no hardware owner exists here.')
    finally:
        if viewer:
            viewer.close()


if __name__ == '__main__':
    main()
