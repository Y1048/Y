"""Numerical checks of the live feasible planner, no sockets or robot SDK."""

import sys
import itertools
import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from pathlib import Path

import mink
import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import verify_virtual_center_kinematics as probe
from verify_feasible_target import BuildPlanner


class FeasibleTargetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        probe.base._prepare_mink_xml()
        cls.model = mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
        probe.base._apply_operational_joint_limits(cls.model)
        cls.initial = probe.base._initial_configuration(cls.model)
        cls.qpos = [int(cls.model.jnt_qposadr[probe.base._joint_id(cls.model, name)])
                    for name in probe.base.g1.RIGHT_ARM_JOINTS]
        cls.initial[cls.qpos] = np.deg2rad([10, -22, 0, 55, 0, 0, 0])

    def Pose(self, q):
        configuration = mink.Configuration(self.model)
        configuration.update(q)
        return configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")

    def CheckPlan(self, planner, origin, plan):
        self.assertTrue(plan.valid, plan.status)
        self.assertTrue(planner.CheckConfiguration(plan.next_q))
        self.assertTrue(planner.CheckConfiguration(plan.target_q))
        np.testing.assert_allclose(self.Pose(plan.target_q).translation(), plan.target_position, atol=1e-12)
        velocity = np.zeros(self.model.nv)
        mujoco.mj_differentiatePos(self.model, velocity, probe.base.DT, origin, plan.next_q)
        self.assertTrue(np.all(np.abs(velocity[planner.right_dofs]) <= planner.velocity_caps + 1e-6))
        np.testing.assert_allclose(velocity[planner.frozen_dofs], 0, atol=1e-7)

    def test_known_feasible_goal_has_separate_checked_lookahead(self):
        planner = BuildPlanner(self.model, self.initial)
        goal_q = self.initial.copy()
        goal_q[self.qpos] += np.deg2rad([-20, 5, 15, 10, 20, 15, -20])
        goal = self.Pose(goal_q)
        q = self.initial.copy()
        first = planner.Plan(q, goal)
        self.CheckPlan(planner, q, first)
        self.assertGreater(first.accepted_steps, 1)
        self.assertGreater(np.linalg.norm(first.target_q - first.next_q), 1e-5)
        for _ in range(360):
            plan = planner.Plan(q, goal)
            self.CheckPlan(planner, q, plan)
            q = plan.next_q
        self.assertLess(np.linalg.norm(self.Pose(q).translation() - goal.translation()), 0.005)

    def test_invalid_start_is_not_a_feasible_green_target(self):
        planner = BuildPlanner(self.model, self.initial)
        q = self.initial.copy()
        q[self.qpos[3]] = 100
        plan = planner.Plan(q, self.Pose(self.initial))
        self.assertFalse(plan.valid)
        np.testing.assert_array_equal(plan.next_q, q)

    def test_stationary_goal_does_not_move_for_posture_cost_alone(self):
        planner = BuildPlanner(self.model, self.initial)
        q = self.initial.copy()
        q[self.qpos[4]] += 0.2
        plan = planner.Plan(q, self.Pose(q))
        self.CheckPlan(planner, q, plan)
        np.testing.assert_array_equal(plan.next_q, q)

    def test_boundary_hold_and_inward_return_do_not_rebase(self):
        planner = BuildPlanner(self.model, self.initial)
        original = self.Pose(self.initial)
        outside = probe.base._matrix_to_se3(original.rotation().as_matrix(),
                                            original.translation() + [0.35, 0, 0.15])
        saved_goal = outside.as_matrix().copy()
        q = self.initial.copy()
        tail_speed = []
        for index in range(480):
            plan = planner.Plan(q, outside)
            self.CheckPlan(planner, q, plan)
            if index >= 420:
                tail_speed.append(np.max(np.abs(plan.next_q - q)) / probe.base.DT)
            q = plan.next_q
        self.assertLess(max(tail_speed), np.deg2rad(0.5))
        np.testing.assert_array_equal(outside.as_matrix(), saved_goal)
        for _ in range(360):
            plan = planner.Plan(q, original)
            self.CheckPlan(planner, q, plan)
            q = plan.next_q
        self.assertLess(np.linalg.norm(self.Pose(q).translation() - original.translation()), 0.01)

    def test_wrist_only_fk_trajectory_keeps_proximal_joints_quiet(self):
        for index in (4, 5, 6):
            planner = BuildPlanner(self.model, self.initial)
            q = self.initial.copy()
            excursions = []
            # Same 12-second wrist-only cycle as the existing IK regression.
            for step in range(720):
                target_q = self.initial.copy()
                target_q[self.qpos[index]] += np.deg2rad(25) * np.sin(2 * np.pi * step / 720)
                plan = planner.Plan(q, self.Pose(target_q))
                self.CheckPlan(planner, q, plan)
                q = plan.next_q
                excursions.append(np.max(np.abs(q[self.qpos[:4]] - self.initial[self.qpos[:4]])))
            self.assertLess(max(excursions), np.deg2rad(0.5))

    def test_invalid_solver_velocity_cannot_move_the_arm(self):
        planner = BuildPlanner(self.model, self.initial)
        goal = self.Pose(self.initial)
        for value in (float("nan"), 100.0):
            velocity = np.zeros(self.model.nv)
            velocity[planner.right_dofs[0]] = value
            with patch.object(mink, "solve_ik", return_value=velocity):
                plan = planner.Plan(self.initial, goal)
            self.assertEqual(plan.status, "invalid_velocity")
            np.testing.assert_array_equal(plan.next_q, self.initial)

    def test_nonlinear_clearance_check_rejects_candidate(self):
        planner = BuildPlanner(self.model, self.initial)
        goal_q = self.initial.copy()
        goal_q[self.qpos[0]] -= 0.1
        # Initial pose is clear, every proposed/intermediate pose is blocked.
        with patch.object(planner, "CheckConfiguration", side_effect=lambda q: np.array_equal(q, self.initial)):
            plan = planner.Plan(self.initial, self.Pose(goal_q))
        self.assertEqual(plan.accepted_steps, 0)
        np.testing.assert_array_equal(plan.next_q, self.initial)

    def test_runtime_publishes_separate_feasible_and_raw_targets_without_sockets(self):
        live, base = probe.live, probe.base
        updates = []
        for index in range(5):
            active = index in (1, 2, 3)
            updates.append(SimpleNamespace(
                target_position_m=np.array([0.3 + (0.2 if index >= 2 else 0), -0.2, 1.0]),
                target_quaternion_xyzw=np.array([0., 0., 0., 1.]),
                accepted_count=1, rejected_count=0, command_active=active,
                reset_clutch=index == 4, engage_clutch=index == 1,
                control_state="active" if active else "idle",
                input_command_mode="active" if active else "idle",
                session_id="offline-runtime", packet_age_s=0.0,
                clutch_engaged=active, workspace_fault=False))
        viewer = MagicMock()
        viewer.is_running.side_effect = [True] * 5 + [False]
        clock = itertools.count(100.0, 0.02)
        with ExitStack() as stack:
            stack.enter_context(patch.object(live, "parse_args", return_value=SimpleNamespace(
                gate7_feedback_port=5012, show_inspection_scene=False,
                disable_gate7_simulation_feedback=True)))
            stack.enter_context(patch.object(base, "_prepare_mink_xml"))
            stack.enter_context(patch.object(base, "_open_udp_socket"))
            stack.enter_context(patch.object(live.socket, "socket"))
            stream = stack.enter_context(patch.object(base, "MinkCommandStream"))
            stream.return_value.poll.side_effect = updates
            launch = stack.enter_context(patch.object(mujoco.viewer, "launch_passive"))
            launch.return_value.__enter__.return_value = viewer
            sent = stack.enter_context(patch.object(base, "_send_state"))
            stack.enter_context(patch.object(base, "_write_status"))
            stack.enter_context(patch.object(live.time, "sleep"))
            stack.enter_context(patch.object(live.time, "monotonic", side_effect=lambda: next(clock)))
            stack.enter_context(patch("builtins.print"))
            live.main()
        packets = [call.args[1] for call in sent.call_args_list[::2]]
        self.assertEqual(len(packets), 5)
        self.assertFalse(packets[0]["right_arm"]["feasible_target_valid"])
        self.assertFalse(packets[-1]["right_arm"]["feasible_target_valid"])
        self.assertTrue(packets[2]["right_arm"]["feasible_target_valid"])
        arm = packets[2]["right_arm"]
        self.assertGreater(np.linalg.norm(np.array(arm["target_position"]) - arm["feasible_target_position"]), 0.1)
        np.testing.assert_allclose(arm["target_delta"], [0.2, 0, 0], atol=1e-12)
        from arm_sdk_teleop_contract import parse_mink_arm_sample
        for packet in packets:
            parse_mink_arm_sample(json.dumps(packet).encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
