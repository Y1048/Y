"""Generated request-draft tests only; no DDS, SDK, network or controller."""
import ast
import json
import math
from pathlib import Path
import tempfile
import unittest

import sysid_excitation_request as draft
import test_sysid_excitation_plan as plan_fixture
import test_sysid_readonly as capture_fixture


ROOT = Path(__file__).resolve().parents[2]
COMMON = ROOT / "references/lower_body/twist2_deploy/cpp_g1_twist2/twist2_common.hpp"
CONTROLLER = Path(__file__).resolve().parent / "twist2_mink_cycle_trial.cpp"


def spec():
    value = plan_fixture.request()
    return {"schema": draft.SPEC_SCHEMA, "contract_id": value["contract_id"],
            **{x: value[x] for x in ("amplitude_rad", "velocity_limit_rad_s",
              "acceleration_limit_rad_s2", "sample_period_s", "hold_s", "cycles",
              "termination_owner_contract")},
            "tail_s": .5, "pose_range_tolerance_rad": .01,
            "velocity_tolerance_rad_s": .05,
            "parameter_basis": "generated fixture only"}


class RequestDraftTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def capture(self, moving=False):
        path=self.root/"capture.jsonl"; rows=[capture_fixture.row(k,False) for k in range(301)]
        for row in rows:
            row["measured_q"]=[0.0]*29; row["measured_dq"]=[0.0]*29
            if moving: row["measured_dq"][22]=.1
        capture_fixture.save(path,rows); return path

    def test_builds_source_and_capture_bound_request(self):
        request,receipt=draft.create(self.capture(),COMMON,CONTROLLER,spec())
        self.assertEqual(request["joint_indices"],list(range(22,29)))
        self.assertEqual(request["kp_nm_rad"][22:29],[40.,40.,40.,40.,20.,20.,20.])
        self.assertEqual(request["kd_nm_s_rad"][22:29],[5.,5.,5.,5.,1.,1.,1.])
        self.assertEqual(receipt["controller_source_sha256"],request["controller_source_sha256"])
        self.assertEqual(receipt["parameter_basis"],"generated fixture only")
        self.assertFalse(receipt["physical_execution_authorized"])
        self.assertIsNone(receipt["recommended_hardware_gains"])

    def test_unstable_capture_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"velocity_not_stable"):
            draft.create(self.capture(True),COMMON,CONTROLLER,spec())

    def test_source_parser_rejects_missing_arrays(self):
        bad=self.root/"bad.hpp";bad.write_text("constexpr float kJointLimitMargin=0.05F;")
        with self.assertRaisesRegex(ValueError,"missing_cpp_array"):
            draft.create(self.capture(),bad,CONTROLLER,spec())

    def test_missing_parameter_basis_is_rejected(self):
        value=spec();value["parameter_basis"]=""
        with self.assertRaisesRegex(ValueError,"parameter_basis"):
            draft.create(self.capture(),COMMON,CONTROLLER,value)

    def test_checked_in_draft_matches_existing_joint22_shape(self):
        path=ROOT/"docs/G1_SYSID_EXCITATION_DRAFT_SPEC_20260914.json"
        value=draft._spec(json.loads(path.read_text(encoding="utf-8")))
        self.assertTrue(all(abs(x-math.radians(8))<1e-15 for x in value["amplitude_rad"]))
        self.assertTrue(all(abs(x-math.radians(20))<1e-15 for x in value["velocity_limit_rad_s"]))
        self.assertTrue(all(abs(x-math.radians(60))<1e-15 for x in value["acceleration_limit_rad_s2"]))
        self.assertEqual(value["termination_owner_contract"]["status"],"unresolved")

    def test_no_command_capable_imports(self):
        imports=[]
        for node in ast.walk(ast.parse(Path(draft.__file__).read_text(encoding="utf-8"))):
            if isinstance(node,ast.Import):imports.extend(x.name for x in node.names)
            elif isinstance(node,ast.ImportFrom):imports.append(node.module or "")
        for forbidden in ("socket","subprocess","unitree","torch"):
            self.assertFalse(any(x==forbidden or x.startswith(forbidden+".") for x in imports))


if __name__=="__main__":unittest.main()
