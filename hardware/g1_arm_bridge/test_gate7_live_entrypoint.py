#!/usr/bin/env python3
"""Static entrypoint checks for the supported Gate 7 physical wrapper."""

from __future__ import annotations

import unittest
import builtins
import ast
import time
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

import gate7_live_arm_sdk as live


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]


class Gate7LiveEntrypointTests(unittest.TestCase):
    def test_guarded_wait_forwards_preview_and_preserves_confirmation(self):
        tree = ast.parse((HERE / "gate7_live_arm_sdk_entry.py").read_text(encoding="utf-8"))
        definition = next(node for node in ast.walk(tree)
                          if isinstance(node, ast.FunctionDef) and node.name == "guarded_wait_for_active")
        first, confirmed = object(), object()
        guard = Mock()
        original = Mock(return_value=first)
        receive = Mock(return_value=confirmed)
        preview = Mock()
        namespace = dict(original_wait_for_active=original, acquisition_guard=guard,
                         original_receive_latest=receive, acquisition_timeout_s=0.1, time=time)
        exec(compile(ast.Module(body=[definition], type_ignores=[]), "<guarded wait>", "exec"), namespace)
        wait = namespace["guarded_wait_for_active"]
        sock = object()
        self.assertIs(wait(sock, 1.0, preview), confirmed)
        original.assert_called_once_with(sock, 1.0, preview)
        guard.seed.assert_called_once_with(first)
        guard.observe.assert_called_once_with(confirmed)
        preview.assert_called_once_with()
        self.assertIs(wait.socket, sock)
        preview.side_effect = RuntimeError("stale preview")
        receive.reset_mock()
        with self.assertRaisesRegex(RuntimeError, "stale preview"):
            wait(sock, 1.0, preview)
        receive.assert_not_called()

    def RunWithoutHardware(self, flags, installed=False):
        original_import = builtins.__import__

        def ImportWithoutSDK(name, *args, **kwargs):
            if name.startswith("unitree_sdk2py"):
                raise AssertionError("Unitree SDK import reached in offline test")
            return original_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            with patch.object(live.sys, "argv", ["gate7_live_arm_sdk.py", *flags]), \
                 patch.object(live, "_result_path", return_value=path), \
                 patch.object(live, "_supported_gate7_entry_guards_installed", installed, create=True), \
                 patch.object(live, "ValidateHardwareAuthorization", side_effect=PermissionError("authorization boundary reached")) as authorization, \
                 patch.object(live, "validate_precheck", side_effect=AssertionError("precheck boundary reached")) as precheck, \
                 patch.object(live.socket, "socket", side_effect=AssertionError("socket creation forbidden")) as socket_constructor, \
                 patch("builtins.__import__", side_effect=ImportWithoutSDK) as imports:
                exit_code = live.main()
            result = json.loads(path.read_text(encoding="utf-8"))
        socket_constructor.assert_not_called()
        precheck.assert_not_called()
        self.assertFalse(any(call.args[0].startswith("unitree_sdk2py") for call in imports.call_args_list))
        self.assertFalse(result["publisher_created"])
        self.assertEqual(0, result["published_frames"])
        return exit_code, result, authorization.call_count

    def test_direct_runtime_blocked_before_authorization_sdk_and_network(self):
        for flags in ([], ["--enable-hardware-output"], ["--pre-publisher-check-only"]):
            with self.subTest(flags=flags):
                exit_code, result, calls = self.RunWithoutHardware(flags)
                self.assertEqual(2, exit_code)
                self.assertFalse(result["passed"])
                self.assertIn("requires installed safety guards", result["fault"])
                self.assertEqual(0, calls)

    def test_direct_validate_only_remains_available(self):
        exit_code, result, calls = self.RunWithoutHardware(["--validate-only"])
        self.assertEqual(0, exit_code)
        self.assertTrue(result["passed"])
        self.assertEqual("VALIDATE_ONLY", result["mode"])
        self.assertEqual(0, calls)

    def test_installed_guard_does_not_bypass_authorization(self):
        exit_code, result, calls = self.RunWithoutHardware([], installed=True)
        self.assertEqual(2, exit_code)
        self.assertEqual(1, calls)
        self.assertIn("authorization boundary reached", result["fault"])

    def test_wsl_starter_uses_supported_guarded_entrypoint(self) -> None:
        starter = (HERE / "start_gate7_live_arm_sdk_wsl.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("gate7_live_arm_sdk_entry.py", starter)
        self.assertNotIn(
            'exec "${python_path}" -u hardware/g1_arm_bridge/gate7_live_arm_sdk.py',
            starter,
        )

    def test_entrypoint_installs_collision_guards(self) -> None:
        source = (HERE / "gate7_live_arm_sdk_entry.py").read_text(encoding="utf-8")
        self.assertIn("require_active_collision_evidence", source)
        self.assertIn("validate_final_command_segment", source)
        self.assertIn("frame=None", source)

    def test_entrypoint_installs_continuous_acquisition_and_full_body_guards(self) -> None:
        source = (HERE / "gate7_live_arm_sdk_entry.py").read_text(encoding="utf-8")
        self.assertIn("ActiveAcquisitionGuard", source)
        self.assertIn("ACTIVE Mink stream did not remain live", source)
        self.assertIn("acquisition_guard.require_fresh", source)
        self.assertIn("validate_full_body_snapshot_matches_precheck", source)
        self.assertIn("validate_acquisition_hold_target", source)

    def test_entrypoint_requires_relay_token_live_provenance_and_retired_sessions(self) -> None:
        source = (HERE / "gate7_live_arm_sdk_entry.py").read_text(encoding="utf-8")
        self.assertIn("--expected-relay-token", source)
        self.assertIn("require_relay_token", source)
        self.assertIn("require_live_hardware_provenance", source)
        self.assertIn("RetiredSessionGuard", source)
        launcher = (
            PROJECT_ROOT / "tools" / "START_G1_GATE7_LIVE_HARDWARE.bat"
        ).read_text(encoding="utf-8")
        self.assertIn("GATE7_RELAY_TOKEN", launcher)
        self.assertIn("--relay-token %GATE7_RELAY_TOKEN%", launcher)
        self.assertIn("--expected-relay-token %GATE7_RELAY_TOKEN%", launcher)


if __name__ == "__main__":
    unittest.main(verbosity=2)
