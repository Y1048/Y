"""Local source evidence and existing tests; never launch Unity, WSL or a robot."""

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent


def FindEvidence(relative, token):
    lines = (ROOT / relative).read_text(encoding="utf-8-sig").splitlines()
    return {"path": relative, "matches": [
        {"line": number, "text": line.strip()}
        for number, line in enumerate(lines, 1) if token in line]}


def main():
    with (OUTPUT / "source_checks.csv").open(encoding="utf-8-sig") as stream:
        inventory = list(csv.DictReader(stream))
    changed = [row["path"] for row in inventory if
               hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest()
               != row["sha256"]]
    unity = "Unity_G1_VR/Assets/"
    tokens = [
        (unity + "Scenes/SampleScene.unity", "prefer_skeleton_wrist:"),
        (unity + "Editor/G1ExistingSceneSetup.cs", "prefer_skeleton_wrist ="),
        (unity + "Editor/G1TeleopBatchValidator.cs", "binder_value.prefer_skeleton_wrist"),
        (unity + "G1Teleop/G1WristSourceCompatibility.cs", "prefer_skeleton_wrist ="),
        (unity + "G1Teleop/G1ExistingHandTargetBinder.cs", "if (!prefer_skeleton_wrist"),
        (unity + "Editor/G1OfficialModelImporter.cs", "AssetDatabase.DeleteAsset"),
        (unity + "Editor/G1OfficialModelImporter.cs", "XDocument.Load"),
        (unity + "Editor/G1OfficialModelImporter.cs", "catch (Exception"),
        (unity + "Editor/G1MinkFkParityValidator.cs", "current_position - unity_baseline"),
        (unity + "G1Teleop/G1LiveTeleopTrace.cs", "trace.state_receiver = sender.state_receiver"),
        (unity + "G1Teleop/G1LiveTeleopTrace.cs", "new StreamWriter(trace_path, false"),
    ]
    evidence = [FindEvidence(path, token) for path, token in tokens]
    assert all(item["matches"] for item in evidence), "Source changed; review evidence again"
    authorization = []
    for path in sorted((ROOT / "config").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if "hardware_output_authorized" in payload:
            authorization.append({"path": path.relative_to(ROOT).as_posix(),
                                  "locked_boolean": payload["hardware_output_authorized"] is False})
    command = [sys.executable, "-B", "-m", "unittest",
               "backend.tests.test_unity_workspace_policy",
               "backend.tests.test_unity_display_mode_launcher", "-v"]
    with (OUTPUT / "unity_related_tests.log").open("w", encoding="utf-8") as stream:
        process = subprocess.run(command, cwd=ROOT, stdout=stream,
                                 stderr=subprocess.STDOUT, timeout=120)
    after = [row["path"] for row in inventory if
             hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest()
             != row["sha256"]]
    result = {
        "scope": "Source inspection, not C# compilation or Unity runtime reproduction",
        "indexed_files": len(inventory), "changed_before": changed,
        "changed_after": after, "source_evidence": evidence,
        "hardware_authorizations": authorization,
        "existing_test_exit_code": process.returncode,
        "tests_log": str(OUTPUT / "unity_related_tests.log"),
        "test_limit": "Workspace tests inspect strings; display test runs a copied PS1 in a temporary directory",
        "unity_launched": False, "g1_accessed": False,
    }
    (OUTPUT / "unity_review_checks.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return int(bool(changed or after or process.returncode or
                    not all(item["locked_boolean"] for item in authorization)))


if __name__ == "__main__":
    raise SystemExit(main())
