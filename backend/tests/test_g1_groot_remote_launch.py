"""Offline tests for the integrated onboard GROOT SSH supervisor."""

import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
try:
    spec = importlib.util.spec_from_file_location(
        "groot_remote_test", TOOLS / "G1_GROOT_REMOTE_LAUNCH.py")
    groot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(groot)
finally:
    sys.path.remove(str(TOOLS))

HOST = "192.168.123.164"


class CommandContractTests(unittest.TestCase):
    def test_exact_user_commands_are_preserved(self):
        self.assertEqual(
            ("python3", "-u", "tools/g1_omni_heading_controller.py",
             "--yaw-sign", "-1"),
            groot.HEADING_ARGV)
        self.assertEqual(
            ("./build/groot_balance_actuator", "--normal",
             "--enable-actuation", "--acknowledge-harness",
             "--accept-handoff-risk", "--supervisor-off",
             "--external-controller", "--interface", "eth0",
             "--duration", "300"),
            groot.ACTUATOR_ARGV)
        heading = groot.ssh_command(HOST, groot.HEADING_ARGV)
        actuator = groot.ssh_command(HOST, groot.ACTUATOR_ARGV)
        self.assertIn("unitree@" + HOST, heading)
        self.assertIn(groot.REMOTE_DIR, heading[-1])
        self.assertIn("|| exit 1", heading[-1])
        self.assertIn("trap", heading[-1])
        self.assertIn("g1_omni_heading_controller.py --yaw-sign -1", heading[-1])
        self.assertIn("--enable-actuation", actuator[-1])
        self.assertIn("--supervisor-off", actuator[-1])

    def test_existing_exact_processes_are_reused(self):
        rows = [
            dict(cwd=groot.REMOTE_DIR,
                 args=["python3", "-u", "tools/g1_omni_heading_controller.py",
                       "--yaw-sign", "-1"]),
            dict(cwd=groot.REMOTE_DIR, args=list(groot.ACTUATOR_ARGV)),
        ]
        self.assertEqual({"heading", "actuator"}, groot.classify_existing(rows))

    def test_conflicting_remote_options_fail_closed(self):
        row = dict(
            cwd=groot.REMOTE_DIR,
            args=["python3", "tools/g1_omni_heading_controller.py",
                  "--yaw-sign", "1"])
        with self.assertRaisesRegex(RuntimeError, "Conflicting remote"):
            groot.classify_existing([row])
    def test_unconfirmed_helper_cannot_start_ssh(self):
        with mock.patch.object(groot, "ensure_login") as login:
            with self.assertRaisesRegex(RuntimeError, "requires.*confirmation"):
                groot.run(HOST, confirmed=False)
        login.assert_not_called()

    def test_remote_inspection_is_read_only_python_probe(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout='{"errors":[],"processes":[]}', stderr="")
        with mock.patch.object(groot.subprocess, "run", return_value=completed) as run:
            self.assertEqual([], groot.inspect_remote(HOST))
        command = run.call_args.args[0]
        self.assertEqual("python3 -", command[-1])
        self.assertNotIn("--enable-actuation", " ".join(command))


class LifetimeTests(unittest.TestCase):
    def test_missing_pair_is_started_and_owned(self):
        heading = mock.MagicMock()
        actuator = mock.MagicMock()
        heading.poll.return_value = None
        actuator.poll.return_value = 0
        heading_thread = mock.MagicMock()
        actuator_thread = mock.MagicMock()
        with mock.patch.object(groot, "ensure_login"), \
                mock.patch.object(groot, "inspect_remote", return_value=[]), \
                mock.patch.object(
                    groot, "_spawn",
                    side_effect=[(heading, heading_thread),
                                 (actuator, actuator_thread)]) as spawn, \
                mock.patch.object(groot.sys.stdin, "isatty", return_value=False), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, groot.run(HOST, confirmed=True))
        self.assertEqual(2, spawn.call_count)
        self.assertEqual("heading", spawn.call_args_list[0].args[1])
        self.assertEqual(groot.HEADING_ARGV, spawn.call_args_list[0].args[2])
        self.assertEqual("actuator", spawn.call_args_list[1].args[1])
        self.assertEqual(groot.ACTUATOR_ARGV, spawn.call_args_list[1].args[2])
        heading.terminate.assert_called_once()
        heading.wait.assert_called()
        actuator.terminate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
