"""Offline decisions for the dedicated G1 USB Ethernet preflight."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import G1_PORTABLE as dispatcher
import g1_portable_environment as network


class G1EthernetAutoRepairTests(unittest.TestCase):
    def test_read_only_inspection_detects_wrong_address(self):
        result = subprocess.CompletedProcess([], 0, stdout="17\n", stderr="")
        with mock.patch.object(network.subprocess, "run", return_value=result) as run:
            self.assertEqual(17, network.dedicated_wired_adapter_needing_address())
        self.assertIn("Get-NetAdapter", run.call_args.args[0][-1])
        self.assertIn("Get-NetIPAddress", run.call_args.args[0][-1])

    def test_missing_or_ambiguous_adapter_never_requests_repair(self):
        for code, stdout in ((0, ""), (1, ""), (0, "17\n18\n")):
            with self.subTest(code=code, stdout=stdout), mock.patch.object(
                    network.subprocess, "run", return_value=subprocess.CompletedProcess(
                        [], code, stdout=stdout, stderr="")):
                if code or stdout.strip():
                    with self.assertRaises(RuntimeError):
                        network.dedicated_wired_adapter_needing_address()
                else:
                    self.assertIsNone(network.dedicated_wired_adapter_needing_address())

    def _teleop(self, args, adapter=17, repair_rc=0):
        with mock.patch.object(dispatcher, "require_embedded_interpreter"), \
                mock.patch.object(dispatcher.dependencies, "ensure") as ensure, \
                mock.patch.object(network, "dedicated_wired_adapter_needing_address",
                                  return_value=adapter) as inspect, \
                mock.patch.object(dispatcher, "elevated_powershell",
                                  return_value=repair_rc) as elevated, \
                mock.patch("G1_VR_TELEOP_LAUNCH.main", return_value=0) as launch:
            if repair_rc and adapter is not None and not (
                    "--check-only" in args or "--host" in args and args[args.index("--host") + 1] != "auto"):
                with self.assertRaisesRegex(RuntimeError, "No teleop workers were started"):
                    dispatcher.teleop(args)
            else:
                self.assertEqual(0, dispatcher.teleop(args))
            return ensure.call_count, inspect.call_count, elevated.call_args, launch.call_count

    def test_repair_before_any_worker_launch(self):
        ensure, inspected, elevated, launched = self._teleop([], adapter=17)
        self.assertEqual((1, 1, 1), (ensure, inspected, launched))
        self.assertEqual(
            ["-InterfaceIndex", "17", "-VerifyRobotSsh"], elevated.args[1])

    def test_failed_repair_stops_before_dependency_and_worker_launch(self):
        ensure, inspected, elevated, launched = self._teleop([], repair_rc=1)
        self.assertEqual((0, 1, 0), (ensure, inspected, launched))
        self.assertIsNotNone(elevated)

    def test_no_change_for_correct_address_explicit_or_check_only(self):
        for args, adapter, inspected in (([], None, 1), (["--check-only"], 17, 0),
                                         (["--host", "192.168.10.165"], 17, 0)):
            with self.subTest(args=args, adapter=adapter):
                ensure, actual_inspected, elevated, launched = self._teleop(
                    args, adapter=adapter)
                self.assertEqual((1, inspected, None, 1),
                                 (ensure, actual_inspected, elevated, launched))


if __name__ == "__main__":
    unittest.main()
