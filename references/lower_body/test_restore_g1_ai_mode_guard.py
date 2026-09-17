import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("restore_g1_ai_mode.py")


def load_module():
    spec = importlib.util.spec_from_file_location("restore_g1_ai_mode", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RestoreGuardTest(unittest.TestCase):
    def test_detects_known_owner_and_ignores_unrelated_process(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "101").mkdir()
            (root / "101" / "cmdline").write_bytes(
                b"./build/g1_twist2_mink_cycle_trial\0eth0\0"
            )
            (root / "202").mkdir()
            (root / "202" / "cmdline").write_bytes(b"python3\0camera.py\0")
            self.assertEqual(
                module.active_command_owners(root),
                [(101, "./build/g1_twist2_mink_cycle_trial eth0")],
            )

    def test_empty_proc_has_no_owner(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(module.active_command_owners(Path(directory)), [])


if __name__ == "__main__":
    unittest.main()
