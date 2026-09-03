from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import mink
import mujoco
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import run_mink_g1_right_arm_prototype as base  # noqa: E402
from run_mink_g1_right_arm_virtual_center_live import (  # noqa: E402
    PROXIMAL_MAX_JOINT_VELOCITY_DEG_S,
    WRIST_MAX_JOINT_VELOCITY_DEG_S,
    VirtualCenterOrientationTask,
    virtual_center_damping_costs,
    virtual_center_posture_costs,
    virtual_center_velocity_limits,
)


def rotation_error_degrees(target: np.ndarray, actual: np.ndarray) -> float:
    rotation_delta = target @ actual.T
    cosine_value = np.clip((np.trace(rotation_delta) - 1.0) * 0.5, -1.0, 1.0)
    return math.degrees(math.acos(float(cosine_value)))


class MinkVirtualCenterTrajectoryTest(unittest.TestCase):
    def test_state_feedback_preserves_all_29_joint_positions(self):
        base._prepare_mink_xml()
        model = mujoco.MjModel.from_xml_path(str(base.g1.DEMO_XML))
        configuration = mink.Configuration(model)
        configuration.update(base._initial_configuration(model))
        all_qpos_ids = np.asarray(
            [
                int(model.jnt_qposadr[base._joint_id(model, joint_name)])
                for joint_name in base.g1.G1_29_JOINTS
            ],
            dtype=int,
        )
        right_qpos_ids = all_qpos_ids[22:29]
        wrist_position = configuration.get_transform_frame_to_world(
            "right_wrist_yaw_link",
            "body",
        ).translation()

        packet = base._state_packet(
            configuration,
            right_qpos_ids,
            all_qpos_ids,
            False,
            wrist_position,
            None,
            False,
        )

        self.assertEqual("mink_simulation", packet["state_source"])
        self.assertEqual(packet["all_joint_names"], base.g1.G1_29_JOINT_NAMES)
        np.testing.assert_allclose(
            packet["all_joint_q_rad"],
            configuration.q[all_qpos_ids],
        )
        np.testing.assert_allclose(
            packet["right_arm"]["joints"],
            configuration.q[right_qpos_ids],
        )

    def test_mixed_wrist_target_converges_within_velocity_limit(self):
        base._prepare_mink_xml()
        model = mujoco.MjModel.from_xml_path(str(base.g1.DEMO_XML))
        base._apply_operational_joint_limits(model)
        configuration = mink.Configuration(model)
        configuration.update(base._initial_configuration(model))

        right_dofs = base._right_arm_dof_indices(model)
        frozen_dofs = base._frozen_dof_indices(model, right_dofs)
        collision_pairs, _ = base._build_collision_pairs(model)

        position_task = mink.FrameTask(
            frame_name="right_wrist_roll_link",
            frame_type="body",
            position_cost=base.POSITION_COST,
            orientation_cost=0.0,
            gain=base.FRAME_GAIN,
            lm_damping=base.LM_DAMPING,
        )
        VirtualCenterOrientationTask.assist_latched = False
        orientation_task = VirtualCenterOrientationTask(model)
        posture_task = mink.PostureTask(model, cost=virtual_center_posture_costs(model))
        posture_task.set_target(configuration.q.copy())
        damping_task = mink.DampingTask(
            model,
            cost=virtual_center_damping_costs(model),
        )

        velocity_limits = virtual_center_velocity_limits()
        limits = [
            mink.ConfigurationLimit(model=model),
            mink.VelocityLimit(model, velocity_limits),
            mink.CollisionAvoidanceLimit(
                model=model,
                geom_pairs=collision_pairs,
                minimum_distance_from_collisions=base.COLLISION_MIN_DISTANCE_M,
                collision_detection_distance=base.COLLISION_DETECTION_DISTANCE_M,
                gain=base.COLLISION_GAIN,
                broadphase=True,
            ),
        ]
        constraints = [
            mink.DofFreezingTask(model=model, dof_indices=frozen_dofs),
        ]

        initial_roll_pose = configuration.get_transform_frame_to_world(
            "right_wrist_roll_link",
            "body",
        )
        initial_yaw_pose = configuration.get_transform_frame_to_world(
            "right_wrist_yaw_link",
            "body",
        )
        target_position = initial_roll_pose.translation() + np.array(
            [0.04, -0.03, 0.025],
            dtype=float,
        )
        yaw_angle = math.radians(12.0)
        yaw_delta = np.array(
            [
                [math.cos(yaw_angle), -math.sin(yaw_angle), 0.0],
                [math.sin(yaw_angle), math.cos(yaw_angle), 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=float,
        )
        target_rotation = yaw_delta @ initial_yaw_pose.rotation().as_matrix()
        position_task.set_target(base._matrix_to_se3(
            initial_roll_pose.rotation().as_matrix(),
            target_position,
        ))
        orientation_task.set_target(base._matrix_to_se3(
            target_rotation,
            initial_yaw_pose.translation(),
        ))

        solver = base._select_solver()
        maximum_proximal_velocity = 0.0
        maximum_wrist_velocity = 0.0
        for _ in range(180):
            velocity = mink.solve_ik(
                configuration=configuration,
                tasks=[
                    position_task,
                    orientation_task,
                    posture_task,
                    damping_task,
                ],
                dt=base.DT,
                solver=solver,
                damping=base.QP_DAMPING,
                limits=limits,
                constraints=constraints,
            )
            maximum_proximal_velocity = max(
                maximum_proximal_velocity,
                float(np.max(np.abs(velocity[right_dofs[:4]]))),
            )
            maximum_wrist_velocity = max(
                maximum_wrist_velocity,
                float(np.max(np.abs(velocity[right_dofs[4:]]))),
            )
            configuration.integrate_inplace(velocity, base.DT)
            mujoco.mj_forward(model, configuration.data)

        final_roll_pose = configuration.get_transform_frame_to_world(
            "right_wrist_roll_link",
            "body",
        )
        final_yaw_pose = configuration.get_transform_frame_to_world(
            "right_wrist_yaw_link",
            "body",
        )
        position_error = float(np.linalg.norm(
            target_position - final_roll_pose.translation()
        ))
        orientation_error = rotation_error_degrees(
            target_rotation,
            final_yaw_pose.rotation().as_matrix(),
        )

        self.assertLessEqual(position_error, 0.001)
        self.assertLessEqual(orientation_error, 0.1)
        self.assertLessEqual(
            maximum_proximal_velocity,
            math.radians(PROXIMAL_MAX_JOINT_VELOCITY_DEG_S) + 1e-10,
        )
        self.assertLessEqual(
            maximum_wrist_velocity,
            math.radians(WRIST_MAX_JOINT_VELOCITY_DEG_S) + 1e-10,
        )


if __name__ == "__main__":
    unittest.main()
