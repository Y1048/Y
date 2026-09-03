#!/usr/bin/env python3

from __future__ import annotations

import unittest
import json
import math
import tempfile
from dataclasses import replace
from pathlib import Path

from types import SimpleNamespace

from g1_right_arm_jog import (
    calculate_active_weight,
    create_joint_tracking_stats,
    dual_arm_target_errors_deg,
    finalize_joint_tracking_stats,
    full_authority_ready,
    load_config,
    load_path_permit,
    maximum_dual_arm_target_error,
    permitted_limits,
    step_candidate_tracking_error,
    update_joint_tracking_stats,
    validate_authorization,
    validate_snapshot_matches_precheck,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "g1_right_arm_jog.json"
FULL_AUTHORITY_CONFIG_PATH = (
    PROJECT_ROOT / "config" / "g1_right_shoulder_pitch_full_authority_trial.json"
)


class G1RightArmJogTests(unittest.TestCase):
    def test_launcher_polls_for_slow_mujoco_startup(self) -> None:
        launcher = (
            PROJECT_ROOT / "tools" / "START_G1_RIGHT_ARM_JOG_MUJOCO.bat"
        ).read_text(encoding="utf-8")
        self.assertIn("AddSeconds(15)", launcher)
        self.assertIn("Get-NetUDPEndpoint -LocalPort 5009", launcher)
        self.assertNotIn("timeout /t 4 /nobreak", launcher)

    def test_launcher_uses_single_key_operator_confirmation(self) -> None:
        launcher = (
            PROJECT_ROOT / "tools" / "START_G1_RIGHT_ARM_JOG_MUJOCO.bat"
        ).read_text(encoding="utf-8")
        self.assertIn("choice /C YN", launcher)
        self.assertNotIn("set /p \"CONFIRM_OUTPUT", launcher)
        self.assertNotIn("set /p \"CONFIRM_GROUND", launcher)
        self.assertNotIn("choice /C 1234567Q", launcher)
        self.assertNotIn("--joint %JOINT_NAME%", launcher)
        self.assertIn("--path-permit-json", launcher)
        self.assertIn("Use 1-7 to select", launcher)
        self.assertIn("--confirm ENABLE_G1_RIGHT_ARM_JOG", launcher)
        self.assertIn(
            "--confirm-grounded-regular G1_IS_GROUNDED_IN_REGULAR_MODE",
            launcher,
        )

    def test_locked_runtime_config_is_bounded(self) -> None:
        config = load_config(CONFIG_PATH)
        self.assertAlmostEqual(0.25, config.maximum_weight)
        self.assertLessEqual(config.maximum_active_duration_s, 30.0)
        self.assertAlmostEqual(15.0, config.joint_selection_timeout_s)
        self.assertAlmostEqual(180.0, config.precheck_max_age_s)
        self.assertAlmostEqual(-20.0, math.degrees(config.jog.minimum_offset_rad))
        self.assertAlmostEqual(20.0, math.degrees(config.jog.maximum_offset_rad))
        self.assertAlmostEqual(
            2.5,
            math.degrees(config.proximal_joint_maximum_velocity_rad_s),
        )
        self.assertAlmostEqual(
            5.0,
            math.degrees(config.wrist_joint_maximum_velocity_rad_s),
        )
        self.assertAlmostEqual(
            2.0,
            math.degrees(config.joint_step_tracking_tolerance_rad),
        )

    def test_full_authority_config_is_strictly_limited(self) -> None:
        config = load_config(FULL_AUTHORITY_CONFIG_PATH)
        self.assertEqual("full_authority_shoulder_pitch_trial", config.trial_mode)
        self.assertEqual(("right_shoulder_pitch",), config.allowed_joint_names)
        self.assertTrue(config.hold_unselected_start_pose)
        self.assertTrue(config.require_full_weight_before_jog)
        self.assertAlmostEqual(1.0, config.maximum_weight)
        self.assertAlmostEqual(
            1.5,
            math.degrees(config.arming_tracking_tolerance_rad),
        )
        self.assertGreaterEqual(config.ramp_up_s, 5.0)
        self.assertLessEqual(config.maximum_active_duration_s, 15.0)
        self.assertAlmostEqual(1.0, math.degrees(config.jog.maximum_offset_rad))
        self.assertAlmostEqual(-1.0, math.degrees(config.jog.minimum_offset_rad))

    def test_bounded_config_cannot_be_raised_to_weight_one(self) -> None:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        payload["maximum_weight"] = 1.0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not exceed 0.25"):
                load_config(path)

    def test_full_authority_config_cannot_enable_another_joint(self) -> None:
        payload = json.loads(
            FULL_AUTHORITY_CONFIG_PATH.read_text(encoding="utf-8")
        )
        payload["allowed_joint_names"] = ["right_elbow"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "shoulder pitch only"):
                load_config(path)

    def test_full_authority_launcher_uses_dedicated_config(self) -> None:
        launcher = (
            PROJECT_ROOT
            / "tools"
            / "START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat"
        ).read_text(encoding="utf-8")
        self.assertIn("g1_right_shoulder_pitch_full_authority_trial.json", launcher)
        self.assertIn("ENABLE_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL", launcher)
        self.assertIn("Press 1 once. Wait for [ARMED]", launcher)
        self.assertNotIn("ENABLE_G1_RIGHT_ARM_JOG --confirm", launcher)

    def test_joint_class_selects_proximal_or_wrist_velocity(self) -> None:
        config = load_config(CONFIG_PATH)
        permit = {
            name: (math.radians(-10.0), math.radians(10.0))
            for name in (
                "right_shoulder_pitch",
                "right_shoulder_roll",
                "right_shoulder_yaw",
                "right_elbow",
                "right_wrist_roll",
                "right_wrist_pitch",
                "right_wrist_yaw",
            )
        }
        shoulder = permitted_limits(config, permit, "right_shoulder_pitch")
        elbow = permitted_limits(config, permit, "right_elbow")
        wrist = permitted_limits(config, permit, "right_wrist_yaw")
        self.assertAlmostEqual(2.5, math.degrees(shoulder.maximum_velocity_rad_s))
        self.assertAlmostEqual(2.5, math.degrees(elbow.maximum_velocity_rad_s))
        self.assertAlmostEqual(5.0, math.degrees(wrist.maximum_velocity_rad_s))

    def test_step_candidate_reports_measured_tracking_lead(self) -> None:
        from right_arm_jog_contract import ArmJointJogController

        config = load_config(CONFIG_PATH)
        measured = [0.0] * 29
        controller = ArmJointJogController(
            measured,
            "right_shoulder_pitch",
            config.jog,
        )
        controller.request_step(1)
        candidate, error = step_candidate_tracking_error(
            controller,
            tuple(measured),
            1,
        )
        self.assertAlmostEqual(2.0, math.degrees(candidate))
        self.assertAlmostEqual(2.0, math.degrees(error))

    def test_weight_stays_zero_until_first_joint_selection(self) -> None:
        self.assertEqual(0.0, calculate_active_weight(None, 100.0, 0.25, 2.0))
        self.assertAlmostEqual(
            0.125,
            calculate_active_weight(100.0, 101.0, 0.25, 2.0),
        )
        self.assertAlmostEqual(
            0.25,
            calculate_active_weight(100.0, 103.0, 0.25, 2.0),
        )

    def test_full_authority_requires_weight_and_tracking_tolerance(self) -> None:
        tolerance = math.radians(1.0)
        self.assertFalse(full_authority_ready(0.99, 1.0, 0.0, tolerance))
        self.assertFalse(
            full_authority_ready(1.0, 1.0, math.radians(1.1), tolerance)
        )
        self.assertTrue(
            full_authority_ready(1.0, 1.0, math.radians(1.0), tolerance)
        )

    def test_maximum_dual_arm_target_error_checks_all_14_joints(self) -> None:
        frame = SimpleNamespace(motor_q_rad=[0.0] * 35)
        measured = [0.0] * 29
        frame.motor_q_rad[15] = math.radians(0.5)
        frame.motor_q_rad[28] = math.radians(-1.25)
        self.assertAlmostEqual(
            1.25,
            math.degrees(maximum_dual_arm_target_error(frame, tuple(measured))),
        )
        errors = dual_arm_target_errors_deg(frame, tuple(measured))
        self.assertAlmostEqual(0.5, errors["left_shoulder_pitch"])
        self.assertAlmostEqual(1.25, errors["right_wrist_yaw"])

    def test_joint_tracking_summary_records_excursions(self) -> None:
        from right_arm_jog_contract import ArmJointJogController

        config = load_config(CONFIG_PATH)
        measured = [0.0] * 29
        measured[22] = math.radians(10.0)
        controller = ArmJointJogController(
            measured,
            "right_shoulder_pitch",
            config.jog,
        )
        stats = create_joint_tracking_stats(controller, measured[22])
        tick = SimpleNamespace(
            requested_joint_rad=math.radians(12.0),
            commanded_joint_rad=math.radians(11.5),
            measured_joint_rad=math.radians(10.5),
        )
        update_joint_tracking_stats(stats, tick)
        summary = finalize_joint_tracking_stats(stats)
        self.assertAlmostEqual(2.0, summary["maximum_requested_excursion_deg"])
        self.assertAlmostEqual(1.5, summary["maximum_commanded_excursion_deg"])
        self.assertAlmostEqual(0.5, summary["maximum_measured_excursion_deg"])
        self.assertAlmostEqual(
            1.0,
            summary["maximum_command_measurement_error_deg"],
        )

    def test_path_permit_is_bound_to_exact_precheck(self) -> None:
        config = load_config(CONFIG_PATH)
        precheck = {
            "checked_at_unix_ns": 123,
            "latest_all_joint_q_rad": [0.0] * 29,
        }
        payload = {
            "schema": "g1.right_arm_jog.path_permit.v2",
            "passed": True,
            "publisher_present": False,
            "command_output_enabled": False,
            "precheck_checked_at_unix_ns": 123,
            "precheck_all_joint_q_rad": [0.0] * 29,
            "joints": {
                name: {
                    "minimum_offset_deg": -5.0,
                    "maximum_offset_deg": 7.0,
                }
                for name in (
                    "right_shoulder_pitch",
                    "right_shoulder_roll",
                    "right_shoulder_yaw",
                    "right_elbow",
                    "right_wrist_roll",
                    "right_wrist_pitch",
                    "right_wrist_yaw",
                )
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            permit_path = Path(directory) / "permit.json"
            permit_path.write_text(json.dumps(payload), encoding="utf-8")
            permit = load_path_permit(permit_path, precheck, config)
            self.assertAlmostEqual(math.radians(-5.0), permit["right_elbow"][0])
            self.assertAlmostEqual(math.radians(7.0), permit["right_elbow"][1])

            payload["precheck_checked_at_unix_ns"] = 124
            permit_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "different startup precheck"):
                load_path_permit(permit_path, precheck, config)

    def test_missing_runtime_enable_is_blocked(self) -> None:
        config = load_config(CONFIG_PATH)
        with self.assertRaises(PermissionError):
            validate_authorization(
                config,
                False,
                config.hardware_confirmation_phrase,
                config.grounded_regular_confirmation_phrase,
            )

    def test_wrong_confirmation_is_blocked(self) -> None:
        config = load_config(CONFIG_PATH)
        with self.assertRaises(PermissionError):
            validate_authorization(
                config,
                True,
                "WRONG",
                config.grounded_regular_confirmation_phrase,
            )

    def test_exact_runtime_confirmations_are_accepted(self) -> None:
        config = replace(
            load_config(CONFIG_PATH),
            hardware_output_authorized=True,
        )
        validate_authorization(
            config,
            True,
            config.hardware_confirmation_phrase,
            config.grounded_regular_confirmation_phrase,
        )

    def test_post_precheck_pose_change_is_blocked(self) -> None:
        snapshot = SimpleNamespace(all_q_rad=tuple([0.0] * 29))
        precheck = {"latest_all_joint_q_rad": [0.0] * 29}
        precheck["latest_all_joint_q_rad"][22] = 0.1
        with self.assertRaisesRegex(RuntimeError, "pose changed"):
            validate_snapshot_matches_precheck(
                snapshot,
                precheck,
                0.01,
            )

    def test_matching_post_precheck_pose_is_accepted(self) -> None:
        snapshot = SimpleNamespace(all_q_rad=tuple([0.0] * 29))
        precheck = {"latest_all_joint_q_rad": [0.0] * 29}
        delta = validate_snapshot_matches_precheck(snapshot, precheck, 0.01)
        self.assertEqual(0.0, delta)


if __name__ == "__main__":
    unittest.main(verbosity=2)
    full_authority_ready,
    maximum_dual_arm_target_error,
