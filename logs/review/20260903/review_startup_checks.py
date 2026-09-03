"""Isolated review probes. No SDK, sockets, viewer, or production file writes."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "hardware/g1_arm_bridge"))
sys.path.insert(0, str(ROOT / "MuJoCo_G1_Controller/scripts"))

import numpy as np
import mujoco
import check_startup_readiness as readiness
import diagnose_initial_pose_collision as diagnostics
import gate5_lowstate_safety_monitor as gate5
import simulate_startup_recovery as recovery
import live_lowstate_mujoco as mirror
import replay_startup_recovery as replay
from test_check_startup_readiness import _mode_query, _timed_packet


def EncodePacket(sequence, clock):
    packet = _timed_packet(sequence).telemetry
    return json.dumps(dict(
        schema=gate5.LOWSTATE_TELEMETRY_SCHEMA,
        mode=gate5.LOWSTATE_MODE, topic=gate5.LOWSTATE_TOPIC,
        publisher_present=False, command_output_enabled=False,
        bridge_session_id=packet.bridge_session_id, sequence=sequence,
        sent_at_unix_ns=clock.time_ns(), mode_pr=0, mode_machine=5,
        right_arm_q_rad=list(packet.measured_q_rad),
        right_arm_dq_rad_s=[0.0] * 7,
        all_joint_names=list(packet.all_joint_names),
        all_joint_q_rad=list(packet.all_joint_q_rad),
        all_joint_dq_rad_s=[0.0] * 29,
    )).encode()


def CheckReadinessStaleness():
    class Clock:
        now = 0.0
        def monotonic(self):
            return self.now
        def time_ns(self):
            return 1_800_000_000_000_000_000 + int(self.now * 1e9)

    clock = Clock()
    class FakeSocket:
        count = 0
        def bind(self, _address):
            pass
        def settimeout(self, _timeout):
            pass
        def close(self):
            pass
        def recvfrom(self, _size):
            if self.count < 20:
                self.count += 1
                clock.now += 0.01
                return EncodePacket(self.count, clock), ("127.0.0.1", 0)
            clock.now += 0.1
            raise gate5.socket.timeout()

    config = readiness.load_config(ROOT / "config/g1_startup_precheck.json")
    fake_socket = SimpleNamespace(socket=lambda *_args: FakeSocket(),
        AF_INET=0, SOCK_DGRAM=0, timeout=gate5.socket.timeout)
    with patch.object(readiness, "time", clock), patch.object(readiness, "socket", fake_socket):
        packets, invalid = readiness._collect_packets("unused", 1, config, 8.0)
    query = _mode_query()
    query["queried_at_unix_ns"] = clock.time_ns()
    decision, blockers, _ = readiness.evaluate_readiness(
        packets, invalid, query, config, {"minimum_distance_m": 0.027}, clock.time_ns())
    actual_age = (clock.time_ns() - packets[-1].telemetry.sent_at_unix_ns) / 1e9
    assert actual_age > config.maximum_packet_age_s
    assert decision == "DIRECT_TELEOP_READY"
    return dict(decision=decision, packets=len(packets),
        actual_latest_age_s=actual_age, recorded_latest_age_s=packets[-1].age_s,
        timeout_s=config.maximum_packet_age_s, blockers=[item.code for item in blockers])


def CheckCrossFieldConsistency():
    clock = SimpleNamespace(time_ns=lambda: 1_800_000_000_000_000_000)
    payload = json.loads(EncodePacket(1, clock))
    payload["all_joint_q_rad"][25] = 2.0
    payload["all_joint_dq_rad_s"][25] = 5.0
    packet = gate5.parse_lowstate_telemetry(json.dumps(payload).encode())
    assert packet.measured_q_rad[3] != packet.all_joint_q_rad[25]
    assert packet.measured_dq_rad_s[3] != packet.all_joint_dq_rad_s[25]
    return dict(accepted=True, right_elbow_q=packet.measured_q_rad[3],
        full_body_elbow_q=packet.all_joint_q_rad[25],
        right_elbow_dq=packet.measured_dq_rad_s[3],
        full_body_elbow_dq=packet.all_joint_dq_rad_s[25])


def CheckContactRegression():
    current = np.zeros(7)
    sampled_distances = []
    def SetPose(_model, _data, _controller, pose):
        current[:] = pose
    def Nearby(*_args):
        position = float(current[0])
        distance = 0.005 if position < 0.5e-5 else (-0.002 if position < 1.5e-5 else 0.015)
        sampled_distances.append(distance)
        return [dict(first_body="right_hand", second_body="pelvis", distance_m=distance)]
    samples = [np.array([value] + [0.0] * 6) for value in (0.0, 1e-5, 2e-5)]
    controller = SimpleNamespace(COLLISION_MIN_DISTANCE_M=0.012)
    with patch.object(diagnostics, "_joint_pose", side_effect=SetPose), patch.object(
        diagnostics, "_nearby_pairs", side_effect=Nearby):
        result = recovery._validate_profile(None, None, controller, [], samples,
            {tuple(sorted(("right_hand", "pelvis")))})
    assert result["passed"] is True
    assert min(sampled_distances) < 0.0
    return dict(validation=result, injected_clearances_m=[0.005, -0.002, 0.015],
        minimum_sampled_distance_m=min(sampled_distances),
        note="Injected geometry response tests the validator, not a physical G1 trajectory")


def CheckFullBodyReset():
    import run_mink_g1_right_arm_prototype as controller
    # Read an existing generated model. Do not call _prepare_mink_xml.
    model = mujoco.MjModel.from_xml_path(str(controller.g1.DEMO_XML))
    data = mujoco.MjData(model)
    names = ("waist_yaw_joint", "left_shoulder_pitch_joint", "right_hip_pitch_joint")
    addresses = [int(model.jnt_qposadr[controller._joint_id(model, name)]) for name in names]
    measured = [0.3, 0.4, -0.2]
    data.qpos[addresses] = measured
    diagnostics._joint_pose(model, data, controller, np.radians([10, -22, 0, 55, 0, 0, 0]))
    after = data.qpos[addresses].tolist()
    assert not np.allclose(after, measured)
    return dict(joints=names, injected_measured_q_rad=measured,
        q_after_collision_helper_rad=after,
        model=str(controller.g1.DEMO_XML.relative_to(ROOT)))


def CheckMirrorSessionAndAge():
    original = _timed_packet(100).telemetry
    old = replace(original, bridge_session_id="previous-session", sequence=900,
        sent_at_unix_ns=1)
    current = replace(original, bridge_session_id="current-session", sequence=10)
    stream = mirror.StreamState()
    outcomes = [stream.Accept(packet, float(index)) for index, packet in
        enumerate((old, current, old))]
    assert all(outcomes)
    return dict(accepted_old_current_old=outcomes, final_session=stream.session_id,
        final_timestamp_ns=stream.packet.sent_at_unix_ns,
        note="Receive-time freshness in Run does not check source timestamp")


def CheckReplayNanTimestamp():
    path = OUTPUT / "replay_nan_fixture.json"
    path.write_text(json.dumps(dict(passed=True, initial_q_rad=[0.0] * 7,
        trace=[dict(time_s=float("nan"), q_rad=[0.0] * 7, phase="teleop_ready")])) )
    _, times, poses, _ = replay.LoadRecovery(path)
    assert not np.all(np.isfinite(times))
    result = dict(loader_accepted_nonfinite_time=True)
    try:
        pose = replay.InterpolatePose(times, poses, 0.5)
        result["interpolated_pose_finite"] = bool(np.all(np.isfinite(pose)))
    except Exception as exc:
        result["interpolation_error"] = type(exc).__name__ + ": " + str(exc)
    return result


def Main():
    observations = dict(
        stale_readiness=CheckReadinessStaleness(),
        conflicting_lowstate=CheckCrossFieldConsistency(),
        contact_regression=CheckContactRegression(),
        full_body_reset=CheckFullBodyReset(),
        mirror_session_replay=CheckMirrorSessionAndAge(),
        replay_nan_timestamp=CheckReplayNanTimestamp(),
    )
    observations["unitree_sdk_imported"] = any(name.startswith("unitree_sdk") for name in sys.modules)
    assert observations["unitree_sdk_imported"] is False
    result = OUTPUT / "startup_review_checks.json"
    result.write_text(json.dumps(observations, indent=2), encoding="utf-8")
    print(json.dumps(observations, indent=2))
    print(f"Result saved to: {result}")


if __name__ == "__main__":
    Main()
