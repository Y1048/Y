import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import mujoco
import mink

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "MuJoCo_G1_Controller/scripts"))
import run_mink_g1_right_arm_prototype as base
from g1_mink_feasible_target import FeasibleTargetPlanner
from g1_mink_trajectory import StatefulMinkTrajectory
from g1_mink_return_cycle import SimulationReturnCycle
from run_mink_g1_right_arm_virtual_center_live import cycle_velocity_limits


class ModelReturnTest(unittest.TestCase):
    def build(self):
        with tempfile.TemporaryDirectory() as directory:
            path = base._prepare_mink_xml(output_path=Path(directory)/"model.xml")
            model = mujoco.MjModel.from_xml_path(str(path))
        base._apply_operational_joint_limits(model)
        configuration = mink.Configuration(model)
        home = base._initial_configuration(model)
        configuration.update(home)
        speeds = cycle_velocity_limits()
        planner = FeasibleTargetPlanner(model, None, None, None, None, [], [],
                                       "quadprog", .020,
                                       speeds)
        caps = [speeds[name] for name in base.g1.RIGHT_ARM_JOINTS]
        np.testing.assert_allclose(caps, np.deg2rad([90]*4+[180]*3))
        np.testing.assert_allclose(planner.velocity_caps, caps)
        trajectory = StatefulMinkTrajectory(planner, planner.qpos_ids, caps,
                                           [np.deg2rad(30.)]*7, [10.]*7, .01)
        self.assertTrue(planner.CheckConfiguration(home))
        return configuration, home, planner, trajectory

    def stream(self):
        stream = SimpleNamespace(return_state="returning", return_epoch=1,
                                 return_session="test")
        def ack(epoch, session):
            self.assertEqual((epoch, session), (stream.return_epoch, "test"))
            stream.return_state = "await_idle"
            return True
        stream.acknowledge_simulation_return = ack
        return stream

    def test_actual_model_return_and_repeat(self):
        configuration, home, planner, trajectory = self.build()
        cycle = SimulationReturnCycle(home, trajectory)
        stream = self.stream()
        now = 0.
        for repeat in range(2):
            goal = home.copy()
            goal[planner.qpos_ids[0]] -= .3
            for _ in range(120):
                step = trajectory.Step(configuration.q, goal)
                self.assertTrue(step.applied)
                configuration.update(step.q)
                now += .01
            self.assertGreater(np.max(np.abs(configuration.q-home)), .01)
            stream.return_state = "returning"
            stream.return_epoch = repeat+1
            stages = set()
            for _ in range(2900):
                now += .01
                before = configuration.q.copy()
                step = cycle.step(stream, configuration, now)
                stages.add(cycle.stage)
                self.assertNotEqual(stream.return_state, "fault", cycle.reason)
                self.assertTrue(np.all(np.abs(step.velocity_rad_s) <= np.array(trajectory.velocity_limits)+1e-9))
                self.assertLessEqual(max(abs(x) for x in step.acceleration_rad_s2), np.deg2rad(30.)+1e-9)
                frozen = np.ones(len(home), dtype=bool)
                frozen[planner.qpos_ids] = False
                np.testing.assert_array_equal(configuration.q[frozen], before[frozen])
                if stream.return_state == "await_idle":
                    break
            self.assertEqual(stream.return_state, "await_idle")
            self.assertIn("home", stages)
            self.assertIn("complete", stages)
            np.testing.assert_allclose(configuration.q, home, atol=1e-6)

    def test_collision_failure_holds_without_ack(self):
        configuration, home, planner, trajectory = self.build()
        planner.CheckConfiguration = lambda q: False
        stream = self.stream()
        cycle = SimulationReturnCycle(home, trajectory)
        cycle.step(stream, configuration, 1.)
        self.assertEqual(stream.return_state, "fault")
        np.testing.assert_array_equal(configuration.q, home)


if __name__ == "__main__":
    unittest.main()
