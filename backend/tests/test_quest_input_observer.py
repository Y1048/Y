"""Generated raw-input fixtures; these are not measured Quest or G1 data."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("observer", ROOT / "tools/quest_input_observer.py")
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
PEER = ("127.0.0.1", 42000)


def fixture():
    pose = {"position_m": [.1, .2, .3], "quaternion_xyzw": [0, 0, 0, 1]}
    hand = {"tracked": True, "high_confidence": True, "pinch": False}
    hand.update({key: copy.deepcopy(pose) for key in ("wrist", "index_base", "middle_base", "pinky_base")})
    return {"schema": observer.SCHEMA, "observation_only": True, "session_id": "a"*32,
            "clock_source": observer.CLOCK, "frame": observer.FRAME, "sequence": 0,
            "source_time_s": 1., "send_hz": 60, "focused": True, "head_tracked": True,
            "head": copy.deepcopy(pose), "left": hand, "right": copy.deepcopy(hand)}


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.recorder = observer.Recorder(self.output)
        self.discovery = json.dumps({"schema": "g1.quest.observation.discover.v1", "nonce": "b"*32}).encode()
        self.recorder.handle(self.discovery, PEER, 100.)

    def send(self, value):
        return self.recorder.handle(json.dumps(value).encode(), PEER, 101.)

    def test_roundtrip_original_raw_and_ack(self):
        raw = json.dumps(fixture(), indent=2).encode()
        ack = self.recorder.handle(raw, PEER, 101.5)
        record = json.loads(self.output.getvalue())
        self.assertEqual(record["raw_json_utf8"], raw.decode())
        self.assertEqual(record["sample"], fixture())
        self.assertEqual(record["pc_receive_monotonic_s"], 101.5)
        self.assertEqual(record["clock_alignment"], "not_established")
        self.assertEqual(ack["sequence"], 0)
        self.assertEqual(record["acceptance"], "PC_validated_recorded_only")

    def test_no_discovery_rejected(self):
        with self.assertRaisesRegex(ValueError, "discovery"):
            observer.Recorder(io.StringIO()).handle(json.dumps(fixture()).encode(), PEER, 1.)

    def test_discovery_echo_nonce(self):
        reply = self.recorder.handle(self.discovery, PEER, 100.)
        self.assertEqual(reply["nonce"], "b"*32)
        self.assertEqual(reply["schema"], "g1.quest.observation.offer.v1")

    def test_gap_detected(self):
        x = fixture(); self.send(x)
        x["sequence"] = 4; x["source_time_s"] = 1.1; self.send(x)
        self.assertEqual(json.loads(self.output.getvalue().splitlines()[1])["sequence_gap"], 3)

    def test_duplicate_and_reordered_rejected(self):
        x = fixture(); x["sequence"] = 3; self.send(x)
        for sequence in (3, 2):
            x["sequence"] = sequence; x["source_time_s"] = 2.
            with self.assertRaisesRegex(ValueError, "non-monotonic"): self.send(x)
        self.assertEqual(self.recorder.accepted, 1)

    def test_nonmonotonic_time_rejected(self):
        x = fixture(); self.send(x)
        x["sequence"] = 1
        with self.assertRaisesRegex(ValueError, "non-monotonic"): self.send(x)

    def test_new_session(self):
        x = fixture(); self.send(x); x["session_id"] = "c"*32; self.send(x)
        self.assertTrue(json.loads(self.output.getvalue().splitlines()[1])["session_first_sample"])

    def test_missing_fields_fail_closed(self):
        for field in ("schema", "observation_only", "frame", "clock_source", "session_id", "sequence", "source_time_s", "left", "right", "head", "head_tracked", "focused", "send_hz"):
            x = fixture(); del x[field]
            with self.subTest(field=field), self.assertRaises(ValueError): observer.validate(x)

    def test_nonfinite_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            x = fixture(); x["left"]["wrist"]["position_m"][0] = bad
            with self.assertRaises(ValueError): observer.validate(x)
            with self.assertRaises(ValueError): observer.strict_load(json.dumps(x).encode())
        with self.assertRaises(ValueError): observer.validate(observer.strict_load(json.dumps(fixture()).replace('1.0', '1e400').encode()))

    def test_boolean_is_not_number_or_sequence(self):
        for field in ("sequence", "source_time_s"):
            x = fixture(); x[field] = True
            with self.assertRaises(ValueError): observer.validate(x)

    def test_duplicate_json_keys(self):
        with self.assertRaises(ValueError): observer.strict_load(b'{"schema":1,"schema":2}')

    def test_pose_shape_norm_and_coordinate(self):
        x = fixture(); x["left"]["wrist"]["position_m"] = [0, 0]
        with self.assertRaises(ValueError): observer.validate(x)
        x = fixture(); x["head"]["quaternion_xyzw"] = [0, 0, 0, 0]
        with self.assertRaises(ValueError): observer.validate(x)
        x = fixture(); x["frame"] = "robot"
        with self.assertRaises(ValueError): observer.validate(x)

    def test_untracked_no_fake_pose_needed(self):
        x = fixture(); x["head_tracked"] = False; x["head"] = None
        for side in ("left", "right"):
            x[side] = {"tracked": False, "high_confidence": False, "pinch": False,
                       "wrist": None, "index_base": None, "middle_base": None, "pinky_base": None}
        observer.validate(x)
        x["left"]["pinch"] = True
        with self.assertRaises(ValueError): observer.validate(x)

    def test_observer_has_no_control_transport(self):
        source = (ROOT / "tools/quest_input_observer.py").read_text()
        self.assertNotIn("unitree_sdk", source)
        self.assertNotIn("ChannelPublisher", source)
        self.assertNotIn("LowCmd", source)
        self.assertEqual(source.count("sock.sendto("), 1)
        self.assertIn('sock.sendto(json.dumps(reply).encode("utf-8"), peer)', source)
        sender = (ROOT / "Unity_G1_VR/Assets/G1Teleop/G1QuestObservationSender.cs").read_text()
        self.assertIn("const int Port = 55100", sender)
        for forbidden in ("5005", "5008", "5014", "55070"):
            self.assertNotIn(forbidden, sender)

    def test_real_udp_loopback_generated_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "samples.jsonl"
            proc = subprocess.Popen([sys.executable, "-B", str(ROOT / "tools/quest_input_observer.py"), "--seconds", "2", "--output", str(output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                self.assertIn(b"OBSERVATION ONLY", proc.stdout.readline())
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                    client.settimeout(.3)
                    reply = None
                    for _ in range(10):
                        client.sendto(self.discovery, ("127.0.0.1", observer.PORT))
                        try: reply = json.loads(client.recvfrom(4096)[0]); break
                        except (socket.timeout, ConnectionResetError): pass
                    self.assertEqual(reply["schema"], "g1.quest.observation.offer.v1")
                    client.sendto(json.dumps(fixture()).encode(), ("127.0.0.1", observer.PORT))
                    self.assertEqual(json.loads(client.recvfrom(4096)[0])["schema"], "g1.quest.observation.ack.v1")
                stdout, stderr = proc.communicate(timeout=5)
                self.assertEqual(proc.returncode, 0, stderr.decode())
                self.assertEqual(json.loads(output.read_text())["sample"], fixture())
            finally:
                if proc.poll() is None: proc.kill()
                proc.communicate()


if __name__ == "__main__": unittest.main()
