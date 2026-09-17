"""Windows-local test of the inventory's exact-path read-only source inspection."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from inspect_wsl_sdk_readonly import Inspect,RELATIVE_FILES

class InventoryTests(unittest.TestCase):
 def test_exact_paths_hash_and_no_execution(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);file=root/RELATIVE_FILES[0]
   file.parent.mkdir(parents=True);file.write_bytes(b"synthetic header")
   ignored=root/"unrelated.py";ignored.write_text("raise RuntimeError('must not execute')")
   result=Inspect(root)
   self.assertEqual(len(result),1)
   self.assertEqual(result[0]["sha256"],hashlib.sha256(b"synthetic header").hexdigest())
   self.assertEqual(file.read_bytes(),b"synthetic header")
   self.assertEqual(len(list(root.rglob("*"))),6) # 4 directories + two files
 def test_absent_sources(self):
  with tempfile.TemporaryDirectory() as directory:self.assertEqual(Inspect(directory),[])

if __name__=="__main__":unittest.main()
