"""Validate the bundled CPython Embedded runtime before teleop startup."""
import argparse
import importlib
import hashlib
from importlib import metadata
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "runtime" / "python" / "python.exe"
MODULES = {"websocket-client": "websocket", "absl-py": "absl", "pyopengl": "OpenGL"}
EXPECTED_PYTHON = (3, 11, 9)
MANIFEST = ROOT / "runtime" / "python" / "RUNTIME_MANIFEST.json"


def runtime_manifest():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("schema") != "g1.embedded-python.runtime.v1":
        raise RuntimeError("Unsupported bundled runtime manifest")
    return data


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def requirements(path):
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name, separator, version = line.partition("==")
        if not separator or not name or not version:
            raise RuntimeError("Expected exact dependency pin: " + line)
        result[name] = version
    if not result:
        raise RuntimeError("Dependency list is empty")
    return result


def probe():
    errors = []
    if sys.version_info[:3] != EXPECTED_PYTHON or struct.calcsize("P") != 8:
        errors.append("Bundled Python 3.11.9 x64 required")
    try:
        if Path(sys.executable).resolve() != PYTHON.resolve():
            errors.append("Wrong interpreter: " + sys.executable)
    except OSError as error:
        errors.append("Interpreter path error: " + str(error))
    try:
        manifest = runtime_manifest()
        expected_pins = requirements(ROOT / "tools/requirements-teleop.txt")
        if manifest.get("python_version") != "3.11.9":
            errors.append("runtime manifest Python version mismatch")
        if manifest.get("architecture") != "win_amd64":
            errors.append("runtime manifest architecture mismatch")
        if manifest.get("packages") != {k.lower(): v for k, v in expected_pins.items()}:
            errors.append("runtime manifest package pins differ from requirements")
        for filename, expected_hash in manifest.get("core_sha256", {}).items():
            path = ROOT / "runtime" / "python" / filename
            if not path.is_file() or sha256(path) != expected_hash:
                errors.append("runtime core hash mismatch: " + filename)
    except Exception as error:
        errors.append("runtime manifest: " + type(error).__name__ + ": " + str(error))
        expected_pins = requirements(ROOT / "tools/requirements-teleop.txt")

    for name, expected in expected_pins.items():
        try:
            actual = metadata.version(name)
            if actual != expected:
                errors.append(name + ": expected " + expected + ", found " + actual)
            importlib.import_module(MODULES.get(name, name.replace("-", "_")))
        except Exception as error:
            errors.append(name + ": " + type(error).__name__ + ": " + str(error))
    try:
        import qpsolvers
        if "daqp" not in qpsolvers.available_solvers:
            errors.append("qpsolvers: DAQP backend unavailable")
    except Exception as error:
        errors.append("qpsolvers backend: " + type(error).__name__ + ": " + str(error))
    print(json.dumps(dict(python=sys.executable, errors=errors)), flush=True)
    return not errors


def validate(python=PYTHON):
    python = Path(python)
    if not python.is_file():
        return False
    command = [str(python), "-I", "-B", str(ROOT / "tools/g1_teleop_dependencies.py"), "--probe"]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )
        if result.returncode:
            print(result.stdout or result.stderr, flush=True)
            return False
        return True
    except (OSError, subprocess.TimeoutExpired) as error:
        print("[PORTABLE DEPENDENCIES] " + str(error), flush=True)
        return False


def ensure():
    if not validate(PYTHON):
        raise RuntimeError(
            "Bundled runtime is incomplete or corrupted. Restore runtime/python from the project package."
        )
    print("[PORTABLE DEPENDENCIES] Bundled Python and pinned imports passed.", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    if args.probe:
        return 0 if probe() else 1
    ensure()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print("[PORTABLE DEPENDENCIES FAILED] " + str(error), file=sys.stderr)
        raise SystemExit(1)
