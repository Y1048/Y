"""Run an explicit allowlist of SDK-free tests; never run a robot binary.

Linux/WSL examples:
  python3 verify_regular_handoff_offline.py --output /tmp/g1-offline.json
  python3 verify_regular_handoff_offline.py --sanitizers
  python3 verify_regular_handoff_offline.py --compiler clang++
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
PYTHON_TESTS = ["test_analyze_pd_sweep", "test_no_overlap_runtime",
                "test_persistent_pd_runtime", "test_controller_handoff_offline",
                "test_native_cycle_build_contract"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--sanitizers", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = {"schema": "g1.regular.offline.v1", "compiler": args.compiler,
              "sanitizers": args.sanitizers, "physical_validation": False,
              "sdk_or_dds_initialized": False, "commands": [], "source_sha256": {}}
    names = ["twist2_mink_cycle_trial.cpp", "regular_handoff_safety.hpp",
             "verified_regular_handoff.hpp", "writer_frame.hpp", "periodic_csv.hpp",
             "test_pd_gain_options.cpp", "test_pd_small_signal_trial.cpp", "test_writer_frame.cpp",
             "test_verified_regular_handoff.cpp", "test_regular_handoff_safety.cpp",
             "test_periodic_csv_failure.cpp", "native_vr_build/CMakeLists.txt",
             "offline_handoff_tests/CMakeLists.txt", "verify_regular_handoff_offline.py"]
    names += [name + ".py" for name in PYTHON_TESTS]
    for name in names:
        report["source_sha256"][name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    env = os.environ.copy()
    env["CXX"] = args.compiler
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["G1_OFFLINE_CXXFLAGS"] = ("-fsanitize=address,undefined -fno-omit-frame-pointer -fno-pie -no-pie"
                                 if args.sanitizers else "")

    def run(command, timeout=60):
        result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                capture_output=True, timeout=timeout)
        report["commands"].append({"argv": command, "returncode": result.returncode,
                                   "stdout": result.stdout, "stderr": result.stderr})
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        if result.returncode:
            raise RuntimeError(f"offline command failed: {command[0]} ({result.returncode})")

    status = 1
    try:
        for tool in (args.compiler, "cmake", "ctest"):
            if shutil.which(tool) is None:
                raise RuntimeError(f"missing required offline tool: {tool}")
        run([args.compiler, "--version"])
        run(["cmake", "--version"])
        with tempfile.TemporaryDirectory(prefix="g1-regular-offline-") as folder:
            build = Path(folder)
            run(["cmake", "-S", str(ROOT / "offline_handoff_tests"), "-B", str(build),
                 f"-DCMAKE_CXX_COMPILER={args.compiler}", "-DCMAKE_BUILD_TYPE=Debug",
                 f"-DG1_OFFLINE_SANITIZERS={'ON' if args.sanitizers else 'OFF'}"])
            run(["cmake", "--build", str(build), "--parallel", "2"])
            run(["ctest", "--test-dir", str(build), "--output-on-failure"])
            run([sys.executable, "-B", "-m", "unittest", "-v", *PYTHON_TESTS])
            # Explicit memory-only executable, not a DDS publisher.
            for _ in range(20):
                run([str(build / "test_writer_frame")], timeout=15)
        status = 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        report["error"] = str(error)
        print(str(error), file=sys.stderr)
    report["passed"] = status == 0
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("PASS offline checks (NOT physical validation)" if status == 0 else "FAIL offline checks")
    return status


if __name__ == "__main__":
    sys.exit(main())
