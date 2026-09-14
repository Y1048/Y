"""Generated plan tests only; no robot, SDK, DDS, network or command output."""
import ast
import math
from pathlib import Path
import unittest

import sysid_excitation_plan as plan


def request():
    return {
        "schema": plan.SCHEMA,
        "contract_id": "generated-test-only",
        "controller_source_sha256": "0" * 64,
        "joint_indices": list(range(22, 29)),
        "start_q_rad": [0.0] * 29,
        "soft_lower_q_rad": [-1.0] * 29,
        "soft_upper_q_rad": [1.0] * 29,
        "kp_nm_rad": [40.0] * 29,
        "kd_nm_s_rad": [5.0] * 29,
        "amplitude_rad": [0.1] * 7,
        "velocity_limit_rad_s": [0.2] * 7,
        "acceleration_limit_rad_s2": [0.4] * 7,
        "sample_period_s": 0.002,
        "hold_s": 0.5,
        "cycles": 2,
        "termination_owner_contract": {"status": "unresolved", "description": "fixture only; no physical execution"},
    }


class ExcitationPlanTests(unittest.TestCase):
    def test_plan_is_bounded_sequential_and_split(self):
        value = plan.build(request())
        self.assertFalse(value["command_capable"])
        self.assertFalse(value["execution_authorized"])
        self.assertIsNone(value["recommended_hardware_gains"])
        self.assertEqual(value["joint_indices"], list(range(22, 29)))
        train = value["episodes"]["training"]
        validation = value["episodes"]["validation"]
        self.assertEqual(train["joint_order"], list(range(22, 29)))
        self.assertEqual(validation["joint_order"], list(reversed(range(22, 29))))
        for episode in (train, validation):
            previous = None
            for segment in episode["segments"]:
                if segment["kind"] == "quintic_move":
                    local = segment["joint_index"] - 22
                    self.assertLessEqual(segment["analytic_peak_velocity_rad_s"], 0.2 + 1e-12)
                    self.assertLessEqual(segment["analytic_peak_acceleration_rad_s2"], 0.4 + 1e-12)
                    self.assertLessEqual(abs(segment["end_offset_rad"]), 0.1 + 1e-12)
                    previous = segment
                elif previous is not None:
                    self.assertEqual(segment["joint_index"], previous["joint_index"])
                    self.assertEqual(segment["offset_rad"], previous["end_offset_rad"])
                    previous = None

    def test_request_is_hash_bound_and_deterministic(self):
        a = plan.build(request())
        b = plan.build(request())
        self.assertEqual(a, b)
        changed = request(); changed["amplitude_rad"][0] = 0.11
        self.assertNotEqual(a["request_sha256"], plan.build(changed)["request_sha256"])

    def test_bad_limits_order_nonfinite_and_missing_are_rejected(self):
        cases = []
        x = request(); x["joint_indices"] = list(reversed(x["joint_indices"])); cases.append(x)
        x = request(); x["amplitude_rad"][0] = 2.0; cases.append(x)
        x = request(); x["velocity_limit_rad_s"][0] = math.nan; cases.append(x)
        x = request(); del x["cycles"]; cases.append(x)
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError): plan.build(value)

    def test_module_has_no_command_or_transport_imports(self):
        imports = []
        for node in ast.walk(ast.parse(Path(plan.__file__).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import): imports.extend(x.name for x in node.names)
            elif isinstance(node, ast.ImportFrom): imports.append(node.module or "")
        for forbidden in ("socket", "subprocess", "unitree", "torch"):
            self.assertFalse(any(x == forbidden or x.startswith(forbidden + ".") for x in imports))


if __name__ == "__main__":
    unittest.main()
