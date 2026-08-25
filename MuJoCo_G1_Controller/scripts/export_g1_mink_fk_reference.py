"""Export MuJoCo right_wrist_yaw FK samples for Unity parity validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g1_right_arm_common as g1  # noqa: E402


OUTPUT_PATH = g1.PROJECT_ROOT / "logs" / "runtime" / "g1_mink_fk_reference.json"

SAMPLES_DEG = [
    ("ready", [10.0, -22.0, 0.0, 55.0, 0.0, 0.0, 0.0]),
    ("shoulder_elbow", [24.0, -10.0, 18.0, 72.0, 0.0, 0.0, 0.0]),
    ("wrist_rotation", [10.0, -22.0, 0.0, 55.0, 32.0, -24.0, 38.0]),
    ("mixed", [-8.0, -34.0, -28.0, 46.0, -26.0, 21.0, -31.0]),
]


def mujoco_to_unity_delta(delta: np.ndarray) -> np.ndarray:
    # MuJoCo +X forward, +Y left, +Z up -> Unity +X right, +Y up, +Z forward.
    return np.array([-delta[1], delta[2], delta[0]], dtype=float)


def main() -> None:
    g1.make_demo_xml("control")
    model = mujoco.MjModel.from_xml_path(str(g1.DEMO_XML))
    data = mujoco.MjData(model)
    wrist_body = g1.get_body_id(model, "right_wrist_yaw_link")

    output_samples: list[dict] = []
    baseline_position: np.ndarray | None = None

    for sample_name, right_q_deg in SAMPLES_DEG:
        data.qpos[:] = model.qpos0.copy()
        for joint_name, value_deg in zip(g1.LEFT_ARM_JOINTS, g1.LEFT_ARM_READY_DEGREES):
            g1.set_joint(model, data, joint_name, float(np.radians(value_deg)))
        for joint_name, value_deg in zip(g1.RIGHT_ARM_JOINTS, right_q_deg):
            g1.set_joint(model, data, joint_name, float(np.radians(value_deg)))
        mujoco.mj_forward(model, data)

        wrist_position = data.xpos[wrist_body].copy()
        if baseline_position is None:
            baseline_position = wrist_position.copy()
        unity_delta = mujoco_to_unity_delta(wrist_position - baseline_position)

        output_samples.append(
            {
                "name": sample_name,
                "right_arm_q_rad": np.radians(np.asarray(right_q_deg, dtype=float)).tolist(),
                "unity_wrist_delta_m": unity_delta.tolist(),
            }
        )

    payload = {
        "frame": "right_wrist_yaw_link",
        "tolerance_m": 0.002,
        "samples": output_samples,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[PASS] Wrote MuJoCo wrist-yaw FK reference: {OUTPUT_PATH}")
    for sample in output_samples:
        print(
            "       "
            + sample["name"]
            + " delta[m]="
            + ", ".join(f"{value:+.5f}" for value in sample["unity_wrist_delta_m"])
        )


if __name__ == "__main__":
    main()
