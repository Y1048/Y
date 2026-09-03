"""Capture/replay review reproductions with fake transport and local fixtures only."""

import base64
import csv
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "hardware/g1_arm_bridge"))


def main():
    from arm_sdk_teleop_contract import load_gate7_config, load_regular_arm_pose, parse_mink_arm_sample
    from gate7_hardware_virtual_e2e import _packet
    from gate7_mink_replay import LoadCapture, NormalizePayload, CaptureSha256
    from gate7_capture_quality import _decode_capture, _raw_metrics
    from gate7_mink_wsl_relay import MinkOrderGuard, ValidateAndForward
    from gate7_live_arm_sdk import LoadLiveHardwareConfig, CreateHardwareTrajectoryController
    from gate7_live_dry_run import Gate7LiveDryRunSession

    with (OUTPUT / "source_checks.csv").open(encoding="utf-8-sig") as stream:
        inventory = list(csv.DictReader(stream))
    observations = {}
    regular = load_regular_arm_pose(ROOT / "config/g1_regular_arm_pose.json")
    config = load_gate7_config(ROOT / "config/g1_gate7_mink_arm_sdk.json")
    hardware = LoadLiveHardwareConfig(ROOT / "config/g1_gate7_live_hardware_output.json")
    assert not config.hardware_output_authorized and not hardware.hardware_output_authorized

    class FakeTransport:
        def __init__(self):
            self.packets = []

        def sendto(self, payload, endpoint):
            self.packets.append(payload)
            return len(payload)

    # Any unintended socket creation fails before a real endpoint can be opened.
    with patch("socket.socket", side_effect=AssertionError("network forbidden in capture review")):
        transport = FakeTransport()
        guard = MinkOrderGuard()
        source = json.loads(_packet(regular, 2))
        source["timestamp"] = 1.0
        source["input_packet_age_s"] = 99.0
        raw_payload = json.dumps(source).encode()
        controller = CreateHardwareTrajectoryController(
            regular, config, hardware,
            return_path_validator=lambda *_: (True, "review_stub_not_collision_validation"))
        session = Gate7LiveDryRunSession(
            regular, config, measured_source="lowstate", controller=controller,
            return_path_validator=lambda *_: (True, "review_stub_not_collision_validation"))
        states = []
        for index in range(3):
            normalized = NormalizePayload(raw_payload, session_id="replay-review", sequence=index)
            ValidateAndForward(normalized, guard, transport, ("fake-no-network", 5013))
            sample = parse_mink_arm_sample(transport.packets[-1])
            tick = session.Step(sample, regular.reference_all_joint_q_rad,
                                1.0 / config.command_hz, lowstate_age_s=0.0,
                                mode_pr=0, mode_machine=5)
            states.append({"state": tick.decision.state, "frame_present": tick.frame is not None})
        observations["replay_accepted_as_live_candidate"] = {
            "original_timestamp": 1.0, "original_age_s": 99.0,
            "normalized_age_s": sample.input_packet_age_s,
            "normalized_timestamp": sample.timestamp_s,
            "normalized_session": sample.session_id, "forwarded_packets": len(transport.packets),
            "states": states, "physical_publisher": False,
            "boundary": "Offline controller/frame construction; physical authorization and runtime checks not executed"}

        manifest = {"schema": "g1.mink.capture.manifest.v1", "capture_id": "file-A",
                    "hardware_output_authorized": False}
        records = [manifest]
        for index, sequence in enumerate((10, 9)):
            records.append({"schema": "g1.mink.capture.packet.v1", "capture_id": "file-B",
                            "index": index, "offset_s": index * 0.02,
                            "session_id": "metadata-unrelated", "sequence": 500 + index,
                            "input_command_mode": "idle",
                            "payload_base64": base64.b64encode(_packet(regular, sequence)).decode()})
        fixture = OUTPUT / "capture_metadata_mismatch.jsonl"
        fixture.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
        loaded_manifest, loaded = LoadCapture(fixture)
        quality_manifest, decoded = _decode_capture(fixture)
        observations["mismatched_capture_accepted"] = {
            "replay_count": len(loaded), "quality_count": len(decoded),
            "manifest_id": loaded_manifest["capture_id"], "record_ids": [r["capture_id"] for r in records[1:]],
            "payload_sequences": [parse_mink_arm_sample(p.payload).sequence for p in loaded],
            "metadata_sequences": [r["sequence"] for r in records[1:]],
            "quality_manifest": quality_manifest["capture_id"]}
        for record in records[1:]:
            record["offset_s"] *= 10.0
        retimed = OUTPUT / "capture_metadata_retimed.jsonl"
        retimed.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
        _, retimed_packets = LoadCapture(retimed)
        observations["payload_hash_ignores_timing"] = {
            "same_hash": CaptureSha256(loaded) == CaptureSha256(retimed_packets),
            "first_duration_s": loaded[-1].offset_s, "second_duration_s": retimed_packets[-1].offset_s}

        edge_cases = {}
        for name, offsets in (("one_packet", (0.0,)), ("same_time_only", (0.0, 0.0))):
            packets = []
            for index, offset in enumerate(offsets):
                payload = _packet(regular, index)
                packets.append({"offset_s": offset, "sample": parse_mink_arm_sample(payload),
                                "value": json.loads(payload)})
            try:
                _raw_metrics(packets, config.input_timeout_s)
                edge_cases[name] = "accepted"
            except Exception as error:
                edge_cases[name] = type(error).__name__ + ": " + str(error)
        observations["quality_zero_duration"] = edge_cases

        suite = unittest.defaultTestLoader.loadTestsFromNames([
            "test_gate7_capture_quality", "test_gate7_fault_injection_matrix"])
        with (OUTPUT / "capture_related_tests.log").open("w", encoding="utf-8") as stream:
            tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)

    changed = [row["path"] for row in inventory if hashlib.sha256(
        (ROOT / row["path"]).read_bytes()).hexdigest() != row["sha256"]]
    locks = []
    for path in sorted((ROOT / "config").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if "hardware_output_authorized" in value:
            locks.append({"path": path.relative_to(ROOT).as_posix(),
                          "locked": value["hardware_output_authorized"] is False})
    result = {"observations": observations, "tests_run": tests.testsRun,
              "tests_passed": tests.wasSuccessful(), "indexed_source_changes": changed,
              "hardware_locks": locks, "sdk_imported": any(
                  name.startswith("unitree_sdk") for name in sys.modules),
              "real_network_opened": False, "unity_or_viewer_started": False}
    (OUTPUT / "capture_review_checks.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return int(not tests.wasSuccessful() or bool(changed) or not all(item["locked"] for item in locks))


if __name__ == "__main__":
    raise SystemExit(main())
