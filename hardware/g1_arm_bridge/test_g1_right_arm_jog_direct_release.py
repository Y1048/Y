#!/usr/bin/env python3
"""Static regression checks for direct Jog shared release integration (R46)."""
from __future__ import annotations
import ast
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'g1_right_arm_jog.py'

class DirectJogReleaseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.source)
        cls.main = next(
            node for node in cls.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == 'main'
        )
        cls.main_text = ast.unparse(cls.main)

    def test_direct_controller_uses_shared_release_contract(self) -> None:
        self.assertIn(
            'from arm_sdk_release_contract import ReleaseEvidence, execute_release_sequence',
            self.source,
        )
        self.assertGreaterEqual(self.main_text.count('execute_release_sequence'), 2)
        self.assertIn('release_evidence.as_dict()', self.main_text)

    def test_active_weight_is_recorded_after_successful_write(self) -> None:
        publish = self.main_text.index('publisher.Write(command_message)')
        recorded = self.main_text.index(
            'last_successful_weight = float(current_weight)', publish
        )
        self.assertLess(publish, recorded)

    def test_fault_handler_does_not_claim_output_disabled(self) -> None:
        outer_try = next(node for node in self.main.body if isinstance(node, ast.Try))
        handler_text = ast.unparse(outer_try.handlers[0])
        self.assertNotIn('command_output_enabled', handler_text)
        self.assertIn("result['passed'] = False", handler_text)

    def test_finalizer_fails_closed_without_release_evidence(self) -> None:
        self.assertIn('output_state_unknown', self.main_text)
        self.assertIn('release_evidence is None', self.main_text)
        self.assertIn("result['command_output_enabled'] = True", self.main_text)
        self.assertNotIn('release_started_s = time.monotonic()', self.main_text)

if __name__ == '__main__':
    unittest.main(verbosity=2)
