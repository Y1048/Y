"""Project-local CPython Embedded runtime contract."""
from __future__ import annotations

import os
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "runtime" / "python"
PYTHON_EXE = RUNTIME_ROOT / "python.exe"
SITE_PACKAGES = RUNTIME_ROOT / "Lib" / "site-packages"
EXPECTED_PYTHON = (3, 11, 9)


def is_embedded_interpreter() -> bool:
    try:
        return Path(sys.executable).resolve() == PYTHON_EXE.resolve()
    except OSError:
        return False


def require_embedded_interpreter() -> None:
    if os.name != "nt":
        raise RuntimeError("The bundled runtime is Windows x64 only.")
    if sys.version_info[:3] != EXPECTED_PYTHON or struct.calcsize("P") != 8:
        raise RuntimeError(
            f"Bundled Python {EXPECTED_PYTHON[0]}.{EXPECTED_PYTHON[1]}.{EXPECTED_PYTHON[2]} x64 required; "
            f"running {sys.version.split()[0]}."
        )
    if not is_embedded_interpreter():
        raise RuntimeError(
            "Use runtime\\python\\python.exe from this project; system Python and venvs are not supported."
        )
    if not (SITE_PACKAGES / "mujoco" / "__init__.py").is_file():
        raise RuntimeError("Bundled site-packages are incomplete.")


def child_environment(base=None):
    env = dict(os.environ if base is None else base)
    env["G1_BIMANUAL_ENGINE_ROOT"] = str(SITE_PACKAGES)
    return env


def python_command(script: Path, *args: str, unbuffered: bool = False):
    flags = ["-I"]
    if unbuffered:
        flags.append("-u")
    flags.append("-B")
    return [str(PYTHON_EXE), *flags, str(script), *map(str, args)]
