"""Exercise the display-mode helper in an isolated Windows PowerShell workspace."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which("powershell.exe")


@unittest.skipUnless(POWERSHELL, "Requires Windows PowerShell used by BAT launchers")
class UnityDisplayModeLauncherTests(unittest.TestCase):
    def test_create_replace_and_invalid_mode_preserve_contract(self):
        # Only a copied helper runs here; no live project config or G1 is accessed.
        with tempfile.TemporaryDirectory(prefix="g1 display mode ") as directory:
            root = Path(directory)
            tools = root / "tools"
            tools.mkdir()
            script = tools / "SET_UNITY_DISPLAY_MODE.ps1"
            shutil.copy2(PROJECT_ROOT / "tools" / script.name, script)
            target = root / "logs/runtime/unity_display_mode.json"
            command = [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass",
                       "-File", str(script), "-Mode"]
            for mode in ("simulation", "simulation", "hardware", "recorded", "simulation"):
                result = subprocess.run(command + [mode], capture_output=True,
                                        text=True, timeout=20)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual({"schema": "g1.unity.display.v1", "mode": mode},
                                 json.loads(target.read_text(encoding="utf-8")))
                self.assertEqual([], list(target.parent.glob("*.tmp")))
            previous = target.read_bytes()
            result = subprocess.run(command + ["auto"], capture_output=True,
                                    text=True, timeout=20)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(previous, target.read_bytes())


class ReadOnlyPreviewLauncherTests(unittest.TestCase):
    def test_preview_only_delegates_to_read_only_launchers(self):
        source = (PROJECT_ROOT / "tools/START_G1_VR_PREVIEW_READ_ONLY.bat").read_text()
        self.assertIn('call "%~dp0VIEW_G1_LIVE_MUJOCO.bat"', source)
        self.assertIn('call "%~dp0START_G1_CAMERA_TO_UNITY.bat"', source)
        for forbidden in ("--enable-hardware-output", "START_G1_GATE7", "START_VR_HAND_TO_MUJOCO", "hardware_output_authorized", "SelectMode"):
            self.assertNotIn(forbidden, source)
        self.assertLess(source.index(":5013"), source.index('start "G1 Read-only Camera"'))


if __name__ == "__main__":
    unittest.main()
