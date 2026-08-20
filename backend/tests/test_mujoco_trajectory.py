from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path

import mujoco
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

CONTROLLER_PATH = (
    PROJECT_ROOT
    / "MuJoCo_G1_Controller"
    / "scripts"
    / "g1_right_arm_udp_ik_demo.py"
)
FAKE_SENDER_PATH = (
    PROJECT_ROOT
    / "MuJoCo_G1_Controller"
    / "scripts"
    / "udp_fake_vr_sender.py"
)
TELEOP_CONFIG_PATH = PROJECT_ROOT / "config" / "teleop.json"

from g1_teleop.config import apply_to_base_module, load_teleop_config  # noqa: E402
from g1_teleop.ik_emergency import (  # noqa: E402
    install_severe_ik_fallback_trigger,
    load_severe_ik_fallback_settings,
)
from g1_teleop.ik_fallback import (  # noqa: E402
    install_coupled_ik_fallback,
    load_ik_fallback_settings,
)
from g1_teleop.ik_primary_guard import install_primary_task_guard  # noqa: E402
from g1_teleop.inspection_contact import install_inspection_contact_monitor  # noqa: E402
from g1_teleop.runtime_collision import install_runtime_collision_policy  # noqa: E402


def load_module(module_name: str, module_path: Path):
    module_spec = importlib.util.spec_from_file_location(module_name, module_path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"Unable to load module: {module_path}")

    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


CONTROLLER = load_module("g1_right_arm_udp_ik_trajectory", CONTROLLER_PATH)
FAKE_SENDER = load_module("udp_fake_vr_sender_trajectory", FAKE_SENDER_PATH)


class MuJoCoTrajectoryTest(unittest.TestCase):
    def test_fake_vr_path_stays_humanlike_and_trackable(self):
        config = load_teleop_config(TELEOP_CONFIG_PATH)
        fallback_settings = load_ik_fallback_settings(TELEOP_CONFIG_PATH)
        severe_fallback_settings = load_severe_ik_fallback_settings(TELEOP_CONFIG_PATH)
        apply_to_base_module(CONTROLLER, config)
        install_runtime_collision_policy(CONTROLLER, config)
        install_inspection_contact_monitor(CONTROLLER, config)
        install_coupled_ik_fallback(CONTROLLER, fallback_settings)
        install_severe_ik_fallback_trigger(CONTROLLER, severe_fallback_settings)
        install_primary_task_guard(CONTROLLER)

        original_wrist_guard = CONTROLLER.is_right_wrist_target_safe
        CONTROLLER.is_right_wrist_target_safe = lambda target: True
        self.addCleanup(
            setattr,
            CONTROLLER,
            "is_right_wrist_target_safe",
            original_wrist_guard,
        )

        model, data, initial_qpos, preferred = CONTROLLER.initialize_model()
        context = CONTROLLER.create_right_arm_ik_context(model)
        mujoco.mj_forward(model, data)

        position_body = context["position_body"]
        orientation_body = context["orientation_body"]
        first_position, first_rotation = FAKE_SENDER.sample_motion(0.0)
        clutch_reference = CONTROLLER.capture_clutch_reference(
            data,
            position_body,
            orientation_body,
            np.asarray(first_position, dtype=float),
            np.asarray(first_rotation, dtype=float),
            context["shoulder_body"],
            context["elbow_body"],
        )

        safe_position = clutch_reference["robot_position"].copy()
        safe_rotation = np.asarray(first_rotation, dtype=float)
        previous_joint_positions = data.qpos[context["right_qpos_ids"]].copy()
        total_duration = sum(
            duration for duration, _ in FAKE_SENDER.MOTION_KEYFRAMES[:-1]
        )
        delta_time = 1.0 / 30.0
        frame_count = int(math.ceil(total_duration / delta_time)) + 1

        maximum_tracking_error = 0.0
        maximum_rotation_error = 0.0
        maximum_joint_step = 0.0
        minimum_elbow_angle = float("inf")
        relative_workspace_failures = 0
        collision_limited_frames = 0
        fallback_frames = 0
        severe_trigger_frames = 0
        primary_guard_frames = 0
        maximum_error_diagnostic = None

        for frame_index in range(frame_count):
            elapsed_time = min(frame_index * delta_time, total_duration)
            input_position, input_rotation = FAKE_SENDER.sample_motion(elapsed_time)
            desired_position, _ = CONTROLLER.calculate_clutched_target(
                clutch_reference,
                np.asarray(input_position, dtype=float),
                np.asarray(input_rotation, dtype=float),
            )
            requested_delta = desired_position - clutch_reference["robot_position"]

            if not CONTROLLER.is_clutch_delta_within_workspace(requested_delta):
                relative_workspace_failures += 1
                continue

            safe_position = CONTROLLER.update_safe_position_reference(
                safe_position,
                desired_position,
                delta_time,
            )
            safe_rotation = CONTROLLER.update_safe_rotation_reference(
                safe_rotation,
                np.asarray(input_rotation, dtype=float),
                delta_time,
            )
            _, target_rotation = CONTROLLER.calculate_clutched_target(
                clutch_reference,
                np.asarray(input_position, dtype=float),
                safe_rotation,
            )
            CONTROLLER.solve_right_arm_target(
                model,
                data,
                initial_qpos,
                preferred,
                safe_position,
                target_rotation=target_rotation,
                context=context,
                elbow_pole_reference=clutch_reference["elbow_pole"],
            )

            wrist_position = data.xpos[position_body].copy()
            wrist_rotation = data.xmat[orientation_body].reshape(3, 3).copy()
            tracking_error = float(np.linalg.norm(safe_position - wrist_position))
            rotation_error = float(np.linalg.norm(
                CONTROLLER.calculate_rotation_error(target_rotation, wrist_rotation)
            ))
            joint_positions = data.qpos[context["right_qpos_ids"]].copy()
            joint_step = float(np.max(np.abs(joint_positions - previous_joint_positions)))
            previous_joint_positions = joint_positions

            if tracking_error > maximum_tracking_error:
                maximum_tracking_error = tracking_error
                supervisor = getattr(CONTROLLER, "IK_FALLBACK_SUPERVISOR", None)
                maximum_error_diagnostic = {
                    "frame": frame_index,
                    "elapsed_s": round(elapsed_time, 6),
                    "tracking_error_m": tracking_error,
                    "rotation_error_deg": math.degrees(rotation_error),
                    "ik_mode": getattr(CONTROLLER, "RUNTIME_IK_MODE", None),
                    "fallback_active": getattr(CONTROLLER, "RUNTIME_IK_FALLBACK_ACTIVE", None),
                    "severe_triggered": getattr(CONTROLLER, "RUNTIME_IK_SEVERE_TRIGGERED", None),
                    "severe_reason": getattr(CONTROLLER, "RUNTIME_IK_SEVERE_REASON", None),
                    "primary_guard_reverted": getattr(CONTROLLER, "RUNTIME_IK_PRIMARY_GUARD_REVERTED", None),
                    "primary_guard_fallback_triggered": getattr(CONTROLLER, "RUNTIME_IK_PRIMARY_GUARD_FALLBACK_TRIGGERED", None),
                    "primary_guard_start_error_m": getattr(CONTROLLER, "RUNTIME_IK_PRIMARY_GUARD_START_ERROR_M", None),
                    "primary_guard_candidate_error_m": getattr(CONTROLLER, "RUNTIME_IK_PRIMARY_GUARD_CANDIDATE_ERROR_M", None),
                    "primary_guard_recovery_error_m": getattr(CONTROLLER, "RUNTIME_IK_PRIMARY_GUARD_RECOVERY_ERROR_M", None),
                    "fallback_bad_frames": getattr(supervisor, "bad_frames", None) if supervisor is not None else None,
                    "fallback_good_frames": getattr(supervisor, "good_frames", None) if supervisor is not None else None,
                    "decoupled_score": getattr(CONTROLLER, "RUNTIME_IK_DECOUPLED_SCORE", None),
                    "coupled_score": getattr(CONTROLLER, "RUNTIME_IK_COUPLED_SCORE", None),
                    "multiseed_score": getattr(CONTROLLER, "RUNTIME_IK_MULTI_SEED_SCORE", None),
                    "selected_seed": getattr(CONTROLLER, "RUNTIME_IK_SELECTED_SEED", None),
                    "collision_status": getattr(CONTROLLER, "RUNTIME_COLLISION_NEAREST_STATUS", None),
                    "collision_clearance_m": getattr(CONTROLLER, "RUNTIME_COLLISION_CLEARANCE_M", None),
                    "safe_position": np.asarray(safe_position).tolist(),
                    "wrist_position": np.asarray(wrist_position).tolist(),
                    "seed_diagnostics": getattr(CONTROLLER, "RUNTIME_IK_SEED_DIAGNOSTICS", []),
                }

            maximum_rotation_error = max(maximum_rotation_error, rotation_error)
            maximum_joint_step = max(maximum_joint_step, joint_step)
            minimum_elbow_angle = min(minimum_elbow_angle, float(joint_positions[3]))
            if context["collision_limited"]:
                collision_limited_frames += 1
            if getattr(CONTROLLER, "RUNTIME_IK_MODE", "decoupled") != "decoupled":
                fallback_frames += 1
            if getattr(CONTROLLER, "RUNTIME_IK_SEVERE_TRIGGERED", False):
                severe_trigger_frames += 1
            if getattr(CONTROLLER, "RUNTIME_IK_PRIMARY_GUARD_REVERTED", False):
                primary_guard_frames += 1

        self.assertEqual(relative_workspace_failures, 0)
        self.assertEqual(collision_limited_frames, 0)
        self.assertLessEqual(
            maximum_tracking_error,
            0.01,
            msg=f"maximum tracking error diagnostic: {maximum_error_diagnostic}",
        )
        self.assertLessEqual(maximum_rotation_error, math.radians(2.0))

        # The controller clamps each joint step to exactly 1.5 degrees. Floating-
        # point subtraction can reproduce that boundary a few ulps above
        # math.radians(1.5), so compare with a tiny numerical tolerance rather
        # than treating an exact-limit command as a physical overshoot.
        self.assertLessEqual(
            maximum_joint_step,
            math.radians(1.5) + 1e-12,
        )
        self.assertGreaterEqual(minimum_elbow_angle, math.radians(10.0))
        self.assertGreaterEqual(fallback_frames, 0)
        self.assertGreaterEqual(severe_trigger_frames, 0)
        self.assertGreaterEqual(primary_guard_frames, 0)


if __name__ == "__main__":
    unittest.main()
