"""Read-only preflight for the Quest -> Unity -> MuJoCo bimanual simulation lane."""
import argparse
import ast
import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATED = "3.12.0"
PRODUCTION_PORT = 5020
PARITY_FILES = [
    "MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py",
    "MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py",
    "MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py",
    "MuJoCo_G1_Controller/scripts/g1_bimanual_motion_policy.py",
    "MuJoCo_G1_Controller/scripts/g1_bimanual_return.py",
    "MuJoCo_G1_Controller/scripts/g1_bimanual_udp_cycle.py",
    "Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs",
    "Unity_G1_VR/Assets/Editor/G1SameSceneBimanualSetup.cs",
    "tools/START_BIMANUAL_UNITY_SIM.bat",
]
FORBIDDEN_IMPORTS = {"unitree_sdk2py", "rclpy", "cyclonedds", "paramiko"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check_runtime_scene(runtime_root):
    scene = (runtime_root / "Unity_G1_VR/Assets/Scenes/SampleScene.unity").read_text(
        encoding="utf-8")
    require("Assembly-CSharp::G1BimanualSimulationSender" in scene,
            "runtime SampleScene has no bimanual sender")
    for field in ("  useExistingScene: 1", "  armMode: 1", "  port: 5020"):
        require(field in scene, f"runtime SampleScene missing {field.strip()}")
    build = (runtime_root / "Unity_G1_VR/ProjectSettings/EditorBuildSettings.asset").read_text(
        encoding="utf-8")
    require("enabled: 1" in build and "Assets/Scenes/SampleScene.unity" in build,
            "runtime SampleScene is not the enabled build scene")


def check_source_installer():
    installer = (ROOT / "Unity_G1_VR/Assets/Editor/G1SameSceneBimanualSetup.cs").read_text(
        encoding="utf-8")
    require('MenuItem("G1 Teleop/Arms/Use Both Arms (Simulation)")' in installer,
            "source bimanual scene installer is missing")
    require("dual.useExistingScene = true;" in installer and
            "ArmMode.BimanualSimulation" in installer,
            "source bimanual installer is incomplete")


def check_no_hardware_imports(root):
    scripts = [
        "g1_bimanual_runtime.py", "g1_bimanual_sim.py",
        "g1_bimanual_unity_sim.py", "g1_bimanual_motion_policy.py",
        "g1_bimanual_return.py", "g1_bimanual_udp_cycle.py",
    ]
    for name in scripts:
        path = root / "MuJoCo_G1_Controller/scripts" / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        blocked = imported & FORBIDDEN_IMPORTS
        require(not blocked, f"{name} imports hardware/remote modules: {blocked}")


def check_parity(runtime_root):
    mismatches = []
    for relative in PARITY_FILES:
        source = ROOT / relative
        runtime = runtime_root / relative
        if not source.is_file() or not runtime.is_file():
            mismatches.append((relative, "missing"))
        elif sha256(source) != sha256(runtime):
            mismatches.append((relative, "sha256"))
    require(not mismatches, "source/runtime parity failed: " + repr(mismatches))
    return len(PARITY_FILES)


def check_port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as error:
            raise AssertionError(f"UDP {port} is already in use: {error}") from error
def validate_engine(engine_root):
    runtime = ROOT / "MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py"
    command = [
        sys.executable, "-B", str(runtime),
        "--engine-root", str(engine_root), "--validate-only",
    ]
    completed = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, timeout=30)
    require(completed.returncode == 0,
            "validated engine check failed: " + completed.stdout + completed.stderr)
    rows = [line for line in completed.stdout.splitlines()
            if line.startswith("{") and line.endswith("}")]
    require(rows, "validated engine metadata was not emitted")
    metadata = json.loads(rows[-1])
    require(metadata["simulation_only"] is True, "simulation_only provenance missing")
    require(metadata["hardware_output_authorized"] is False,
            "hardware output must remain unauthorized")
    require(metadata["mujoco_version"] == VALIDATED, "wrong MuJoCo package")
    require(metadata["mujoco_native_version"] == VALIDATED, "wrong MuJoCo native")
    return metadata


def main(argv=None):
    default_runtime = Path(os.environ.get(
        "G1_BIMANUAL_RUNTIME_ROOT",
        str(Path.home() / "Desktop/G1_Teleop_Project")))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, default=default_runtime)
    parser.add_argument("--engine-root", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)
    runtime_root = args.runtime_root.expanduser().resolve()
    engine_root = (args.engine_root or
        runtime_root / "logs/diagnostics/mujoco_versions" / VALIDATED).resolve()
    checks = []
    try:
        require(runtime_root.is_dir(), f"runtime root missing: {runtime_root}")
        checks.append("runtime_root")
        require((engine_root / "mujoco/__init__.py").is_file(),
                f"MuJoCo {VALIDATED} engine root missing: {engine_root}")
        checks.append("engine_root")
        check_source_installer()
        checks.append("source_bimanual_installer")
        check_runtime_scene(runtime_root)
        checks.append("runtime_sample_scene_bimanual")
        parity_count = check_parity(runtime_root)
        checks.append(f"source_runtime_sha256:{parity_count}")
        check_no_hardware_imports(ROOT)
        checks.append("no_hardware_imports")
        check_port_free(PRODUCTION_PORT)
        checks.append("udp_5020_free")
        metadata = validate_engine(engine_root)
        checks.append("mujoco_3.12_validate")
        result = dict(
            schema="g1.bimanual.preflight.v1", result="PASS",
            simulation_only=True, hardware_output_authorized=False,
            source_root=str(ROOT), runtime_root=str(runtime_root),
            engine_root=str(engine_root), checks=checks,
            mujoco_module=metadata["mujoco_module"])
    except (AssertionError, OSError, subprocess.SubprocessError, ValueError) as error:
        result = dict(
            schema="g1.bimanual.preflight.v1", result="FAIL",
            simulation_only=True, hardware_output_authorized=False,
            source_root=str(ROOT), runtime_root=str(runtime_root),
            engine_root=str(engine_root), checks=checks, error=str(error))
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, indent=2, allow_nan=False))
    print("READY FOR QUEST TEST" if result["result"] == "PASS"
          else "NOT READY FOR QUEST TEST")
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
