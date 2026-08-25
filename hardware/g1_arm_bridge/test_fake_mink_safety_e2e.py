#!/usr/bin/env python3
"""End-to-end offline process test for fake Mink targets through Safety Gate."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "hardware" / "g1_arm_bridge"
RECEIVER = BRIDGE / "mink_target_dry_run.py"
GENERATOR = BRIDGE / "generate_fake_mink_targets.py"


def main() -> int:
    print("G1 fake Mink -> Safety Gate E2E test")
    print("------------------------------------")
    print("Unity:       NONE")
    print("MuJoCo:      NONE")
    print("Unitree SDK: NONE")
    print("DDS:         NONE")
    print("Robot cmd:   NONE")

    receiver = subprocess.Popen(
        [sys.executable, str(RECEIVER)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        time.sleep(0.35)
        generator = subprocess.run(
            [sys.executable, str(GENERATOR), "--hz", "60", "--duration", "4"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        print(generator.stdout, end="")
        if generator.returncode != 0:
            print(generator.stderr, end="")
            print("[FAIL] Synthetic target generator failed.")
            return 2

        try:
            output, _ = receiver.communicate(timeout=3.0)
        except subprocess.TimeoutExpired:
            receiver.kill()
            output, _ = receiver.communicate()
            print(output, end="")
            print("[FAIL] Safety dry-run did not stale-stop after input ended.")
            return 3

        print(output, end="")
        required = (
            "[SYNC] Initial simulated measured pose captured from Mink.",
            "[ALLOW]",
            "rate_limited=",
            "[PASS] Mink stream stale",
            "no command candidate produced",
        )
        missing = [marker for marker in required if marker not in output]
        if receiver.returncode != 0 or missing:
            print(f"[FAIL] Safety receiver return code: {receiver.returncode}")
            if missing:
                print("[FAIL] Missing output markers: " + ", ".join(missing))
            return 4

        print("[PASS] Fake Mink UDP -> Safety Gate -> stale-stop E2E test passed.")
        print("[PASS] No Unitree/DDS/robot command path existed during this test.")
        return 0
    finally:
        if receiver.poll() is None:
            receiver.kill()
            receiver.wait(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
