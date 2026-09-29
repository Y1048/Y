import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
import sys
sys.path.insert(0, str(TOOLS))

import G1_ARCHIVE_OFFLINE_VALIDATE as validator


class ArchiveOfflineValidatorTests(unittest.TestCase):
    def make_archive(self, directory, expected_hash=None):
        path = Path(directory) / "archive.zip"
        payload = b"offline-capture\n"
        digest = hashlib.sha256(payload).hexdigest()
        manifest = {
            "files": [{
                "path": "PC\\sample.txt",
                "size": len(payload),
                "sha256": expected_hash or digest,
            }]
        }
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("PC/sample.txt", payload)
            archive.writestr("manifest.json", json.dumps(manifest))
        return path
    def test_manifest_verification_accepts_exact_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_archive(directory)
            with zipfile.ZipFile(path) as archive:
                result = validator.verify_manifest(archive)
        self.assertEqual(1, result["verified_files"])
        self.assertEqual([], result["failures"])

    def test_manifest_verification_rejects_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_archive(directory, expected_hash="0" * 64)
            with zipfile.ZipFile(path) as archive:
                result = validator.verify_manifest(archive)
        self.assertEqual(0, result["verified_files"])
        self.assertEqual(["manifest_sha256:PC/sample.txt"], result["failures"])

    def test_quaternion_comparison_is_sign_invariant(self):
        value = [0.5, 0.5, 0.5, 0.5]
        self.assertEqual(
            0.0,
            validator.quaternion_l2_sign_invariant(
                value, [-component for component in value]
            ),
        )

    def test_validator_source_has_no_live_transport_import(self):
        source = (TOOLS / "G1_ARCHIVE_OFFLINE_VALIDATE.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertTrue(
            imports.isdisjoint(
                {"socket", "subprocess", "requests", "websocket", "paramiko"}
            )
        )

    def test_camera_log_requires_streaming_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "camera.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(
                    "camera.log",
                    "[WAIT] Unity TCP5011 unavailable; enter Play\n"
                    "[STREAMING] frames=1 latest_bytes=165287\n"
                    "[STREAMING] frames=3 latest_bytes=165433\n",
                )
            with zipfile.ZipFile(path) as archive:
                result = validator.analyze_camera_log(archive, "camera.log")
        self.assertEqual(2, result["streaming_updates"])
        self.assertEqual(3, result["last_frame_counter"])
        self.assertFalse(result["jpeg_payload_archived"])
        self.assertEqual([], result["failures"])

    def test_unique_entry_requires_exactly_one_match(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "entries.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("logs/a.jsonl", "{}\n")
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(
                    "logs/a.jsonl",
                    validator.unique_entry(archive, "logs/", ".jsonl"),
                )
                with self.assertRaises(RuntimeError):
                    validator.unique_entry(archive, "missing/", ".jsonl")


if __name__ == "__main__":
    unittest.main()
