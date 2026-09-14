"""Generated waveform preview tests; no hardware or transport."""
import ast
from pathlib import Path
import tempfile
import unittest

import sysid_excitation_plan as planner
import sysid_excitation_preview as preview
import test_sysid_excitation_plan as fixture


class PreviewTests(unittest.TestCase):
    def setUp(self):self.plan=planner.build(fixture.request())
    def test_expansion_is_continuous_bounded_and_returns_zero(self):
        episodes=preview.expand(self.plan)
        for rows in episodes.values():
            self.assertTrue(all(max(abs(x) for x in row[3])<=.1+1e-12 for row in rows))
            self.assertTrue(all(abs(row[4])<=.2+1e-12 for row in rows))
            self.assertTrue(all(abs(row[5])<=.4+1e-12 for row in rows))
            self.assertEqual(rows[-1][3],[0.0]*7)

    def test_csv_and_summary_are_hash_bound_and_exclusive(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);plan_path=root/"plan.json"
            from sysid_capture import canonical
            plan_path.write_bytes(canonical(self.plan));out=root/"preview"
            summary=preview.write(plan_path,out)
            self.assertFalse(summary["physical_execution_authorized"])
            self.assertGreater(summary["samples"]["training"],100)
            with self.assertRaises(FileExistsError):preview.write(plan_path,out)

    def test_discontinuity_is_rejected(self):
        self.plan["episodes"]["training"]["segments"][1]["start_offset_rad"]=.01
        with self.assertRaisesRegex(ValueError,"discontinuity"):preview.expand(self.plan)

    def test_no_command_capable_imports(self):
        imports=[]
        for node in ast.walk(ast.parse(Path(preview.__file__).read_text(encoding="utf-8"))):
            if isinstance(node,ast.Import):imports.extend(x.name for x in node.names)
            elif isinstance(node,ast.ImportFrom):imports.append(node.module or "")
        for forbidden in ("socket","subprocess","unitree","torch"):
            self.assertFalse(any(x==forbidden or x.startswith(forbidden+".") for x in imports))


if __name__=="__main__":unittest.main()
