"""Snapshot selected installed IK license evidence without importing controllers.

This is a scoped inventory, not a complete SBOM or legal approval.
"""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def collect(dist, label, output):
    package = {
        "label": label,
        "name": dist.metadata["Name"],
        "version": dist.version,
        "license_expression": dist.metadata.get("License-Expression"),
        "license_field": dist.metadata.get("License"),
        "license_classifiers": [x for x in dist.metadata.get_all("Classifier", [])
                                if x.startswith("License ::")],
        "requires_dist": dist.requires or [],
        "license_files": [],
    }
    for item in dist.files or []:
        if not re.search(r"license|licence|notice|copying", str(item), re.I):
            continue
        source = Path(dist.locate_file(item))
        if not source.is_file():
            continue
        data = source.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        relative = Path("notices") / label / (digest[:16] + "_" + source.name)
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        package["license_files"].append({
            "installed_path": str(source), "copy": relative.as_posix(),
            "sha256": digest, "size_bytes": len(data),
        })
    package["evidence_missing"] = not package["license_files"]
    return package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mujoco-overlay", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        "schema": "g1.ik.license_inventory.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.executable,
        "scope": "selected Windows IK packages and optional MuJoCo overlay; not transitive closure",
        "release_approved": False, "packages": [], "missing_packages": [],
    }
    for name in ("mink", "mujoco", "qpsolvers", "daqp", "numpy", "scipy", "ruckig"):
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            report["missing_packages"].append(name)
            continue
        report["packages"].append(collect(dist, name, args.output))
    if args.mujoco_overlay:
        matches = [d for d in metadata.distributions(path=[str(args.mujoco_overlay)])
                   if d.metadata["Name"].lower() == "mujoco"]
        if len(matches) != 1:
            raise RuntimeError("Expected exactly one MuJoCo distribution in overlay")
        report["packages"].append(collect(matches[0], "mujoco-live-overlay", args.output))
    target = args.output / "inventory.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"inventory": str(target), "packages": len(report["packages"]),
                      "missing_packages": report["missing_packages"], "release_approved": False}))
    if report["missing_packages"] or any(p["evidence_missing"] for p in report["packages"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
