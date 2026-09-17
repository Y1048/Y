"""Isolated MuJoCo 3.12 simulation. Never emits live hardware provenance."""

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
ENGINE_ROOT = ROOT / "logs/diagnostics/mujoco_versions/3.12.0"


def LoadEngine():
    if "mujoco" in sys.modules:
        raise RuntimeError("Start a fresh Python process for isolated MuJoCo")
    if not (ENGINE_ROOT / "mujoco/__init__.py").is_file():
        raise RuntimeError(f"Isolated MuJoCo 3.12 is missing: {ENGINE_ROOT}")
    sys.path.insert(0, str(ENGINE_ROOT))
    import mujoco
    if mujoco.__version__ != "3.12.0" or not Path(mujoco.__file__).resolve().is_relative_to(ENGINE_ROOT.resolve()):
        raise RuntimeError("Unexpected MuJoCo version or module path")
    return mujoco


def MarkSimulation(factory):
    def BuildPacket(*args, **kwargs):
        packet = dict(factory(*args, **kwargs))
        packet["command_provenance"] = "simulation_only"
        packet["simulation_only"] = True
        packet["hardware_output_authorized"] = False
        packet["simulation_engine"] = "mujoco-3.12.0"
        return packet
    return BuildPacket


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ik-solver", choices=("vanilla", "hierarchical"), default="vanilla")
    parser.add_argument("--collision-profile", choices=("mink-default",), default="mink-default")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--seed-from-environment", action="store_true")
    parser.add_argument("--initial-lowstate-seed", type=Path)
    parser.add_argument("--initial-lowstate-session")
    parser.add_argument("--initial-state-check-only", type=Path)
    parser.add_argument("--right-arm-csv", type=Path)
    args = parser.parse_args()
    if args.seed_from_environment:
        if args.initial_lowstate_seed or args.initial_lowstate_session:
            parser.error("Choose explicit seed arguments or environment, not both")
        args.initial_lowstate_seed = os.environ.get("G1_MINK_INITIAL_SEED")
        args.initial_lowstate_session = os.environ.get("G1_MINK_INITIAL_SESSION")
        if not args.initial_lowstate_seed or not args.initial_lowstate_session:
            parser.error("Both G1_MINK_INITIAL_SEED and G1_MINK_INITIAL_SESSION are required")
    if bool(args.initial_lowstate_seed) != bool(args.initial_lowstate_session):
        parser.error("Seed and session must be supplied together")
    engine = LoadEngine()
    import run_mink_g1_right_arm_prototype as base
    import run_mink_g1_right_arm_virtual_center_live as controller
    print(f"SIMULATION ONLY | MuJoCo {engine.__version__} | IK {args.ik_solver}")
    print(f"Engine: {engine.__file__}")
    print("Hardware relay rejects simulation_only provenance. No SDK or DDS.")
    if args.validate_only:
        print("[PASS] Isolated engine and controller imports validated; no runtime started.")
        return 0
    base._state_packet = MarkSimulation(base._state_packet)
    sys.argv = [sys.argv[0], "--ik-solver", args.ik_solver,
                "--collision-profile", args.collision_profile]
    if args.initial_lowstate_seed:
        sys.argv += ["--initial-lowstate-seed", str(args.initial_lowstate_seed),
                     "--initial-lowstate-session", args.initial_lowstate_session]
    if args.initial_state_check_only:
        sys.argv += ["--initial-state-check-only", str(args.initial_state_check_only)]
    if args.right_arm_csv:
        sys.argv += ["--right-arm-csv", str(args.right_arm_csv)]
    controller.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
