"""Persist the fixed local-frame rotation between Quest hand and G1 wrist."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_controller_status.json"
CALIBRATION_PATH = PROJECT_ROOT / "config" / "wrist_frame_calibration.json"


def main() -> int:
    if not STATUS_PATH.exists():
        raise RuntimeError(f"runtime status not found: {STATUS_PATH}")
    status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    hand = np.asarray(status.get("quest_hand_mapped_rotation_matrix"), dtype=float)
    g1 = np.asarray(status.get("g1_wrist_rotation_matrix"), dtype=float)
    if hand.shape != (3, 3) or g1.shape != (3, 3):
        raise RuntimeError(
            "rotation matrices are unavailable; run geometry teleop with valid hand tracking first"
        )
    if not (np.all(np.isfinite(hand)) and np.all(np.isfinite(g1))):
        raise RuntimeError("rotation matrices contain non-finite values")

    # R_target = R_hand_mapped @ R_offset
    # therefore R_offset = R_hand_mapped^T @ R_g1 when the two physical frames
    # are deliberately aligned during calibration.
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
    print("Saved wrist frame calibration:")
    print(CALIBRATION_PATH)
    print(np.array2string(offset, precision=6, suppress_small=True))
    print("Restart MuJoCo/Unity so the saved frame offset is loaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
