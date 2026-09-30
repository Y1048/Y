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
            "START_G1_VR_TELEOP": (ROOT / "START_G1_VR_TELEOP.bat", "teleop"),
            "BUILD_AND_INSTALL_VR_APK": (
                ROOT / "tools/BUILD_AND_INSTALL_VR_APK.bat", "build-install-apk"),
            "CONFIGURE_G1_ETHERNET": (
                ROOT / "tools/CONFIGURE_G1_ETHERNET.bat", "ethernet-configure"),
            "RESTORE_G1_ETHERNET_DHCP": (
                ROOT / "tools/RESTORE_G1_ETHERNET_DHCP.bat", "ethernet-restore"),
        }
        tracked_tools = {path.stem for path in (ROOT / "tools").glob("*.bat")}
        self.assertEqual(set(expected) - {"START_G1_VR_TELEOP"}, tracked_tools)
        self.assertTrue((ROOT / "START_G1_VR_TELEOP.bat").is_file())
        for name, (path, command) in expected.items():
            with self.subTest(name=name):
                source = path.read_text(encoding="utf-8")
                self.assertEqual(3, len(source.splitlines()))
                self.assertIn(r"runtime\python\python.exe", source)
                self.assertIn("G1_PORTABLE.py", source)
                self.assertIn(" " + command, source)
                self.assertIn("%*", source)
                for forbidden in (".venv-teleop", "py -3.11", "pip ", "powershell"):
                    self.assertNotIn(forbidden, source.lower())

    def test_operator_runtime_sources_have_no_machine_local_python_paths(self):
        sources = list((ROOT / "tools").glob("*.py"))
        sources.remove(ROOT / "tools/BUILD_EMBEDDED_RUNTIME.py")
        sources += list((ROOT / "MuJoCo_G1_Controller/scripts").glob("g1_*.py"))
        sources += list((ROOT / "hardware/g1_arm_bridge").glob("g1_*.py"))
        forbidden = (r"C:\\Users\\", ".venv-teleop", "py -3.11", "VIRTUAL_ENV")
        for path in sources:
            with self.subTest(path=path.relative_to(ROOT)):
                source = path.read_text(encoding="utf-8-sig")
                for token in forbidden:
                    self.assertNotIn(token, source)

    def test_portable_module_has_no_wsl_camera_fallback(self):
        source = (ROOT / "tools/g1_portable_environment.py").read_text(encoding="utf-8")
        for token in (
            "wsl.exe", "camera_run", "configure_mirrored_network",
            "start_camera_tcp_bridge_wsl.sh",
        ):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
