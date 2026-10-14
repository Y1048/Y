"""Offline tests for the integrated onboard GROOT SSH supervisor."""

import importlib.util
import io
import json
import hashlib
from contextlib import redirect_stdout
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import threading
from contextlib import ExitStack
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
            dict(cwd=groot.REMOTE_DIR, owner=OWNER, args=list(expected_actuator),
                 observer_log_dir=groot.observer_log_directory(OWNER)),
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
            stdout=json.dumps(dict(errors=[],supports_unlimited_duration=False,processes=[],
                                   observer_verified=True,observer_binary=groot.OBSERVER_BINARY)),
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
        self.assertNotIn('subprocess', groot.inspection_source())
        self.assertNotIn('mkdir', groot.inspection_source())
        self.assertNotIn('publisher', groot.inspection_source())

    def test_observer_environment_only_for_actuator_and_preserves_runtime_cwd(self):
        command=groot.ssh_command(HOST,groot.actuator_argv(False),OWNER)[-1]
        self.assertIn('cd '+groot.REMOTE_DIR,command)
        self.assertIn('mkdir -p -- '+groot.observer_log_directory(OWNER),command)
        self.assertIn('export GROOT_COMMAND_OBSERVER_DIR='+groot.observer_log_directory(OWNER),command)
        self.assertIn('exec '+groot.OBSERVER_BINARY,command)
        self.assertNotIn('GROOT_COMMAND_OBSERVER_DIR',groot.ssh_command(HOST,groot.HEADING_ARGV,OWNER)[-1])
        for owner in ('.','..','../escape'):
            with self.assertRaises(ValueError):groot.observer_log_directory(owner)

    def test_old_actuator_or_missing_log_environment_is_not_reused(self):
        expected=groot.actuator_argv(False)
        for args,directory in [(('./build/groot_balance_actuator',)+expected[1:],''),
                               (expected,''),(expected,'/tmp/elsewhere')]:
            with self.assertRaises(RuntimeError):
                groot.classify_existing([dict(cwd=groot.REMOTE_DIR,owner=OWNER,
                    args=list(args),observer_log_dir=directory)],expected)

    def test_observer_check_does_not_enroll_or_run(self):
        with mock.patch.object(groot,'inspect_remote',return_value={}) as inspect, \
                mock.patch.object(groot,'ensure_login') as enroll, mock.patch.object(groot,'run') as run, \
                redirect_stdout(io.StringIO()):
            self.assertEqual(0,groot.main(['--host',HOST,'--check-observer']))
            inspect.assert_called_once_with(HOST);enroll.assert_not_called();run.assert_not_called()

    def test_hash_query_rejects_changed_candidate_without_execution(self):
        # Execute the actual remote inspection against mocked files/proc; never runs a binary.
        for changed in (False,True):
            data=b'fixture --unlimited-duration'
            scope=dict(observer_binary='/candidate/build/groot_balance_actuator',
                       observer_files=[('/candidate/build/groot_balance_actuator',
                                       hashlib.sha256(data).hexdigest(),False)])
            def fake_open(path, mode='r'):
                return io.BytesIO(b'changed' if changed else data) if mode == 'rb' else io.StringIO('fixture-boot')
            with mock.patch('builtins.open',side_effect=fake_open), \
                    mock.patch('os.path.isdir',return_value=True),mock.patch('os.path.isfile',return_value=True), \
                    mock.patch('os.access',return_value=True),mock.patch('os.listdir',return_value=[]), \
                    mock.patch('shutil.which',return_value='/usr/bin/python3'),redirect_stdout(io.StringIO()) as output:
                exec(groot.REMOTE_INSPECT,scope)
            result=json.loads(output.getvalue())
            self.assertEqual(not changed,result['observer_verified'])
            self.assertEqual(changed,bool(result['errors']))

    def test_missing_verification_payload_fails(self):
        result=subprocess.CompletedProcess([],0,'{"errors":[]}', '')
        with mock.patch.object(groot.subprocess,'run',return_value=result):
            with self.assertRaisesRegex(RuntimeError,'verification missing'):groot.inspect_remote(HOST)

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

    def test_confirmed_start_selects_one_observer_and_records_log_directory(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(groot,'ROOT',Path(directory)), \
                mock.patch.object(groot,'ensure_login'), \
                mock.patch.object(groot,'inspect_remote',return_value={'processes':[]}), \
                mock.patch.object(groot,'_spawn',side_effect=lambda *a:(mock.MagicMock(pid=101),mock.MagicMock())) as spawn, \
                mock.patch.object(groot,'_require_still_running'), \
                mock.patch.object(groot,'_install_stop_handlers',return_value={}), \
                mock.patch.object(groot,'_restore_stop_handlers'), \
                mock.patch.object(groot,'graceful_stop_owned') as stop, \
                mock.patch.object(groot.threading,'Thread'), \
                mock.patch.object(groot.threading,'Event') as event,redirect_stdout(io.StringIO()):
            event.return_value.wait.return_value=True
            self.assertEqual(0,groot.run(HOST,confirmed=True,owner_id=OWNER))
            self.assertEqual(['heading','actuator'],[c.args[1] for c in spawn.call_args_list])
            self.assertEqual(groot.OBSERVER_BINARY,spawn.call_args_list[1].args[2][0])
            report=json.loads(next(Path(directory).rglob('command_observer.json')).read_text())
            self.assertEqual(groot.observer_log_directory(OWNER),report['remote_log_directory'])
            self.assertFalse(report['reused']);stop.assert_called_once_with(HOST,OWNER)

    def test_failed_remote_hash_check_cannot_start_children(self):
        with mock.patch.object(groot,'ensure_login'), \
                mock.patch.object(groot,'inspect_remote',side_effect=RuntimeError('observer_hash_mismatch')), \
                mock.patch.object(groot,'_spawn') as spawn:
            with self.assertRaisesRegex(RuntimeError,'observer_hash_mismatch'):
                groot.run(HOST,confirmed=True)
            spawn.assert_not_called()

    def test_startup_exit_is_rejected(self):
        child = mock.MagicMock()
        child.poll.return_value = 1
        with mock.patch.object(groot.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "exited during startup"):
                groot._require_still_running("heading controller", child)

    def test_manager_file_is_detected_without_stdin_or_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'groot.stop'
            stopped = threading.Event()
            journal = mock.MagicMock()
            self.assertFalse(groot._manager_stop_requested(path, stopped, journal))
            path.write_text('stop\n')
            self.assertTrue(groot._manager_stop_requested(path, stopped, journal))
            self.assertTrue(stopped.is_set())
            self.assertTrue(groot._manager_stop_requested(path, stopped, journal))
            journal.record.assert_called_once_with('stop_requested', source='manager_file', request_file=str(path))

    def test_stop_already_requested_does_not_start_heading_or_actuator(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(groot, 'ROOT', Path(directory)), \
                mock.patch.object(groot, 'ensure_login'), \
                mock.patch.object(groot, 'inspect_remote', return_value={'processes': []}), \
                mock.patch.object(groot, '_spawn') as spawn, \
                mock.patch.object(groot, '_install_stop_handlers', return_value={}), \
                mock.patch.object(groot, '_restore_stop_handlers'), \
                mock.patch.object(groot, 'graceful_stop_owned') as stop, \
                mock.patch.object(groot.threading, 'Thread'), redirect_stdout(io.StringIO()):
            path = Path(directory) / 'groot.stop'
            path.write_text('stop\n')
            self.assertEqual(0, groot.run(HOST, confirmed=True, owner_id=OWNER, stop_request_file=path))
            spawn.assert_not_called()
            stop.assert_called_once_with(HOST, OWNER)

    def test_request_during_heading_start_prevents_actuator_start(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(groot, 'ROOT', Path(directory)), \
                mock.patch.object(groot, 'ensure_login'), \
                mock.patch.object(groot, 'inspect_remote', return_value={'processes': []}), \
                mock.patch.object(groot, '_require_still_running'), \
                mock.patch.object(groot, '_install_stop_handlers', return_value={}), \
                mock.patch.object(groot, '_restore_stop_handlers'), \
                mock.patch.object(groot, 'graceful_stop_owned') as stop, \
                mock.patch.object(groot.threading, 'Thread'), redirect_stdout(io.StringIO()):
            path = Path(directory) / 'groot.stop'
            def spawn_heading(*args):
                path.write_text('stop\n')
                return mock.MagicMock(pid=101), mock.MagicMock()
            with mock.patch.object(groot, '_spawn', side_effect=spawn_heading) as spawn:
                self.assertEqual(0, groot.run(HOST, confirmed=True, owner_id=OWNER, stop_request_file=path))
                self.assertEqual(['heading'], [c.args[1] for c in spawn.call_args_list])
                stop.assert_called_once_with(HOST, OWNER)

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


class ReusedProcessTests(unittest.TestCase):
    def rows(self):
        return [dict(pid=101, boot_id='boot-1', start_ticks='456', owner='old-owner',
                     cwd=groot.REMOTE_DIR, args=list(groot.HEADING_ARGV)),
                dict(pid=102, boot_id='boot-1', start_ticks='789', owner='old-owner',
                     cwd=groot.REMOTE_DIR, args=list(groot.actuator_argv(False)),
                     observer_log_dir=groot.observer_log_directory('old-owner'))]

    def test_remote_watch_checks_pid_identity_and_is_read_only(self):
        row = self.rows()[0]
        def execute_watch(change=None):
            def read(path, mode='r'):
                if path.endswith('/boot_id'):
                    return io.StringIO('different' if change == 'boot' else 'boot-1')
                if path.endswith('/stat'):
                    fields = ['Z' if change == 'zombie' else 'S'] + ['0'] * 18 + ['999' if change == 'pid_reuse' else '456']
                    return io.StringIO('101 (python3) ' + ' '.join(fields))
                if path.endswith('/cmdline'):
                    if change == 'missing':
                        raise FileNotFoundError(path)
                    return io.BytesIO(b'other\0' if change == 'args' else '\0'.join(row['args']).encode())
                if path.endswith('/environ'):
                    return io.BytesIO(b'G1_GROOT_OWNER=' + (b'new-owner' if change == 'owner' else b'old-owner'))
                raise AssertionError(path)
            with mock.patch('builtins.open', side_effect=read), \
                    mock.patch('os.readlink', return_value='/other' if change == 'cwd' else groot.REMOTE_DIR), \
                    mock.patch('time.sleep', side_effect=InterruptedError('fixture end')), \
                    redirect_stdout(io.StringIO()) as output:
                if change:
                    with self.assertRaises(SystemExit) as ended:
                        exec(groot.REMOTE_WATCH, {'expected': [row]})
                    self.assertEqual(3, ended.exception.code)
                else:
                    with self.assertRaises(InterruptedError):
                        exec(groot.REMOTE_WATCH, {'expected': [row]})
            return json.loads(output.getvalue())
        self.assertEqual('reused_process_alive', execute_watch()['event'])
        for change in ('boot', 'pid_reuse', 'zombie', 'missing', 'args', 'owner', 'cwd'):
            with self.subTest(change=change):
                self.assertEqual('reused_process_lost', execute_watch(change)['event'])
        for forbidden in ('os.kill', 'subprocess', 'publisher', 'SDK', 'SIGINT'):
            self.assertNotIn(forbidden, groot.REMOTE_WATCH)

    def test_missing_identity_cannot_start_watcher(self):
        for key in ('pid', 'boot_id', 'start_ticks'):
            row = self.rows()[0]
            del row[key]
            with mock.patch.object(groot.subprocess, 'Popen') as spawn:
                with self.assertRaisesRegex(RuntimeError, 'identity unavailable'):
                    groot._watch_reused(HOST, [row], Path('unused'))
                spawn.assert_not_called()

    def test_watch_opens_noninteractive_read_only_ssh(self):
        with mock.patch.object(groot, 'ssh_executable', return_value='ssh-test.exe'), \
                mock.patch.object(groot.subprocess, 'Popen') as spawn, \
                mock.patch.object(groot.threading, 'Thread') as thread:
            groot._watch_reused(HOST, self.rows(), Path('unused'))
            command = spawn.call_args.args[0]
            self.assertIn('-T', command)
            self.assertNotIn('-tt', command)
            self.assertTrue(command[-1].startswith('python3 -c '))
            self.assertNotIn('; exec ', command[-1])
            self.assertEqual(subprocess.DEVNULL, spawn.call_args.kwargs['stdin'])
            thread.return_value.start.assert_called_once()

    def test_lost_console_does_not_drop_remote_error_log(self):
        child = mock.MagicMock()
        child.stdout = iter(['first error\n', 'last error\n'])
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch('builtins.print', side_effect=OSError('console lost')):
            path = Path(directory) / 'heading.log'
            groot._tee('heading', child, path)
            self.assertEqual('[HEADING] first error\n[HEADING] last error\n', path.read_text())

    def test_watch_loss_and_normal_stop_never_adopt_or_signal_reused_owner(self):
        for lost in (False, True):
            with self.subTest(lost=lost), tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
                stack.enter_context(mock.patch.object(groot, 'ROOT', Path(directory)))
                stack.enter_context(mock.patch.object(groot, 'ensure_login'))
                stack.enter_context(mock.patch.object(groot, 'inspect_remote', return_value={'processes': self.rows()}))
                spawn = stack.enter_context(mock.patch.object(groot, '_spawn'))
                watch = mock.MagicMock(pid=501, returncode=3 if lost else None)
                watch.poll.return_value = 3 if lost else None
                stack.enter_context(mock.patch.object(groot, '_watch_reused', return_value=(watch, mock.MagicMock())))
                stack.enter_context(mock.patch.object(groot, '_require_still_running'))
                stack.enter_context(mock.patch.object(groot, '_install_stop_handlers', return_value={}))
                stack.enter_context(mock.patch.object(groot, '_restore_stop_handlers'))
                stop = stack.enter_context(mock.patch.object(groot, 'graceful_stop_owned'))
                stack.enter_context(mock.patch.object(groot.threading, 'Thread'))
                event = stack.enter_context(mock.patch.object(groot.threading, 'Event'))
                event.return_value.wait.return_value = not lost
                stack.enter_context(redirect_stdout(io.StringIO()))
                if lost:
                    with self.assertRaisesRegex(RuntimeError, 'reused-process watcher ended'):
                        groot.run(HOST, confirmed=True, owner_id='new-owner')
                else:
                    self.assertEqual(2, groot.run(HOST, confirmed=True, owner_id='new-owner'))
                    watch.terminate.assert_called_once()
                spawn.assert_not_called()
                stop.assert_called_once_with(HOST, 'new-owner')
                rows = [json.loads(s) for s in next(Path(directory).rglob('supervisor.jsonl')).read_text().splitlines()]
                self.assertEqual('not_owned_not_verified', rows[-1]['reused_actuator_shutdown'])
                if lost:
                    self.assertIn('unexpected_worker_exit', [r['event'] for r in rows])


if __name__ == "__main__":
    unittest.main()
