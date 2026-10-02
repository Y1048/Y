"""Offline tests for the integrated onboard GROOT SSH supervisor."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
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
OWNER = "test-owner"


class CommandContractTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(groot, 'ssh_executable', return_value='ssh-test.exe')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_manual_command_contract_and_duration_selection(self):
        self.assertEqual(
            ("python3", "-u", "tools/g1_omni_heading_controller.py",
             "--yaw-sign", "-1"),
            groot.HEADING_ARGV)
        fallback = groot.actuator_argv(False)
        unlimited = groot.actuator_argv(True)
        self.assertEqual(
            ("--duration", "300"), fallback[-2:])
        self.assertEqual(
            ("--unlimited-duration",), unlimited[-1:])
        for command in (fallback, unlimited):
            self.assertIn("--enable-actuation", command)
            self.assertIn("--accept-handoff-risk", command)
            self.assertIn("--supervisor-off", command)
            self.assertIn("--external-controller", command)
            self.assertEqual("eth0", command[command.index("--interface") + 1])

    def test_interactive_commands_force_pty_and_run_foreground(self):
        command = groot.ssh_command(HOST, groot.HEADING_ARGV, OWNER)
        self.assertIn("-tt", command)
        self.assertNotIn("-T", command)
        self.assertIn("unitree@" + HOST, command)
        remote = command[-1]
        self.assertIn("cd " + groot.REMOTE_DIR, remote)
        self.assertIn("G1_GROOT_OWNER=", remote)
        self.assertIn("exec python3 -u tools/g1_omni_heading_controller.py", remote)
        self.assertNotIn("& child=", remote)
        self.assertNotIn("trap ", remote)

    def test_existing_exact_processes_are_reused(self):
        expected_actuator = groot.actuator_argv(False)
        rows = [
            dict(
                cwd=groot.REMOTE_DIR,
                owner="",
                args=["python3", "-u", "tools/g1_omni_heading_controller.py",
                      "--yaw-sign", "-1"]),
            dict(cwd=groot.REMOTE_DIR, owner="", args=list(expected_actuator)),
        ]
        self.assertEqual(
            {"heading", "actuator"},
            groot.classify_existing(rows, expected_actuator))

    def test_conflicting_remote_options_fail_closed(self):
        row = dict(
            cwd=groot.REMOTE_DIR,
            owner="",
            args=["python3", "tools/g1_omni_heading_controller.py",
                  "--yaw-sign", "1"])
        with self.assertRaisesRegex(RuntimeError, "Conflicting remote"):
            groot.classify_existing([row], groot.actuator_argv(False))

    def test_unconfirmed_helper_cannot_start_ssh(self):
        with mock.patch.object(groot, "ensure_login") as login:
            with self.assertRaisesRegex(RuntimeError, "requires.*confirmation"):
                groot.run(HOST, confirmed=False)
        login.assert_not_called()

    def test_remote_inspection_is_noninteractive_and_read_only(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=(
                '{"errors":[],"supports_unlimited_duration":false,'
                '"processes":[]}'
            ),
            stderr="")
        with mock.patch.object(
                groot.subprocess, "run", return_value=completed) as run:
            payload = groot.inspect_remote(HOST)
        self.assertFalse(payload["supports_unlimited_duration"])
        command = run.call_args.args[0]
        self.assertIn("-T", command)
        self.assertNotIn("-tt", command)
        self.assertEqual("python3 -", command[-1])
        self.assertNotIn("--enable-actuation", " ".join(command))

    def test_owner_id_is_strictly_validated(self):
        with self.assertRaises(ValueError):
            groot.ssh_command(HOST, groot.HEADING_ARGV, "bad owner; rm -rf /")
        command = groot.ssh_command(HOST, groot.HEADING_ARGV, OWNER)
        self.assertIn("G1_GROOT_OWNER=" + OWNER, command[-1])


class SpawnAndShutdownTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(groot, 'ssh_executable', return_value='ssh-test.exe')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_spawn_separates_stdin_from_supervisor(self):
        child = mock.MagicMock()
        thread = mock.MagicMock()
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(groot.subprocess, "Popen", return_value=child) as spawn, \
                mock.patch.object(groot.threading, "Thread", return_value=thread):
            groot._spawn(
                HOST, "heading", groot.HEADING_ARGV, OWNER,
                Path(directory) / "heading.log")
        self.assertEqual(subprocess.DEVNULL, spawn.call_args.kwargs["stdin"])
        self.assertEqual(subprocess.PIPE, spawn.call_args.kwargs["stdout"])
        self.assertIn("-tt", spawn.call_args.args[0])
        if os.name == "nt":
            self.assertTrue(
                spawn.call_args.kwargs["creationflags"]
                & subprocess.CREATE_NEW_PROCESS_GROUP)
        thread.start.assert_called_once_with()

    def test_startup_exit_is_rejected(self):
        child = mock.MagicMock()
        child.poll.return_value = 1
        with mock.patch.object(groot.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "exited during startup"):
                groot._require_still_running("heading controller", child)

    def test_controlled_shutdown_is_actuator_then_heading(self):
        with mock.patch.object(
                groot, "_signal_owned",
                side_effect=[
                    {"signalled": [101], "remaining": []},
                    {"signalled": [102], "remaining": []},
                ]) as signal_owned:
            groot.graceful_stop_owned(HOST, OWNER)
        self.assertEqual(
            [
                mock.call(HOST, OWNER, "groot_balance_actuator", 12.0),
                mock.call(HOST, OWNER, "g1_omni_heading_controller.py", 4.0),
            ],
            signal_owned.call_args_list,
        )

    def test_shutdown_failure_is_not_treated_as_success(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=2,
            stdout=(
                '{"target":"groot_balance_actuator",'
                '"signalled":[101],"remaining":[101]}'
            ),
            stderr="")
        with mock.patch.object(
                groot.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "did not finish"):
                groot._signal_owned(
                    HOST, OWNER, "groot_balance_actuator", 0.1)


if __name__ == "__main__":
    unittest.main()
