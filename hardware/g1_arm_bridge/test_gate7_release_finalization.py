#!/usr/bin/env python3
"""Source wiring and extracted-finalizer execution tests without SDK/network."""

from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from arm_sdk_release_contract import execute_release_sequence


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

    def RunFinalizer(self, scenario="normal", prior_pass=True):
        # Execute source, not a copied finalizer; all I/O is replaced in this namespace.
        module = ast.Module(body=self.outer_try.finalbody, type_ignores=[])
        clock = [0.0]
        frames = []
        writes = []
        snapshot = SimpleNamespace(all_q_rad=tuple([0.0] * 29), mode_pr=0, mode_machine=5)
        hold_config = object()
        target = tuple([0.1] * 14)
        message = SimpleNamespace()

        def BuildFrame(measured, arm_target, **kwargs):
            frame = SimpleNamespace(measured=measured, target=arm_target, **kwargs)
            frame.motor_q_rad = tuple(measured)
            frame.motor_mode = (0,) * 35
            frame.motor_kp = frame.motor_kd = (0.0,) * 35
            frame.motor_dq_rad_s = frame.motor_tau_nm = (0.0,) * 35
            frames.append(frame)
            return frame

        def ApplyFrame(command, frame):
            command.frame = frame

        def Publish(command):
            writes.append(command.frame.weight)
            if scenario == "all_writes_fail" or (scenario == "first_write_fails" and len(writes) == 1):
                raise OSError("fake write failure")
            if scenario == "zero_tail_fails" and len(writes) == 4:
                raise OSError("fake zero tail failure")

        def Snapshot():
            return None if scenario == "snapshot_missing" else snapshot

        def Sleep(seconds):
            clock[0] += seconds

        def Release(**kwargs):
            if scenario == "release_raises":
                raise RuntimeError("fake finalizer failure")
            return execute_release_sequence(
                **kwargs, monotonic=lambda: clock[0], sleep=Sleep,
                unix_time_ns=lambda: int(clock[0] * 1e9) + 1000,
            )

        result = {
            "passed": prior_pass, "command_output_enabled": True,
            "release_zero_frames": 0, "output_state_unknown": False,
            "external_authority_handoff_confirmed": False,
        }
        path = Mock()
        trace_namespace = {}
        trace_class = next(node for node in self.tree.body
                           if isinstance(node, ast.ClassDef) and node.name == "CommandDiagnosticTrace")
        exec(compile(ast.Module(body=[trace_class], type_ignores=[]),
                     str(SOURCE_PATH), "exec"), trace_namespace)
        snapshot.received_monotonic_s = 0.0
        namespace = dict(
            diagnostic_trace=trace_namespace["CommandDiagnosticTrace"](),
            time=SimpleNamespace(time_ns=lambda: int(clock[0] * 1e9) + 1000,
                                 monotonic=lambda: clock[0]),
            publisher=None if scenario == "no_publisher" else SimpleNamespace(Write=Publish),
            command_message=message, command_crc=SimpleNamespace(Crc=lambda _: 123),
            gate7_config=SimpleNamespace(command_hz=100.0),
            hardware_config=SimpleNamespace(release_ramp_s=0.02, release_zero_cycles=3),
            session=None if scenario == "missing_prerequisite" else SimpleNamespace(hold_config=hold_config),
            last_target=target, last_successful_weight=0.2,
            last_successful_write_unix_ns=777, buffer=SimpleNamespace(snapshot=Snapshot),
            build_measured_hold_frame=BuildFrame,
            dual_arm_from_all_joints=lambda values: tuple(values[15:29]),
            _apply_frame=ApplyFrame, execute_release_sequence=Release,
            result=result, mink_socket=Mock(), unity_socket=Mock(),
            result_path=path, json=json, print=Mock(),
        )
        exec(compile(module, str(SOURCE_PATH), "exec"), namespace)
        namespace["mink_socket"].close.assert_called_once_with()
        namespace["unity_socket"].close.assert_called_once_with()
        path.write_text.assert_called_once()
        saved = json.loads(path.write_text.call_args.args[0])
        self.assertEqual(result, saved)
        self.assertFalse(saved["external_authority_handoff_confirmed"])
        for frame in frames:
            self.assertIs(frame.config, hold_config)
        return saved, writes, frames

    def test_executed_normal_finalizer_preserves_hold_config_and_zero_target(self):
        result, writes, frames = self.RunFinalizer()
        self.assertTrue(result["passed"])
        self.assertTrue(result["zero_release_completed"])
        self.assertFalse(result["command_output_enabled"])
        self.assertEqual(3, result["release_zero_frames"])
        self.assertEqual([0.2, 0.1, 0.0, 0.0, 0.0, 0.0], writes)
        self.assertEqual(tuple([0.1] * 14), frames[0].target)
        self.assertEqual(tuple([0.0] * 14), frames[-1].target)
        trace = result["command_diagnostic_trace"]
        self.assertEqual(trace["errors"], 0)
        self.assertEqual([sample["phase"] for sample in trace["samples"]],
                         ["RELEASE", "ZERO_WEIGHT"])

    def test_executed_release_does_not_erase_prior_fault(self):
        result, _, _ = self.RunFinalizer(prior_pass=False)
        self.assertFalse(result["passed"])
        self.assertTrue(result["zero_release_completed"])

    def test_executed_ramp_fault_revokes_pass_even_after_zero_tail(self):
        result, writes, _ = self.RunFinalizer("first_write_fails")
        self.assertFalse(result["passed"])
        self.assertTrue(result["zero_release_completed"])
        self.assertFalse(result["command_output_enabled"])
        self.assertEqual([0.2, 0.0, 0.0, 0.0], writes)

    def test_executed_incomplete_release_never_reports_safe_output(self):
        for scenario in ("all_writes_fail", "zero_tail_fails", "snapshot_missing",
                         "missing_prerequisite", "release_raises"):
            with self.subTest(scenario=scenario):
                result, _, _ = self.RunFinalizer(scenario)
                self.assertFalse(result["passed"])
                self.assertTrue(result["output_state_unknown"])
                self.assertTrue(result["command_output_enabled"])
                self.assertTrue(result["release_fault"])
                if scenario in ("all_writes_fail", "snapshot_missing"):
                    self.assertEqual(777, result["last_successful_write_unix_ns"])

    def test_executed_no_publisher_does_not_send_release(self):
        result, writes, frames = self.RunFinalizer("no_publisher", prior_pass=False)
        self.assertEqual([], writes)
        self.assertEqual([], frames)
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
