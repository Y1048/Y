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
        return {}
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _actively_engaged(status: dict) -> bool:
    return bool(
        status.get("input_valid", False)
        and status.get("input_active", False)
        and status.get("clutch_active", False)
    )


def main() -> int:
    FREEZE_FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_FLAG_PATH.write_text(
        "freeze wrist orientation for frame calibration\n",
        encoding="utf-8",
    )
    print("Wrist orientation FREEZE requested BEFORE engagement.")
    print("Now engage the Quest hand in Unity.")
    print("The first active control cycle will keep the G1 wrist orientation frozen.")
    print("XYZ tracking and geometry redundancy remain active.\n")

    try:
        deadline = time.monotonic() + 60.0
        status: dict = {}
        announced_active = False
        while time.monotonic() < deadline:
            status = _read_status()
            if _actively_engaged(status) and not announced_active:
                print("Hand engagement detected; waiting for controller freeze confirmation...")
                announced_active = True
            if (
                _actively_engaged(status)
                and bool(status.get("wrist_frame_calibration_freeze_active", False))
            ):
                break
            time.sleep(0.10)
        else:
            raise RuntimeError(
                "timed out waiting for active hand engagement with wrist freeze; "
                "keep the latest geometry teleop runtime running and engage within 60 seconds"
            )

        print("Wrist orientation is now frozen before Quest rotation can drive the G1 wrist.")
        print("Physically align the Quest hand to the desired G1 wrist/hand orientation.")
        print("The G1 wrist will not rotate to chase the Quest hand while this tool is active.")
        input("Keep both still, then press Enter to capture calibration... ")

        time.sleep(0.25)
        status = _read_status()
        if not _actively_engaged(status):
            raise RuntimeError("hand tracking disengaged before calibration capture")
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

        # R_target = R_hand_mapped @ R_offset.
        # During capture the G1 wrist is frozen before Quest orientation control,
        # so the measured fixed local-frame relation is not contaminated by the
        # controller chasing the operator's hand.
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
        CALIBRATION_PATH.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
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
