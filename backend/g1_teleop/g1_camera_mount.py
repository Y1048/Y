"""G1 head-camera geometry shared by simulation and deployment checks."""

from __future__ import annotations

import xml.etree.ElementTree as ET


G1_D435I_CAMERA_NAME = "g1_d435_color"
G1_D435I_PARENT_LINK = "torso_link"
G1_D435I_POSITION_M = (0.0576235, 0.01753, 0.42987)
G1_D435I_PITCH_RAD = 0.8307767239493009
G1_D435I_VERTICAL_FOV_DEG = 42.5

# Unitree's Isaac Lab camera configuration attaches the sensor under d435_link
# with this WXYZ rotation and interprets its axes using the ROS optical-camera
# convention (+Z forward, -Y up).
G1_D435I_ISAACLAB_ROS_QUAT_WXYZ = (0.5, -0.5, 0.5, -0.5)

# MuJoCo cameras look along local -Z with local +Y up. This quaternion converts
# the official Isaac Lab ROS optical axes to MuJoCo camera axes after applying
# the fixed d435_joint pitch above.
G1_D435I_MUJOCO_QUAT_WXYZ = (
    0.65925248,
    0.25570719,
    -0.25570719,
    -0.65925248,
)


def _find_body(element: ET.Element, name: str) -> ET.Element | None:
    if element.tag == "body" and element.get("name") == name:
        return element
    for child in element:
        body = _find_body(child, name)
        if body is not None:
            return body
    return None


def add_g1_d435i_camera(robot_body: ET.Element) -> ET.Element:
    """Attach a MuJoCo camera at the official G1 d435_joint transform."""
    torso = _find_body(robot_body, G1_D435I_PARENT_LINK)
    if torso is None:
        raise ValueError(f"G1 body not found: {G1_D435I_PARENT_LINK}")

    existing = torso.find(f"camera[@name='{G1_D435I_CAMERA_NAME}']")
    if existing is not None:
        return existing

    return ET.SubElement(
        torso,
        "camera",
        {
            "name": G1_D435I_CAMERA_NAME,
            "mode": "fixed",
            "pos": " ".join(f"{value:.9g}" for value in G1_D435I_POSITION_M),
            "quat": " ".join(f"{value:.9g}" for value in G1_D435I_MUJOCO_QUAT_WXYZ),
            "fovy": f"{G1_D435I_VERTICAL_FOV_DEG:.6g}",
        },
    )
