"""Generated-file tests for native/Python excitation cross-checking."""
import ast
import csv
import math
from pathlib import Path
import tempfile
import unittest

import sysid_excitation_crosscheck as crosscheck
import sysid_excitation_plan as plan
import sysid_excitation_preview as preview
from test_sysid_excitation_plan import request


class CrosscheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.plan = plan.build(request())
        self.plan_path = self.folder / "plan.json"
        self.plan_path.write_bytes(plan.canonical(self.plan))
        self.csv_path = self.folder / "native.csv"
        self.rows = preview.expand(self.plan)["training"]
        self._write(self.rows)

    def tearDown(self):
        self.temporary.cleanup()

    def _write(self, rows):
        with self.csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(crosscheck.HEADER)
            for time_s, segment, joint, offsets, velocity, acceleration in rows:
                writer.writerow([
                    time_s, segment, "" if joint is None else joint, *offsets,
                    velocity, acceleration,
                ])

    def test_matching_samples_are_hash_bound_and_nonexecuting(self):
        result = crosscheck.compare(self.plan_path, self.csv_path, "training")
        self.assertEqual(result["samples"], len(self.rows))
        self.assertFalse(result["command_capable"])
        self.assertFalse(result["physical_execution_authorized"])
        self.assertIsNone(result["recommended_hardware_gains"])

    def test_numeric_change_missing_row_and_nonfinite_are_rejected(self):
        cases = []
        changed = [list(row) for row in self.rows]
        changed[10][3] = changed[10][3].copy()
        changed[10][3][0] += 1e-5
        cases.append(changed)
        cases.append(self.rows[:-1])
        changed = [list(row) for row in self.rows]
        changed[10][4] = math.nan
        cases.append(changed)
        for rows in cases:
            with self.subTest(samples=len(rows)):
                self._write(rows)
                with self.assertRaises(ValueError):
                    crosscheck.compare(self.plan_path, self.csv_path, "training")

    def test_crosschecker_and_dumper_have_no_transport_path(self):
        imports = []
        source = Path(crosscheck.__file__).read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.extend(item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        self.assertFalse(any(name in ("socket", "subprocess") for name in imports))
        native = (Path(__file__).parent / "sysid_excitation_plan_dump.cpp").read_text(
            encoding="utf-8")
        for forbidden in (
                "unitree", "ChannelPublisher", "LowCmd", "ChannelFactory",
                "socket", "Client", "Write(", "Send("):
            self.assertNotIn(forbidden, native)


if __name__ == "__main__":
    unittest.main()
