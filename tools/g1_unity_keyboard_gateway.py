"""Unity Game keyboard -> local combined input tap. No SDK, DDS or robot socket."""
import argparse
import json
import math
import os
from pathlib import Path
import socket
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g1_observation_tap import ObservationTap, next_deadline

UNITY_PORT = 55076
GATEWAY_PORT = 55077
TIMEOUT = 0.15
SCHEMA = 'g1.unity.keyboard.v1'


def velocity(packet, token, pending, now):
    if not isinstance(packet, dict) or packet.get('schema') != SCHEMA or packet.get('token') != token:
        raise ValueError('keyboard schema/token')
    seq = packet.get('request_sequence')
    if type(seq) is not int or seq not in pending or not 0 <= now - pending[seq] <= TIMEOUT:
        raise ValueError('keyboard expired/replayed request')
    if type(packet.get('focused')) is not bool:
        raise ValueError('keyboard focus')
    axes = [packet.get(name) for name in ('forward', 'left', 'turn_left')]
    if any(type(x) is not int or x not in (-1, 0, 1) for x in axes):
        raise ValueError('keyboard axes')
    # Consume this and older requests: reordered input cannot restore old motion.
    for old in list(pending):
        if old <= seq:
            del pending[old]
    if not packet['focused']:
        return (0.0, 0.0, 0.0)
    scale = max(1.0, math.hypot(*axes[:2]))
    return (0.2 * axes[0] / scale, 0.2 * axes[1] / scale, 0.2 * axes[2])


class OmniKeyboardAdapter:
    """Generate a virtual Omni angle; production heading receiver uses yaw-sign=-1.

    Advance the previous held input before replacing it. Never integrate across
    a stalled gateway tick or beyond the Unity input lease.
    """
    def __init__(self, now):
        self.last = now
        self.receipt = -math.inf
        self.command = (0.0, 0.0, 0.0)
        self.yaw_rad = 0.0

    def advance(self, now):
        dt = now - self.last
        if not math.isfinite(now) or dt < 0:
            raise ValueError('keyboard clock')
        if dt <= TIMEOUT:
            active_dt = max(0.0, min(now, self.receipt + TIMEOUT) - self.last)
            self.yaw_rad -= self.command[2] * active_dt
        self.last = now
        if now - self.receipt > TIMEOUT:
            self.command = (0.0, 0.0, 0.0)

    def accept(self, command, now):
        self.advance(now)
        self.command = command
        self.receipt = now

    def values(self, now):
        self.advance(now)
        return dict(input_mode='unity_keyboard', source_origin='unity_game_keyboard',
                    calibrated=True, arm_yaw_deg=math.degrees(self.yaw_rad),
                    vx=self.command[0], vy=self.command[1], yaw_rate=self.command[2])


def bound(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(('127.0.0.1', port))
        sock.setblocking(False)
        if hasattr(socket, 'SIO_UDP_CONNRESET'):
            sock.ioctl(socket.SIO_UDP_CONNRESET, False)
        return sock
    except BaseException:
        sock.close()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true', help='Print only; do not publish into teleop')
    args = parser.parse_args()
    # Reserve the same exclusive ownership port as the Omni gateway. Do not run both.
    with bound(55074), bound(GATEWAY_PORT) as sock:
        os.environ['G1_OBSERVATION_TAP'] = '0' if args.preview else '1'
        os.environ['G1_OMNI_UNITY_HEADING'] = '0'
        tap = ObservationTap('omni')  # Legacy base slot, explicitly tagged keyboard.
        token = uuid.uuid4().hex
        pending = {}
        sequence = 0
        deadline = time.monotonic()
        adapter = OmniKeyboardAdapter(deadline)
        last_display = None
        print('KEYBOARD: Unity Game W/S forward/back, A/D strafe, Q/E turn. '
              'Release/focus loss -> zero translation, hold target heading. 0.2 m/s, target turn 0.2 rad/s.', flush=True)
        print('PREVIEW ONLY' if args.preview else 'Local input tap enabled; no robot socket in this process.', flush=True)
        try:
            while True:
                now = time.monotonic()
                # Never wait for Unity. The input lease expires even if Play freezes.
                for _ in range(64):
                    try:
                        raw, peer = sock.recvfrom(2049)
                    except BlockingIOError:
                        break
                    if peer != ('127.0.0.1', UNITY_PORT) or len(raw) > 2048:
                        continue
                    try:
                        packet = json.loads(raw)
                        adapter.accept(velocity(packet, token, pending, now), now)
                    except (ValueError, TypeError, UnicodeError):
                        continue
                if now >= deadline:
                    values = adapter.values(now)
                    command = adapter.command
                    tap.publish(values, now)
                    if command != last_display:
                        print('[KEYBOARD] vx=%.3f vy=%.3f yaw_rate=%.3f' % command, flush=True)
                        last_display = command
                    pending = {seq: stamp for seq, stamp in pending.items() if now - stamp <= TIMEOUT}
                    pending[sequence] = now
                    sock.sendto(json.dumps(dict(schema=SCHEMA, token=token,
                        request_sequence=sequence)).encode(), ('127.0.0.1', UNITY_PORT))
                    sequence += 1
                    deadline, _ = next_deadline(deadline, now, 1 / 60)
                time.sleep(0.001)
        except KeyboardInterrupt:
            pass
        finally:
            now = time.monotonic()
            adapter.accept((0.0, 0.0, 0.0), now)
            tap.publish(adapter.values(now), now)
            tap.close()


if __name__ == '__main__':
    main()
