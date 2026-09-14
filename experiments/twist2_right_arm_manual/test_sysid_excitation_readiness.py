"""Generated offline readiness tests; never initializes DDS or a controller."""
import ast
import json
from pathlib import Path
import tempfile
import unittest

import sysid_excitation_plan as planner
import sysid_excitation_readiness as readiness
import test_sysid_excitation_plan as plan_fixture
import test_sysid_readonly as capture_fixture


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        request = plan_fixture.request()
        request["termination_owner_contract"] = {"status": "reviewed", "description": "generated fixture"}
        self.plan = self.root / "plan.json"
        self.plan.write_bytes(json.dumps(planner.build(request), separators=(",", ":")).encode())

    def tearDown(self): self.temp.cleanup()

    def capture(self, *, moving=False, pose_error=0.0, command=True, gain_error=False):
        path = self.root / "capture.jsonl"
        rows = [capture_fixture.row(k, command) for k in range(301)]
        for row in rows:
            row["measured_q"] = [0.0] * 29
            row["measured_dq"] = [0.0] * 29
            row["measured_q"][22] = pose_error
            if moving: row["measured_dq"][25] = 0.2
            if command:
                row["kp"] = [40.0] * 29
                row["kd"] = [5.0] * 29
                if gain_error: row["kp"][22] = 41.0
        capture_fixture.save(path, rows)
        return path

    def test_matching_stable_tail_passes_as_evidence_not_authorization(self):
        result = readiness.inspect(self.plan, self.capture(), pose_tolerance_rad=0.02,
                                   velocity_tolerance_rad_s=0.05)
        self.assertTrue(result["data_collection_preflight_passed"])
        self.assertFalse(result["physical_execution_authorized"])
        self.assertIsNone(result["recommended_hardware_gains"])

    def test_pose_motion_gain_and_owner_blockers(self):
        for kwargs, blocker in (({"pose_error": 0.03}, "start_pose"),
                                ({"moving": True}, "not_stationary"),
                                ({"gain_error": True}, "gain_contract")):
            with self.subTest(blocker=blocker):
                result = readiness.inspect(self.plan, self.capture(**kwargs),
                    pose_tolerance_rad=0.02, velocity_tolerance_rad_s=0.05)
                self.assertTrue(any(blocker in x for x in result["blockers"]))
        value = json.loads(self.plan.read_text())
        value["termination_owner_contract"]["status"] = "unresolved"
        self.plan.write_text(json.dumps(value))
        result = readiness.inspect(self.plan, self.capture(), pose_tolerance_rad=0.02,
                                   velocity_tolerance_rad_s=0.05)
        self.assertIn("termination_owner_contract_unresolved", result["blockers"])

    def test_missing_command_is_unknown_not_a_match(self):
        result = readiness.inspect(self.plan, self.capture(command=False),
            pose_tolerance_rad=0.02, velocity_tolerance_rad_s=0.05)
        self.assertIsNone(result["observed_gains_match_plan"])

    def test_no_transport_or_process_imports(self):
        imports = []
        for node in ast.walk(ast.parse(Path(readiness.__file__).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import): imports.extend(x.name for x in node.names)
            elif isinstance(node, ast.ImportFrom): imports.append(node.module or "")
        for forbidden in ("socket", "subprocess", "unitree", "torch"):
            self.assertFalse(any(x == forbidden or x.startswith(forbidden + ".") for x in imports))


if __name__ == "__main__": unittest.main()
