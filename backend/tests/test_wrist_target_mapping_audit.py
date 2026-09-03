"""Target mapping diagnostics must not turn a necessary reach bound into a permit."""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_wrist_target_mapping import OperatorToRobotDelta, GetNecessaryScale, AuditSender


class MappingAuditTests(unittest.TestCase):
    def test_basis_and_lengths(self):
        np.testing.assert_array_equal(OperatorToRobotDelta(np.eye(3)), [[0,-1,0],[0,0,1],[1,0,0]])
        value = np.array([.3,-.2,.1])
        self.assertAlmostEqual(np.linalg.norm(value), np.linalg.norm(OperatorToRobotDelta(value)))
        with self.assertRaises(ValueError):
            OperatorToRobotDelta([0, float("nan"), 0])

    def test_fixed_offset_cancels_in_relative_mapping(self):
        first, second = np.array([.1,.2,.3]), np.array([.2,-.1,.4])
        for center in (np.zeros(3), np.array([.42,-.16,1.05])):
            np.testing.assert_allclose((center + OperatorToRobotDelta(second)) -
                (center + OperatorToRobotDelta(first)), OperatorToRobotDelta(second-first))

    def test_counterfactual_scale_and_anchor_validation(self):
        self.assertAlmostEqual(GetNecessaryScale([.1,0,0], [0,0,0], [[.5,0,0]], .4), .6)
        self.assertEqual(GetNecessaryScale([.1,0,0], [0,0,0], [[0,0,0]], .4), 1.)
        with self.assertRaises(ValueError):
            GetNecessaryScale([.5,0,0], [0,0,0], [[0,0,0]], .4)
        with self.assertRaises(ValueError):
            GetNecessaryScale([0,0,0], [0,0,0], [[1,0,0]], float("inf"))

    def test_sender_rejects_scale_or_axis_drift(self):
        rows=[]
        for value in ([0,0,0], [.1,.2,.3]):
            robot = np.array([.42,-.16,1.05]) + OperatorToRobotDelta(value)
            row={"time_s":"0"}
            row.update({"sender_delta_"+a:str(v) for a,v in zip("xyz",value)})
            row.update({"sender_robot_"+a:str(v) for a,v in zip("xyz",robot)})
            rows.append(row)
        self.assertLess(AuditSender(rows)["axis_mapping_residual_max_m"],1e-12)
        rows[-1]["sender_robot_x"]=".9"
        with self.assertRaises(ValueError):
            AuditSender(rows)


if __name__ == "__main__":
    unittest.main()
