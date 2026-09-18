"""Paired input protocol/state tests and a real loopback synthetic sender."""
import copy
import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
from g1_bimanual_unity_sim import UnityCycle, decode, BASIS, SCHEMA, mink


def packet(sequence=0, engage=False, session='test', tracked=True, returning=False):
    return dict(schema=SCHEMA, simulation_only=True, session=session, sequence=sequence,
        sender_time_s=sequence / 60, engage=engage, return_home=returning,
        left=dict(tracked=tracked, position_m=[-.22, -.24, .38], quaternion_wxyz=[1, 0, 0, 0]),
        right=dict(tracked=tracked, position_m=[.22, -.24, .38], quaternion_wxyz=[1, 0, 0, 0]))


class CycleTests(unittest.TestCase):
    def setUp(self):
        self.sim = Mock()
        self.sim.state = 'tracking'
        self.sim.home_targets = {s: mink.SE3.identity() for s in ('left', 'right')}
        self.cycle = UnityCycle(self.sim)

    def engage(self):
        self.cycle.receive(packet(), 0.)
        self.cycle.receive(packet(1, True), .02)
        self.assertEqual(self.cycle.state, 'tracking')

    def test_validation_nonfinite_missing_duplicates(self):
        self.assertEqual(decode(json.dumps(packet()).encode()), packet())
        for field, value in [('sequence', True), ('sender_time_s', float('nan')),
                             ('engage', 1), ('simulation_only', False)]:
            p = packet()
            p[field] = value
            with self.assertRaises(ValueError):
                decode(json.dumps(p).encode())
        p = packet()
        del p['right']
        with self.assertRaises(ValueError):
            decode(json.dumps(p).encode())
        with self.assertRaises(ValueError):
            decode(b'{"schema":1,"schema":2}')

    def test_startup_active_requires_inactive_edge(self):
        self.cycle.receive(packet(0, True), 0)
        self.assertEqual(self.cycle.state, 'ready')
        self.cycle.receive(packet(1, False), .02)
        self.cycle.receive(packet(2, True), .04)
        self.assertEqual(self.cycle.state, 'tracking')

    def test_mapping_same_frame_both_hands(self):
        self.engage()
        p = packet(2, True)
        delta = np.array([.01, .02, .03])
        rotation = mink.SO3.exp(np.array([.1, -.2, .3]))
        for side in ('left', 'right'):
            p[side]['position_m'] = (np.array(p[side]['position_m']) + delta).tolist()
            p[side]['quaternion_wxyz'] = rotation.wxyz.tolist()
        self.cycle.receive(p, .04)
        self.cycle.tick(.04)
        goals = self.sim.step.call_args.args[0]
        for goal in goals.values():
            np.testing.assert_allclose(goal.translation(), [.03, -.01, .02])
            np.testing.assert_allclose(goal.rotation().as_matrix(), BASIS @ rotation.as_matrix() @ BASIS.T)

    def test_pinch_return_ignores_early_engage_then_rearms(self):
        self.engage()
        self.cycle.receive(packet(2, True, returning=True), .04)
        self.assertEqual(self.cycle.state, 'returning')
        self.cycle.receive(packet(3, True), .06)
        self.cycle.tick(.06)
        self.sim.step.assert_called_with(returning=True)
        self.sim.state = 'ready'
        self.cycle.tick(.08)
        self.cycle.receive(packet(4, True), .09)
        self.assertEqual(self.cycle.state, 'ready')
        self.cycle.receive(packet(5), .1)
        self.cycle.receive(packet(6, True), .12)
        self.assertEqual(self.cycle.state, 'tracking')

    def test_tracking_grace_timeout_and_reordering(self):
        self.engage()
        self.assertFalse(self.cycle.receive(packet(1, True), .5))
        self.assertEqual(self.cycle.received, .02)
        self.cycle.receive(packet(2, True, tracked=False), .03)
        self.cycle.tick(.03)
        self.assertEqual(self.cycle.state, 'tracking')
        self.cycle.tick(.39)
        self.assertEqual(self.cycle.reason, 'tracking_lost')
        other = UnityCycle(self.sim)
        other.receive(packet(), 0)
        other.receive(packet(1, True), .01)
        other.tick(.77)
        self.assertEqual(other.reason, 'input_timeout')

    def test_session_change_returns_and_blocked_is_not_ready(self):
        self.engage()
        self.cycle.receive(packet(0, True, session='new'), .04)
        self.assertEqual(self.cycle.reason, 'session_changed')
        self.sim.state = 'blocked'
        self.sim.reason = 'swept_clearance'
        self.cycle.tick(.05)
        self.assertEqual(self.cycle.state, 'blocked')

    def test_real_loopback_synthetic_sender(self):
        with tempfile.TemporaryDirectory() as directory, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            # Ephemeral test listener port; no G1 address or SDK.
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.bind(('127.0.0.1', 0))
                port = probe.getsockname()[1]
            sender.bind(('127.0.0.1', 0))
            sender.settimeout(.1)
            output = Path(directory) / 'loopback.jsonl'
            process = subprocess.Popen([sys.executable, str(ROOT / 'MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py'),
                '--headless', '--seconds', '4', '--port', str(port), '--output', str(output)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                sequence = 0
                deadline = time.monotonic() + 8
                states = set()
                while process.poll() is None and time.monotonic() < deadline:
                    # Remain inactive until ready feedback, then calibrate stationary wrists.
                    p = packet(sequence, engage='ready' in states)
                    sender.sendto(json.dumps(p).encode(), ('127.0.0.1', port))
                    try:
                        raw, _ = sender.recvfrom(4096)
                        feedback = json.loads(raw)
                        states.add(feedback['state'])
                        self.assertEqual(len(feedback['q_rad']), 14)
                        self.assertEqual(feedback['joint_names'][0], 'left_shoulder_pitch_joint')
                        self.assertEqual(feedback['joint_names'][7], 'right_shoulder_pitch_joint')
                        self.assertTrue(np.isfinite(feedback['q_rad']).all())
                    except (socket.timeout, ConnectionResetError):
                        pass
                    sequence += 1
                    time.sleep(.015)
                out, err = process.communicate(timeout=3)
                self.assertEqual(process.returncode, 0, out + err)
                self.assertIn('tracking', states)
                rows = [json.loads(x) for x in output.read_text().splitlines()]
                self.assertTrue(any(r['kind'] == 'input' and r['accepted'] for r in rows))
                self.assertTrue(all(r['simulation_only'] for r in rows if r['kind'] == 'state'))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()


if __name__ == '__main__':
    unittest.main()
