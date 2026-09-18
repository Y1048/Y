"""Loopback-only Unity paired wrist input for the isolated kinematic simulator."""
import argparse
import json
import math
import socket
import time
from pathlib import Path

import numpy as np
import mink
from g1_bimanual_sim import BimanualSimulation

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
    x = json.loads(raw, object_pairs_hook=unique)
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


class UnityCycle:
    """Receipt freshness is local monotonic time, never a cross-host subtraction."""
    def __init__(self, sim):
        self.sim = sim
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
                self.origins = {s: (np.array(packet[s]['position_m']),
                    mink.SO3(np.array(packet[s]['quaternion_wxyz'])).as_matrix()) for s in ('left', 'right')}
                self.armed = False
                self.state = 'tracking'
                self.reason = ''
        return True

    def start_return(self, reason):
        self.state = 'returning'
        self.reason = reason
        self.armed = False
        self.loss_since = None

    def tick(self, now):
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
                    return  # Simulation pose hold during transient tracking loss.
            else:
                self.loss_since = None
                goals = {}
                for side in ('left', 'right'):
                    origin_p, origin_r = self.origins[side]
                    hand = self.packet[side]
                    home = self.sim.home_targets[side]
                    delta_r = mink.SO3(np.array(hand['quaternion_wxyz'])).as_matrix() @ origin_r.T
                    robot_r = BASIS @ delta_r @ BASIS.T @ home.rotation().as_matrix()
                    position = home.translation() + BASIS @ (np.array(hand['position_m']) - origin_p)
                    goals[side] = mink.SE3.from_rotation_and_translation(mink.SO3.from_matrix(robot_r), position)
                self.sim.step(goals)
        if self.state == 'returning':
            self.sim.step(returning=True)
            if self.sim.state == 'ready':
                self.state = 'ready'
                self.armed = False  # Require a new inactive packet, then engage.
        if self.sim.state == 'blocked':
            self.state = 'blocked'
            self.reason = self.sim.reason

    def feedback(self):
        return dict(schema='g1.bimanual.unity.sim.state.v1', simulation_only=True,
                    session=self.session, sequence=self.sequence, state=self.state, reason=self.reason)


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
    sim = BimanualSimulation()
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
            print(f'SIMULATION ONLY: Unity -> 127.0.0.1:{args.port}; no G1 output', flush=True)
            start = time.monotonic()
            peer = None
            previous_state = None
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
                cycle.tick(now)
                feedback = cycle.feedback()
                if peer:
                    try:
                        sock.sendto(json.dumps(feedback).encode(), peer)
                    except (ConnectionResetError, BlockingIOError):
                        pass
                log.write(json.dumps(dict(kind='state', monotonic_s=now,
                    **feedback, joint_names=sim.names, q_rad=sim.config.q[sim.qids].tolist()), allow_nan=False)+'\n')
                if cycle.state != previous_state:
                    print(f'[BIMANUAL SIM] {cycle.state}: {cycle.reason}', flush=True)
                    previous_state = cycle.state
                    log.flush()
                if viewer:
                    viewer.sync()
                time.sleep(max(0, sim.dt - (time.monotonic()-now)))
    except KeyboardInterrupt:
        print('Simulation closed; no hardware owner exists here.')
    finally:
        if viewer:
            viewer.close()


if __name__ == '__main__':
    main()
