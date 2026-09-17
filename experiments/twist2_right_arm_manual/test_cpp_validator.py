import json
import ast
import base64
import math
from pathlib import Path
import subprocess
import unittest
from test_vr_input_offline import MakePacket


def EncodePacket(packet):
    # Execute only the pure send helper with a fake socket, not the controller module.
    source = Path(__file__).resolve().parents[2] / 'MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py'
    tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_send_state')
    namespace = {'json': json, 'math': math}
    exec(compile(ast.Module(body=[helper], type_ignores=[]), str(source), 'exec'), namespace)
    class Socket:
        payload = None
        def sendto(self, payload, address):
            self.payload = payload
    socket = Socket()
    namespace['_send_state'](socket, packet, '127.0.0.1', 1)
    return socket.payload.decode()


class ValidatorTests(unittest.TestCase):
    def RunCase(self, events):
        executable = Path(__file__).resolve().parents[2] / 'logs/test_results/test_input_validator.exe'
        result = subprocess.run([str(executable)], input=''.join(json.dumps(e)+'\n' for e in events),
                                text=True, capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()

    def test_sequence_session_age_and_latch(self):
        for bad in [MakePacket(1), MakePacket(2, session_id='other'),
                    MakePacket(2, input_packet_age_s=0.26), b'{}', b'bad',
                    MakePacket(sequence=True),
                    MakePacket(2, input_command_mode='pinch_disengaged'),
                    MakePacket(2, all_joint_names=[]),
                    MakePacket(2, all_joint_q_rad=[0]*29)]:
            with self.subTest(bad=bad):
                self.assertEqual(self.RunCase([
                    {'now': 0, 'payload': MakePacket().decode()},
                    {'now': .02, 'payload': bad.decode()},
                    {'now': .03, 'payload': MakePacket(3).decode()}]), ['ok','stopped','stopped'])

    def test_valid_stream_and_timeout(self):
        self.assertEqual(self.RunCase([
            {'now': 0, 'payload': MakePacket().decode()},
            {'now': .02, 'payload': MakePacket(2).decode()},
            {'now': .28},
            {'now': .29, 'payload': MakePacket(3).decode()}]), ['ok','ok','stopped','stopped'])

    def test_idle_then_active_then_disengaged(self):
        idle = json.loads(MakePacket())
        idle.update(session_id=None, input_packet_age_s=None, input_command_mode='idle')
        idle['right_arm'].update(active=False, command_state='idle', minimum_clearance_m=None)
        self.assertEqual(self.RunCase([
            {'now': 0, 'payload': json.dumps(idle)},
            {'now': 2, 'payload': json.dumps(idle)},
            {'now': 2.01, 'payload': MakePacket().decode()},
            {'now': 2.02, 'payload': json.dumps(idle)},
            {'now': 2.03, 'payload': MakePacket(3).decode()}]),
            ['waiting', 'waiting', 'ok', 'stopped', 'stopped'])

    def test_unknown_diagnostic_and_invalid_control(self):
        packet = json.loads(MakePacket())
        packet['right_arm']['min_wrist_limit_margin_deg'] = math.inf
        encoded = EncodePacket(packet)
        value = json.loads(encoded)
        self.assertTrue(value['right_arm']['wrist_limit_margin_unknown'])
        self.assertEqual(value['right_arm']['min_wrist_limit_margin_deg'], 0)
        self.assertTrue(math.isinf(packet['right_arm']['min_wrist_limit_margin_deg']))
        self.assertEqual(self.RunCase([{'now': 0, 'payload': encoded}]), ['ok'])
        packet['right_arm']['min_wrist_limit_margin_deg'] = 12.5
        finite = json.loads(EncodePacket(packet))
        self.assertFalse(finite['right_arm']['wrist_limit_margin_unknown'])
        self.assertEqual(finite['right_arm']['min_wrist_limit_margin_deg'], 12.5)
        packet['all_joint_q_rad'][22] = math.inf
        with self.assertRaises(ValueError):
            EncodePacket(packet)

    def test_recorded_quest_packets(self):
        capture = Path(__file__).resolve().parents[2] / 'logs/test_results/twist2_vr_shadow_20260907_140851_282afca4/samples.jsonl'
        if not capture.exists():
            self.skipTest('Local Quest capture not present')
        events = []
        for line in capture.read_text().splitlines():
            row = json.loads(line)
            if row['payload_base64']:
                packet = json.loads(base64.b64decode(row['payload_base64']))
                events.append({'now': row['elapsed_s'], 'payload': EncodePacket(packet)})
        results = self.RunCase(events)
        self.assertGreaterEqual(results.count('ok'), 100)
        self.assertIn('waiting', results)
        self.assertEqual(results[-1], 'stopped')
        self.assertNotIn('stopped', results[:-1])
