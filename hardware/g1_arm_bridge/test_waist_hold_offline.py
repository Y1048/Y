"""Offline waist candidate contract checks; never constructs a publisher."""

import math
import json
import unittest
from dataclasses import asdict
from pathlib import Path
import pytest

from arm_sdk_hold_contract import ArmSdkCommandFrame, build_measured_hold_frame, validate_command_frame
from waist_hold_offline import AnalyzeEvents, BuildStudyFrame


class WaistHoldStudyTests(unittest.TestCase):
    def test_trial_draft_cannot_load_as_gate6_physical_config(self):
        from gate6_arm_sdk_hold import load_runtime_config
        root = Path(__file__).resolve().parents[2]
        path = root / "config/g1_waist_hold_trial_draft.json"
        draft = json.loads(path.read_text(encoding="utf-8"))
        self.assertIs(draft["hardware_output_authorized"], False)
        self.assertIsNone(draft["physical_runner"])
        self.assertEqual(draft["target_policy"]["fixed_indices"], list(range(12, 29)))
        for key in ("vr_input_enabled", "saved_pose_as_command_allowed",
                    "automatic_recalibration_allowed", "leg_command_changes_allowed"):
            self.assertIs(draft["target_policy"][key], False)
        self.assertTrue(all(value is None for value in draft["waist_parameters_pending_review"].values()))
        self.assertTrue(all(value is None for value in draft["stop_parameters_pending_review"].values()))
        with self.assertRaisesRegex(ValueError, "unsupported Gate 6 config schema"):
            load_runtime_config(path)
        self.assertIs(json.loads((root / "config/g1_gate6_hold.json").read_text())["hardware_output_authorized"], False)

    def test_only_three_waist_fields_change_and_target_does_not_follow_drift(self):
        initial = (0.01, 0.02, -0.04)
        target = (0.0,) * 14
        for mode in (0, 1):
            for weight in (0.0, 0.6, 0.8, 1.0, 0.4, 0.0):
                for drift in (-0.1, 0.0, 0.1):
                    measured = [0.0] * 29
                    measured[12:15] = [q + drift for q in initial]
                    baseline = asdict(build_measured_hold_frame(measured, target,
                        mode_pr=0, mode_machine=5, weight=weight))
                    result = BuildStudyFrame(measured, target, initial,
                        weight=weight, kp=60.0, kd=1.5, mode=mode)
                    self.assertFalse(result["hardware_authorized"])
                    fields = result["fields"]
                    self.assertEqual(fields["motor_q_rad"][12:15], list(initial))
                    for name, values in baseline.items():
                        if name.startswith("motor_"):
                            for j, value in enumerate(values):
                                if j in (12, 13, 14) and name in ("motor_q_rad", "motor_mode", "motor_kp", "motor_kd"):
                                    continue
                                self.assertEqual(fields[name][j], value)
                        else:
                            self.assertEqual(fields[name], values)
                    # Existing physical contract still rejects this unapproved candidate.
                    with self.assertRaises(ValueError):
                        validate_command_frame(ArmSdkCommandFrame(**fields))

    def test_invalid_study_inputs(self):
        for gain in (0, -1, math.nan, math.inf):
            with self.assertRaises(ValueError):
                BuildStudyFrame([0.0]*29, [0.0]*14, [0.0]*3,
                                weight=0.4, kp=gain, kd=1.5, mode=1)
        with self.assertRaises(ValueError):
            BuildStudyFrame([0.0]*29, [0.0]*14, [math.nan]*3,
                            weight=0.4, kp=60, kd=1.5, mode=1)

    def test_no_baseline_is_not_silently_recalibrated(self):
        with self.assertRaisesRegex(ValueError, "READY baseline"):
            AnalyzeEvents([], kp=60, kd=1.5, mode=1)

    def test_pd_algebra_is_not_claimed_as_physical_validation(self):
        q = [0.0]*29
        q[13] = 0.1
        dq = [0.0]*29
        dq[13] = 0.2
        rows = [{"details": {"schedule_phase": "READY", "measured_all_q_rad": [0.0]*29}},
                {"details": {"schedule_phase": "HOLD", "mode_pr": 0, "mode_machine": 5,
                 "measured_all_q_rad": q, "measured_all_dq_rad_s": dq,
                 "sampled_command": {"q_rad": q, "weight": 1.0, "waist_kp": [0.0]*3}}}]
        result = AnalyzeEvents(rows, kp=60, kd=1.5, mode=1)
        self.assertAlmostEqual(result["samples"][0]["unblended_pd_algebra_nm"][1], -6.3)
        self.assertFalse(result["hardware_authorized"])
        self.assertGreater(len(result["limitations"]), 0)


@pytest.mark.parametrize("axis", range(3), ids=("yaw", "roll", "pitch"))
@pytest.mark.parametrize("weight", (0.0, 0.4, 1.0))
@pytest.mark.parametrize("angle,velocity", (
    (0.05, 0.0), (-0.05, 0.0),
    (0.0, 0.1), (0.0, -0.1),
    (0.05, -0.1), (-0.05, 0.1), (0.0, 0.0),
), ids=("positive_error", "negative_error", "positive_speed", "negative_speed",
        "returning_negative", "returning_positive", "stationary"))
def test_each_axis_pd_direction_without_cross_axis_terms(axis, weight, angle, velocity):
    initial = [0.0]*29
    initial[12:15] = [0.02, -0.03, 0.04]
    measured = initial.copy()
    measured[12 + axis] += angle
    dq = [0.0]*29
    dq[12 + axis] = velocity
    rows = [{"details": {"schedule_phase": "READY", "measured_all_q_rad": initial}},
            {"details": {"schedule_phase": "HOLD", "mode_pr": 0, "mode_machine": 5,
             "measured_all_q_rad": measured, "measured_all_dq_rad_s": dq,
             "sampled_command": {"q_rad": measured, "weight": weight, "waist_kp": [0.0]*3}}}]
    result = AnalyzeEvents(rows, kp=60, kd=1.5, mode=1)
    sample = result["samples"][0]
    terms = sample["unblended_pd_algebra_nm"]
    assert terms[axis] == pytest.approx(-60*angle - 1.5*velocity)
    assert all(terms[index] == 0 for index in range(3) if index != axis)
    if velocity == 0 and angle != 0:
        assert terms[axis]*angle < 0
    if angle == 0 and velocity != 0:
        assert terms[axis]*velocity < 0
    assert sample["candidate_fixed_waist_q_rad"] == initial[12:15]
    assert result["maximum_abs_unblended_pd_algebra_nm"] == pytest.approx([abs(t) for t in terms])
    # Even weight=0 retains this UNBLENDED algebra; it is not applied motor torque.
    assert sample["weight"] == weight
    assert result["hardware_authorized"] is False
    assert result["publisher_created"] is False


if __name__ == "__main__":
    unittest.main()
