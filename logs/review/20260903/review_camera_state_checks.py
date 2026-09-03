"""Review-only camera/saved-state probes; all real socket creation is blocked."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "hardware/g1_arm_bridge"))


def main():
    with (OUTPUT / "source_checks.csv").open(encoding="utf-8-sig") as stream:
        inventory = list(csv.DictReader(stream))
    observations = {}
    with patch("socket.socket", side_effect=AssertionError("network forbidden in review")):
        import g1_camera_replay_tcp as replay
        from g1_camera_tcp_bridge import FRAME_HEADER
        from g1_joint_contract import G1_29_JOINT_NAMES
        from g1_unity_state_bridge import BuildUnityHardwareStatePacket
        from gate5_lowstate_safety_monitor import parse_lowstate_telemetry
        from replay_saved_lowstate_mujoco import BuildPacket, LoadSnapshot

        fixture = OUTPUT / "saved_lowstate_review_fixture.json"
        fixture.write_text(json.dumps({
            "unity_packet_all_joint_names": list(G1_29_JOINT_NAMES),
            "unity_packet_all_joint_q_rad": [0.0] * 29,
        }), encoding="utf-8")
        snapshot = LoadSnapshot(fixture)
        packet = parse_lowstate_telemetry(BuildPacket(
            snapshot, session_id="saved-review", sequence=1))
        unity_packet = BuildUnityHardwareStatePacket(packet)
        assert snapshot.actual_full_body_capture is False
        assert unity_packet["state_source"] == "g1_lowstate_read_only"
        observations["saved_fallback_exported_as_hardware_source"] = {
            "snapshot_source_kind": snapshot.source_kind,
            "actual_full_body_capture": snapshot.actual_full_body_capture,
            "unity_state_source": unity_packet["state_source"],
            "unity_session_id": unity_packet["session_id"],
            "unity_timestamp": unity_packet["timestamp"],
            "boundary": "Python packet conversion only; no Unity execution or robot command",
        }

        class FakeConnection:
            def __init__(self):
                self.frames = []
                self.closed = False

            def sendall(self, payload):
                self.frames.append(payload)

            def close(self):
                self.closed = True

        args = argparse.Namespace(host="127.0.0.1", port=5011, fps=20.0,
                                  quality=40, duration=1.0, connect_timeout=1.0,
                                  reconnect_delay=1.0)
        connection = FakeConnection()
        result_values = []
        generator = replay.BuildReplayJpeg
        with patch.object(replay, "ParseArguments", return_value=args), \
                patch.object(replay, "ConnectUnity", return_value=connection), \
                patch.object(replay.signal, "signal"), \
                patch.object(replay.time, "monotonic", side_effect=[0.0, 0.0, 0.0, 0.0, 2.0]), \
                patch.object(replay, "BuildReplayJpeg", wraps=generator) as generate, \
                patch.object(replay, "WriteResult", side_effect=lambda value: (
                    result_values.append(value) or OUTPUT / "fake_result_no_file.json")), \
                redirect_stdout(io.StringIO()):
            return_code = replay.main()
        assert return_code == 0 and len(connection.frames) == 1 and connection.closed
        payload = connection.frames[0][FRAME_HEADER.size:]
        assert payload == generator(0, 0.0, quality=82)
        assert payload != generator(0, 0.0, quality=40)
        observations["camera_quality_ignored"] = {
            "requested_quality": args.quality,
            "generator_call_args": list(generate.call_args.args),
            "generator_call_kwargs": generate.call_args.kwargs,
            "matches_default_quality_82": True,
            "matches_requested_quality_40": False,
            "send_count": len(connection.frames),
            "connection_closed": connection.closed,
            "result_passed_without_unity": result_values[0]["passed"],
        }
        nan_fields = []
        for field in ("fps", "duration", "connect_timeout", "reconnect_delay"):
            invalid_args = argparse.Namespace(**vars(args))
            setattr(invalid_args, field, float("nan"))
            try:
                replay.ValidateArguments(invalid_args)
                nan_fields.append(field)
            except SystemExit:
                pass
        observations["camera_nan_arguments_accepted"] = nan_fields

        suite = unittest.defaultTestLoader.loadTestsFromNames([
            "test_g1_camera_replay_tcp", "test_g1_camera_tcp_bridge",
            "test_replay_saved_lowstate_mujoco", "test_g1_unity_state_bridge",
        ])
        with (OUTPUT / "camera_state_related_tests.log").open("w", encoding="utf-8") as stream:
            tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)

    changes = [row["path"] for row in inventory if hashlib.sha256(
        (ROOT / row["path"]).read_bytes()).hexdigest() != row["sha256"]]
    locks = []
    for path in sorted((ROOT / "config").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if "hardware_output_authorized" in value:
            locks.append({"path": path.relative_to(ROOT).as_posix(),
                          "locked": value["hardware_output_authorized"] is False})
    result = {"observations": observations, "tests_run": tests.testsRun,
              "tests_passed": tests.wasSuccessful(), "indexed_source_changes": changes,
              "hardware_locks": locks, "real_network_opened": False,
              "unity_or_viewer_started": False,
              "sdk_imported": any(name.startswith("unitree_sdk") for name in sys.modules)}
    (OUTPUT / "camera_state_review_checks.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return int(not tests.wasSuccessful() or bool(changes) or not all(v["locked"] for v in locks))


if __name__ == "__main__":
    raise SystemExit(main())
