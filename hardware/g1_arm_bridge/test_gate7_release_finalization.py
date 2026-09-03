#!/usr/bin/env python3
"""Static integration checks for Gate 7 release finalization (R1)."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE_PATH = HERE / "gate7_live_arm_sdk.py"


class Gate7ReleaseFinalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.main = next(
            node
            for node in cls.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        cls.outer_try = next(
            node
            for node in cls.main.body
            if isinstance(node, ast.Try) and node.finalbody
        )

    def test_finalizer_uses_shared_release_contract(self) -> None:
        final_text = "\n".join(ast.unparse(node) for node in self.outer_try.finalbody)
        self.assertIn("execute_release_sequence", final_text)
        self.assertIn("evidence.as_dict()", final_text)
        self.assertIn("release_zero_frames", final_text)

    def test_finalizer_does_not_reload_runtime_config(self) -> None:
        final_text = "\n".join(ast.unparse(node) for node in self.outer_try.finalbody)
        self.assertNotIn("LoadLiveHardwareConfig", final_text)
        self.assertNotIn("load_gate7_config", final_text)

    def test_release_failure_revokes_pass_and_marks_unknown_output(self) -> None:
        final_text = "\n".join(ast.unparse(node) for node in self.outer_try.finalbody)
        self.assertIn("result['passed'] = False", final_text)
        self.assertIn("result['output_state_unknown'] = True", final_text)
        self.assertIn("result['command_output_enabled'] = True", final_text)

    def test_active_write_records_only_successfully_published_weight(self) -> None:
        main_text = ast.unparse(self.main)
        publish_index = main_text.index("publisher.Write(command_message)")
        success_index = main_text.index(
            "last_successful_weight = float(last_weight)",
            publish_index,
        )
        self.assertLess(publish_index, success_index)


if __name__ == "__main__":
    unittest.main(verbosity=2)
