"""Persist the fixed local-frame rotation between Quest hand and G1 wrist."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_controller_status.json"
CALIBRATION_PATH = PROJECT_ROOT / "config" / "wrist_frame_calibration.json"
FREEZE_FLAG_PATH = PROJECT_ROOT / "logs" / "runtime" / "wrist_frame_calibration.freeze"


def _read_status() -> dict:
    if not STATUS_PATH.exists():
        raise RuntimeError(f"runtime status not found: {STATUS_PATH}")
    return json.loads(STATUS_PATH.read_text(encoding="utf-8"))


def main() -> int:
    FREEZE_FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_FLAG_PATH.write_text("freeze wrist orientation for frame calibration\n", encoding="utf-8")
    print("Wrist orientation FREEZE requested.")
    print("XYZ tracking and geometry redundancy remain active.")

    try:
        deadline = time.monotonic() + 5.0
        status = {}
        while time.monotonic() < deadline:
            status = _read_status()
            if bool(status.get("wrist_frame_calibration_freeze_active", False)):
                break
            time.sleep(0.10)
        else:
            raise RuntimeError(
                "controller did not enter wrist calibration freeze mode; restart the latest geometry teleop runtime"
            )

        if not (
            bool(status.get("input_valid", False))
            and bool(status.get("input_active", False))
            and bool(status.get("clutch_active", False))
        ):
            raise RuntimeError(
                "hand tracking is not actively engaged; engage first, then rerun calibration"
            )

        print("\nWrist orientation is now frozen.")
        print("Physically align the Quest hand to the desired G1 wrist/hand orientation.")
        print("The G1 wrist will not rotate to chase the Quest hand while this tool is active.")
        input("Keep both still, then press Enter to capture calibration... ")

        # Read a fresh status sample after the operator has aligned the frames.
        time.sleep(0.20)
        status = _read_status()
        if not bool(status.get("wrist_frame_calibration_freeze_active", False)):
            raise RuntimeError("wrist calibration freeze unexpectedly became inactive")

        hand = np.asarray(status.get("quest_hand_mapped_rotation_matrix"), dtype=float)
        g1 = np.asarray(status.get("g1_wrist_rotation_matrix"), dtype=float)
        if hand.shape != (3, 3) or g1.shape != (3, 3):
            raise RuntimeError(
                "rotation matrices are unavailable; keep geometry teleop actively engaged"
            )
        if not (np.all(np.isfinite(hand)) and np.all(np.isfinite(g1))):
            raise RuntimeError("rotation matrices contain non-finite values")

        # R_target = R_hand_mapped @ R_offset
        # therefore R_offset = R_hand_mapped^T @ R_g1 while the G1 wrist is
        # explicitly frozen and the physical frames are deliberately aligned.
        offset = hand.T @ g1
        u, _, vt = np.linalg.svd(offset)
        offset = u @ vt
        if np.linalg.det(offset) < 0.0:
            u[:, -1] *= -1.0
            offset = u @ vt

        payload = {
            "right_wrist": {
                "calibrated": True,
                "hand_to_g1_local_rotation": offset.tolist(),
            }
        }
        CALIBRATION_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print("\nSaved wrist frame calibration:")
        print(CALIBRATION_PATH)
        print(np.array2string(offset, precision=6, suppress_small=True))
        print("Restart MuJoCo/Unity so the saved frame offset is loaded.")
        return 0
    finally:
        try:
            FREEZE_FLAG_PATH.unlink()
        except FileNotFoundError:
            pass
        print("Wrist orientation FREEZE released.")


if __name__ == "__main__":
    raise SystemExit(main())
