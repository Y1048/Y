import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import g1_teleop_dependencies as deps


class DependencyTests(unittest.TestCase):
    def test_real_bundled_runtime_probe_passes(self):
        result = deps.validate(deps.PYTHON)
        self.assertTrue(result)

    def test_requirements_are_exact_and_match_installed_metadata(self):
        pins = deps.requirements(ROOT / "tools/requirements-teleop.txt")
        self.assertEqual(pins["mujoco"], "3.12.0")
        self.assertEqual(pins["numpy"], "2.4.6")
        self.assertEqual(pins["websockets"], "15.0.1")
        self.assertEqual(len(pins), 16)

    def test_probe_rejects_wrong_version(self):
        real_version = deps.metadata.version
        def version(name):
            return "0.0.0" if name == "mujoco" else real_version(name)
        with mock.patch.object(deps.metadata, "version", side_effect=version):
            self.assertFalse(deps.probe())

    def test_validate_missing_python_is_false(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(deps.validate(Path(directory) / "python.exe"))

    def test_ensure_never_installs_or_repairs(self):
        with mock.patch.object(deps, "validate", return_value=False),                 mock.patch.object(deps.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "[Rr]estore runtime/python"):
                deps.ensure()
            run.assert_not_called()

    def test_batch_is_only_embedded_python_shim(self):
        source = (ROOT / "tools/START_G1_VR_TELEOP.bat").read_text(encoding="utf-8")
        self.assertIn(r"runtime\python\python.exe", source)
        self.assertIn("G1_PORTABLE.py", source)
        self.assertIn(" teleop ", source)
        for forbidden in ("py -3.11", ".venv-teleop", "pip ", "g1_teleop_dependencies.py"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
