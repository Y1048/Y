"""G1 오른팔 모델, 관절 인덱스, 좌표 변환을 한곳에 모은 공통 모듈.

이 파일은 IK를 직접 풀지 않는다. Mink 제어기와 카메라 회귀 검사용 기존 제어기가
동일한 모델/관절/프레임 정의를 사용하도록 경계를 제공한다.
"""

from __future__ import annotations

import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop import add_g1_d435i_camera  # noqa: E402


G1_DIR = ROOT / "external" / "unitree_mujoco" / "unitree_robots" / "g1"
G1_XML = G1_DIR / "g1_29dof.xml"
DEMO_XML = G1_DIR / "_generated_g1_right_arm_udp_ik.xml"
HARDWARE_INITIAL_STATE_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_hardware_initial_state.json"

LEFT_ARM_READY_DEGREES = np.array([10.0, 22.0, 0.0, 55.0, 0.0, 0.0, 0.0])
DEFAULT_RIGHT_ARM_READY_DEGREES = np.array([10.0, -22.0, 0.0, 55.0, 0.0, 0.0, 0.0])


def _load_hardware_initial_right_arm_degrees() -> np.ndarray | None:
    if os.environ.get("G1_USE_HARDWARE_INITIAL_STATE") != "1":
        return None
    try:
        payload = json.loads(HARDWARE_INITIAL_STATE_PATH.read_text(encoding="utf-8"))
        joints = np.asarray(payload["right_arm_q_rad"], dtype=float)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Hardware initial state requested but invalid: {HARDWARE_INITIAL_STATE_PATH}"
        ) from exc
    if joints.shape != (7,) or not np.all(np.isfinite(joints)):
        raise RuntimeError("Hardware initial right-arm state must contain 7 finite joint values")
    print(
        "[SYNC] Mink initial right-arm posture loaded from G1 LowState: "
        + ", ".join(f"{value:.2f}" for value in np.degrees(joints))
        + " deg"
    )
    return np.degrees(joints)


RIGHT_ARM_READY_DEGREES = (
    _load_hardware_initial_right_arm_degrees()
    if os.environ.get("G1_USE_HARDWARE_INITIAL_STATE") == "1"
    else DEFAULT_RIGHT_ARM_READY_DEGREES.copy()
)

RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES = {
    "right_elbow_joint": (5.0, 120.0),
}

# Unity 작업자 좌표계: +X 오른쪽, +Y 위, +Z 앞.
# MuJoCo G1 좌표계: +X 앞, +Y 왼쪽, +Z 위.
# 위치와 회전에 같은 기저 변환을 사용해 축 변환이 두 번 적용되지 않게 한다.
OPERATOR_TO_ROBOT_BASIS = np.array(
    [
        [0.0, 0.0, 1.0],
        [-1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ],
    dtype=float,
)

RIGHT_ARM_JOINTS = [
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
]

LEFT_ARM_JOINTS = [
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
]

RIGHT_ARM_BODY_NAMES = {
    "right_shoulder_pitch_link",
    "right_shoulder_roll_link",
    "right_shoulder_yaw_link",
    "right_elbow_link",
    "right_wrist_roll_link",
    "right_wrist_pitch_link",
    "right_wrist_yaw_link",
    "inspection_tool_tip_body",
}

SCENES = {
    "control": {
        "panel_pos": (0.46, 0.0, 1.08),
        "panel_size": (0.025, 0.48, 0.34),
        "target_pos": (0.42, -0.16, 1.05),
        # Place the right-hand task slightly outboard.  Offline replay of the
        # live inspection wrist orientation kept the elbow near 20 degrees
        # here instead of collapsing onto its 5 degree extension limit.
        "inspection_target_pos": (0.435, -0.28, 1.05),
    },
    "camera_validation": {
        "panel_pos": (0.58, 0.0, 0.78),
        "panel_size": (0.025, 0.20, 0.16),
        "target_pos": (0.51, -0.10, 0.86),
    },
}


def find_body(element: ET.Element, name: str) -> ET.Element | None:
    if element.tag == "body" and element.get("name") == name:
        return element
    for child in element:
        found = find_body(child, name)
        if found is not None:
            return found
    return None


def make_demo_xml(scene_name: str = "control") -> None:
    """Generate the fixed-base G1 simulation model used by teleoperation."""
    if scene_name not in SCENES:
        raise ValueError(f"unknown scene: {scene_name}")
    scene = SCENES[scene_name]

    tree = ET.parse(G1_XML)
    root = tree.getroot()
    worldbody = root.find("worldbody")
    if worldbody is None:
        raise RuntimeError("worldbody missing from G1 model")
    robot_body = worldbody.find("body")
    if robot_body is None:
        raise RuntimeError("G1 root body missing from model")

    for joint in list(robot_body.findall("freejoint")):
        robot_body.remove(joint)
    robot_body.set("pos", "0 0 0.78")
    add_g1_d435i_camera(robot_body)

    option = root.find("option")
    if option is None:
        option = ET.SubElement(root, "option")
    option.set("gravity", "0 0 0")

    ET.SubElement(
        worldbody,
        "light",
        {"pos": "0 -3 4", "dir": "0 1 -1", "diffuse": "0.9 0.9 0.9"},
    )
    ET.SubElement(
        worldbody,
        "light",
        {"pos": "0 3 3", "dir": "0 -1 -1", "diffuse": "0.5 0.5 0.5"},
    )
    ET.SubElement(
        worldbody,
        "geom",
        {
            "name": "demo_floor",
            "type": "plane",
            "size": "4 4 0.05",
            "rgba": "0.74 0.82 0.88 1",
            "contype": "0",
            "conaffinity": "0",
        },
    )
    inspection_target = ET.SubElement(
        worldbody,
        "body",
        {
            "name": "inspection_demo_target",
            "pos": " ".join(
                str(value) for value in scene.get(
                    "inspection_target_pos", scene["target_pos"]
                )
            ),
        },
    )
    ET.SubElement(
        inspection_target,
        "geom",
        {
            "name": "inspection_demo_target_marker",
            "type": "sphere",
            "size": "0.045",
            "rgba": "0.05 0.65 1.0 0.75",
            "contype": "0",
            "conaffinity": "0",
        },
    )
    ET.SubElement(
        worldbody,
        "geom",
        {
            "name": "inspection_panel",
            "type": "box",
            "pos": " ".join(str(value) for value in scene["panel_pos"]),
            "size": " ".join(str(value) for value in scene["panel_size"]),
            "rgba": "0.16 0.18 0.20 1",
            "contype": "0",
            "conaffinity": "0",
        },
    )
    ET.SubElement(
        worldbody,
        "body",
        {
            "name": "udp_target",
            "mocap": "true",
            "pos": " ".join(str(value) for value in scene["target_pos"]),
        },
    ).append(
        ET.Element(
            "geom",
            {
                "type": "sphere",
                "size": "0.035",
                "rgba": "0.05 1.0 0.10 1",
                "contype": "0",
                "conaffinity": "0",
            },
        )
    )

    right_wrist = find_body(robot_body, "right_wrist_yaw_link")
    if right_wrist is not None:
        ET.SubElement(
            right_wrist,
            "body",
            {"name": "inspection_tool_tip_body", "pos": "0.105 0.029 0.200"},
        ).append(
            ET.Element(
                "geom",
                {
                    "name": "inspection_tool_tip",
                    "type": "sphere",
                    "size": "0.035",
                    "rgba": "0.9 0.18 0.08 1",
                    "density": "0",
                    "contype": "0",
                    "conaffinity": "0",
                },
            )
        )
        ET.SubElement(
            right_wrist,
            "geom",
            {
                "name": "inspection_tool_grip",
                "type": "cylinder",
                "pos": "0.105 0.029 0.040",
                "size": "0.017 0.05",
                "rgba": "0.05 0.05 0.05 1",
                "density": "0",
                "contype": "0",
                "conaffinity": "0",
            },
        )
        ET.SubElement(
            right_wrist,
            "geom",
            {
                "name": "inspection_tool_probe",
                "type": "cylinder",
                "pos": "0.105 0.029 0.145",
                "size": "0.010 0.055",
                "rgba": "0.18 0.20 0.22 1",
                "density": "0",
                "contype": "0",
                "conaffinity": "0",
            },
        )

    tree.write(DEMO_XML, encoding="unicode")


def joint_qpos_addr(model: mujoco.MjModel, joint_name: str) -> int:
    joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
    if joint_id < 0:
        raise RuntimeError(f"MuJoCo joint not found: {joint_name}")
    return int(model.jnt_qposadr[joint_id])


def set_joint(model: mujoco.MjModel, data: mujoco.MjData, joint_name: str, value: float) -> None:
    data.qpos[joint_qpos_addr(model, joint_name)] = value


def clamp_joint_angles(model: mujoco.MjModel, data: mujoco.MjData, joint_names: list[str]) -> None:
    for name in joint_names:
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if joint_id < 0:
            raise RuntimeError(f"MuJoCo joint not found: {name}")
        adr = int(model.jnt_qposadr[joint_id])
        if bool(model.jnt_limited[joint_id]):
            low, high = model.jnt_range[joint_id]
            data.qpos[adr] = np.clip(data.qpos[adr], low, high)
        if name in RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES:
            low_deg, high_deg = RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES[name]
            data.qpos[adr] = np.clip(
                data.qpos[adr], math.radians(low_deg), math.radians(high_deg)
            )


def get_body_id(model: mujoco.MjModel, body_name: str) -> int:
    body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
    if body_id < 0:
        raise RuntimeError(f"MuJoCo body not found: {body_name}")
    return int(body_id)


def normalize_quaternion_xyzw(quaternion: np.ndarray) -> np.ndarray:
    quaternion = np.asarray(quaternion, dtype=float)
    norm = float(np.linalg.norm(quaternion))
    if norm < 1e-8:
        return np.array([0.0, 0.0, 0.0, 1.0])
    return quaternion / norm


def quaternion_xyzw_to_matrix(quaternion: np.ndarray) -> np.ndarray:
    x_value, y_value, z_value, w_value = normalize_quaternion_xyzw(quaternion)
    return np.array(
        [
            [
                1.0 - 2.0 * (y_value * y_value + z_value * z_value),
                2.0 * (x_value * y_value - z_value * w_value),
                2.0 * (x_value * z_value + y_value * w_value),
            ],
            [
                2.0 * (x_value * y_value + z_value * w_value),
                1.0 - 2.0 * (x_value * x_value + z_value * z_value),
                2.0 * (y_value * z_value - x_value * w_value),
            ],
            [
                2.0 * (x_value * z_value - y_value * w_value),
                2.0 * (y_value * z_value + x_value * w_value),
                1.0 - 2.0 * (x_value * x_value + y_value * y_value),
            ],
        ],
        dtype=float,
    )


def operator_rotation_to_robot_matrix(operator_quaternion: np.ndarray) -> np.ndarray:
    operator_rotation = quaternion_xyzw_to_matrix(operator_quaternion)
    return OPERATOR_TO_ROBOT_BASIS @ operator_rotation @ OPERATOR_TO_ROBOT_BASIS.T
