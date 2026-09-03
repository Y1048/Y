"""The inventory lists source files without treating discovery as a full review."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "build_code_index.py"
SPEC = importlib.util.spec_from_file_location("build_code_index", SCRIPT)
index = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(index)


class CodeIndexTests(unittest.TestCase):
    def test_scope_excludes_vendor_and_build_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("START.bat", "backend/one.py", "backend/build/skip.py",
                             "references/original.py", "Unity_G1_VR/Library/skip.cs"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            self.assertEqual([p.relative_to(root).as_posix() for p in index.CollectFiles(root)],
                             ["START.bat", "backend/one.py"])

    def test_python_symbols_are_parsed_without_execution(self):
        source = "raise RuntimeError('must not execute')\nclass Example: pass\ndef Run(): pass\n"
        self.assertEqual(index.GetPythonSymbols(source), "Example, Run")

    def test_index_is_deterministic_and_marks_unknown_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "unknown.py").write_text("def Run(): pass\n", encoding="utf-8")
            result = index.BuildIndex(root)
            self.assertEqual(result, index.BuildIndex(root))
            self.assertIn("| 1 | 목록 확인 | Run |", result)
            self.assertIn("[unknown.py](../unknown.py)", result)


if __name__ == "__main__":
    unittest.main()
