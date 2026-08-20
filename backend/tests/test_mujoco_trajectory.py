from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path

import mujoco
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
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

        for frame_index in range(frame_count):
            elapsed_time = min(frame_index * delta_time, total_duration)
            input_position, input_rotation = FAKE_SENDER.sample_motion(elapsed_time)
            desired_position, _ = CONTROLLER.calculate_clutched_target(
                clutch_reference,
                np.asarray(input_position, dtype=float),
                np.asarray(input_rotation, dtype=float),
            )
            requested_delta = (
                desired_position - clutch_reference["robot_position"]
            )

            # The projected-workspace runtime intentionally replaces the legacy
            # coarse absolute torso keep-out with the sampled voxel workspace.
            # This trajectory test imports the legacy helper module directly and
            # has no workspace NPZ, so only verify that the fake VR motion stays
            # within the clutch-relative envelope here. Workspace projection and
            # collision safety have dedicated tests.
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
                CONTROLLER.calculate_rotation_error(
                    target_rotation,
                    wrist_rotation,
                )
            ))
            joint_positions = data.qpos[context["right_qpos_ids"]].copy()
            joint_step = float(np.max(np.abs(
                joint_positions - previous_joint_positions
            )))
            previous_joint_positions = joint_positions

            maximum_tracking_error = max(maximum_tracking_error, tracking_error)
            maximum_rotation_error = max(maximum_rotation_error, rotation_error)
            maximum_joint_step = max(maximum_joint_step, joint_step)
            minimum_elbow_angle = min(
                minimum_elbow_angle,
                float(joint_positions[3]),
            )
            if context["collision_limited"]:
                collision_limited_frames += 1

        self.assertEqual(relative_workspace_failures, 0)
        self.assertEqual(collision_limited_frames, 0)
        self.assertLessEqual(maximum_tracking_error, 0.01)
        self.assertLessEqual(maximum_rotation_error, math.radians(2.0))
        self.assertLessEqual(maximum_joint_step, math.radians(1.0))
        self.assertGreaterEqual(minimum_elbow_angle, math.radians(10.0))


if __name__ == "__main__":
    unittest.main()
