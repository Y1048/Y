"""Developer-only builder for the committed CPython Embedded runtime.

Operator PCs must not run this script. They consume runtime/python as-is.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PARENT = ROOT / "runtime"
DEFAULT_OUTPUT = RUNTIME_PARENT / "python-rebuilt"
REQUIREMENTS = ROOT / "tools" / "requirements-teleop.txt"

PYTHON_VERSION = "3.11.9"
PYTHON_ARCH = "win_amd64"
ARCHIVE_NAME = "python-3.11.9-embeddable-amd64.zip"
ARCHIVE_URL = "https://www.python.org/ftp/python/3.11.9/" + ARCHIVE_NAME
ARCHIVE_SHA256 = "33b448f95fecb7c6f802157dbd5e6b40a2ad9bfc8b95ca634a06ba4073ad1ac0"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def requirement_pins() -> dict[str, str]:
    pins = {}
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name, marker, version = line.partition("==")
        if not marker or not name or not version:
            raise RuntimeError("Expected exact requirement pin: " + line)
        pins[name.lower()] = version
    return pins


def require_builder_python() -> None:
    if os.name != "nt" or sys.version_info[:2] != (3, 11) or struct.calcsize("P") != 8:
        raise RuntimeError("Build with Windows x64 Python 3.11 that has pip available.")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError("Builder Python must provide pip.")


def remove_generated_launchers(site_packages: Path) -> None:
    # pip --target creates .exe console wrappers with the builder interpreter's
    # absolute path embedded. The G1 runtime never uses them.
    shutil.rmtree(site_packages / "bin", ignore_errors=True)
    for record in site_packages.glob("*.dist-info/RECORD"):
        lines = record.read_text(encoding="utf-8").splitlines()
        lines = [
            line for line in lines
            if not line.replace("\\", "/").startswith("../../bin/")
        ]
        record.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    for cache in sorted(site_packages.rglob("__pycache__"), reverse=True):
        shutil.rmtree(cache, ignore_errors=True)
    for pattern in ("*.pyc", "*.pyo"):
        for file in site_packages.rglob(pattern):
            file.unlink(missing_ok=True)


def write_manifest(runtime: Path) -> None:
    core = {}
    for name in ("python.exe", "python311.dll", "python311.zip", "python311._pth"):
        core[name] = sha256_file(runtime / name)
    manifest = {
        "schema": "g1.embedded-python.runtime.v1",
        "python_version": PYTHON_VERSION,
        "architecture": PYTHON_ARCH,
        "source_url": ARCHIVE_URL,
        "source_archive_sha256": ARCHIVE_SHA256,
        "packages": requirement_pins(),
        "core_sha256": core,
    }
    (runtime / "RUNTIME_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_runtime(runtime: Path) -> None:
    command = [
        str(runtime / "python.exe"), "-I", "-B", "-c",
        (
            "import importlib.metadata as m;"
            "import numpy,scipy,mujoco,mink,qpsolvers,daqp,ruckig,websocket,websockets,OpenGL;"
            "assert mujoco.__version__=='3.12.0';"
            "assert 'daqp' in qpsolvers.available_solvers;"
            "print(m.version('numpy'),m.version('mujoco'),m.version('ruckig'))"
        ),
    ]
    subprocess.run(command, cwd=ROOT, check=True)


def build(output: Path) -> None:
    require_builder_python()
    output = output.resolve()
    if output.exists():
        raise RuntimeError(f"Output already exists: {output}")
    RUNTIME_PARENT.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="g1-embedded-build-") as temporary:
        temporary = Path(temporary)
        archive = temporary / ARCHIVE_NAME
        print("Downloading", ARCHIVE_URL)
        with urllib.request.urlopen(ARCHIVE_URL, timeout=60) as response, archive.open("wb") as target:
            shutil.copyfileobj(response, target)
        actual = sha256_file(archive)
        if actual != ARCHIVE_SHA256:
            raise RuntimeError(f"CPython archive SHA256 mismatch: {actual}")

        staging = temporary / "python"
        staging.mkdir()
        with zipfile.ZipFile(archive) as package:
            package.extractall(staging)
        (staging / "python311._pth").write_text(
            "python311.zip\n"
            ".\n"
            "Lib\n"
            "Lib\\site-packages\n"
            "..\\..\n"
            "..\\..\\tools\n"
            "..\\..\\MuJoCo_G1_Controller\\scripts\n"
            "..\\..\\hardware\\g1_arm_bridge\n",
            encoding="ascii",
            newline="\n",
        )
        site_packages = staging / "Lib" / "site-packages"
        site_packages.mkdir(parents=True)

        subprocess.run(
            [
                sys.executable, "-m", "pip", "install",
                "--disable-pip-version-check", "--no-compile",
                "--target", str(site_packages),
                "-r", str(REQUIREMENTS),
            ],
            cwd=ROOT,
            check=True,
        )
        remove_generated_launchers(site_packages)
        write_manifest(staging)
        validate_runtime(staging)
        shutil.copytree(staging, output)

    print("Built:", output)
    print("Files:", sum(1 for path in output.rglob("*") if path.is_file()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    build(args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print("BUILD EMBEDDED RUNTIME FAILED: " + str(error), file=sys.stderr)
        raise SystemExit(1)
