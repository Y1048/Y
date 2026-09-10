"""Configure-only source graph check with empty SDK/Torch path placeholders.

Never builds or runs a native/ARM/SDK target. Explicit roots and ABI also
prevent CMake's optional torch-import discovery from running.
"""
from pathlib import Path
import json
import platform
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class NativeCycleBuildContractTest(unittest.TestCase):
    def test_cycle_only_configures_without_untracked_legacy_sources(self):
        self.assertIsNotNone(shutil.which("cmake"), "cmake is required")
        with tempfile.TemporaryDirectory(prefix="g1-native-graph-only-") as folder:
            tmp = Path(folder)
            sdk, torch = tmp / "sdk-placeholder", tmp / "torch-placeholder"
            (sdk / "include/unitree").mkdir(parents=True)
            (torch / "include/torch").mkdir(parents=True)
            (torch / "include/torch/script.h").touch()
            lib = sdk / "lib" / platform.machine()
            lib.mkdir(parents=True)
            (lib / "libunitree_sdk2.a").touch()
            command = ["cmake", "-S", str(ROOT / "native_vr_build"),
                       f"-DUNITREE_SDK2_ROOT={sdk}", f"-DTORCH_PYTHON_ROOT={torch}",
                       "-DTORCH_CXX11_ABI=0", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"]
            configured = subprocess.run(command + ["-B", str(tmp / "cycle"),
                                                  "-DBUILD_LEGACY_NATIVE_TARGETS=OFF"],
                                        capture_output=True, text=True, timeout=30)
            self.assertEqual(configured.returncode, 0, configured.stdout + configured.stderr)
            graph = json.loads((tmp / "cycle/compile_commands.json").read_text())
            self.assertEqual([Path(item["file"]).name for item in graph],
                             ["twist2_mink_cycle_trial.cpp"])
            # Explicitly requested missing legacy inputs must fail loudly.
            rejected = subprocess.run(command + ["-B", str(tmp / "legacy"),
                                                "-DBUILD_LEGACY_NATIVE_TARGETS=ON"],
                                      capture_output=True, text=True, timeout=30)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("Legacy source missing", rejected.stdout + rejected.stderr)


if __name__ == "__main__":
    unittest.main()
