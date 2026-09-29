"""Offline portability tests for the bundled Windows runtime."""
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import g1_portable_environment as portable
import g1_embedded_runtime as embedded


class PortableTests(unittest.TestCase):
    def test_wired_first_fallback_and_explicit_host(self):
        with mock.patch.object(portable.socket, "create_connection") as connect:
            self.assertEqual("192.168.123.164", portable.select_robot_host())
            connect.assert_called_once_with(("192.168.123.164", 22), timeout=1.5)
        with mock.patch.object(
                portable.socket, "create_connection",
                side_effect=[OSError("timeout"), mock.MagicMock()]) as connect:
            self.assertEqual("192.168.10.165", portable.select_robot_host())
            self.assertEqual(("192.168.10.165", 22), connect.call_args.args[0])
        with mock.patch.object(
                portable.socket, "create_connection",
                side_effect=OSError("timeout")) as connect:
            with self.assertRaises(RuntimeError):
                portable.select_robot_host()
            self.assertEqual(2, connect.call_count)
        with mock.patch.object(portable.socket, "create_connection") as connect:
            self.assertEqual(
                "192.168.10.165",
                portable.select_robot_host("192.168.10.165"))
            connect.assert_not_called()

    def test_embedded_paths_are_checkout_relative(self):
        self.assertEqual(ROOT / "runtime/python/python.exe", embedded.PYTHON_EXE)
        self.assertEqual(
            ROOT / "runtime/python/Lib/site-packages",
            embedded.SITE_PACKAGES)
        self.assertTrue(embedded.PYTHON_EXE.is_file())
        self.assertTrue((embedded.SITE_PACKAGES / "mujoco/__init__.py").is_file())

    def test_all_bats_are_three_line_embedded_shims(self):
        expected = {
            "START_G1_VR_TELEOP": "teleop",
            "START_G1_CAMERA_TO_UNITY": "camera",
            "START_BIMANUAL_SIM": "bimanual-demo",
            "START_BIMANUAL_UNITY_SIM": "bimanual-unity",
            "REPORT_LATEST_BIMANUAL_SESSION": "report-latest",
            "VERIFY_LATEST_BIMANUAL_QUEST_CYCLE": "verify-latest-quest",
            "SETUP_G1_VR_TELEOP": "check-runtime",
            "RESOLVE_UNITY_EDITOR": "resolve-unity",
            "BUILD_AND_INSTALL_VR_APK": "build-install-apk",
            "CONFIGURE_G1_ETHERNET": "ethernet-configure",
            "RESTORE_G1_ETHERNET_DHCP": "ethernet-restore",
        }
        tracked = {path.stem for path in (ROOT / "tools").glob("*.bat")}
        self.assertEqual(set(expected), tracked)
        for name, command in expected.items():
            with self.subTest(name=name):
                source = (ROOT / "tools" / (name + ".bat")).read_text(encoding="utf-8")
                self.assertEqual(3, len(source.splitlines()))
                self.assertIn(r"runtime\python\python.exe", source)
                self.assertIn("G1_PORTABLE.py", source)
                self.assertIn(" " + command, source)
                self.assertIn("%*", source)
                for forbidden in (".venv-teleop", "py -3.11", "pip ", "powershell"):
                    self.assertNotIn(forbidden, source.lower())

    def test_portable_module_has_no_wsl_camera_fallback(self):
        source = (ROOT / "tools/g1_portable_environment.py").read_text(encoding="utf-8")
        for token in (
            "wsl.exe", "camera_run", "configure_mirrored_network",
            "start_camera_tcp_bridge_wsl.sh",
        ):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
