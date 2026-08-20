"""Build camera sources without leaking hardware details into teleoperation code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .camera import MuJoCoHeadCameraSource, RealSenseD435iSource


SUPPORTED_CAMERA_SCHEMA = "g1.teleop.camera.v1"


def load_camera_profile(path: str | Path) -> dict[str, Any]:
    profile = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(profile, dict) or profile.get("schema") != SUPPORTED_CAMERA_SCHEMA:
        raise ValueError(f"camera profile schema must be {SUPPORTED_CAMERA_SCHEMA}")
    stream = profile.get("stream")
    if not isinstance(stream, dict):
        raise ValueError("camera profile stream must be an object")
    for field_name in ("width", "height", "fps"):
        if int(stream.get(field_name, 0)) <= 0:
            raise ValueError(f"camera profile stream.{field_name} must be positive")
    return profile


def create_head_camera_source(
    profile: dict[str, Any],
    *,
    model: Any | None = None,
    data: Any | None = None,
    include_depth: bool = False,
):
    """Create the selected source while preserving one CameraFrame contract."""
    source = profile.get("active_source")
    stream = profile["stream"]
    width = int(stream["width"])
    height = int(stream["height"])
    fps = int(stream["fps"])

    if source == "simulation":
        if model is None or data is None:
            raise ValueError("simulation camera source requires MuJoCo model and data")
        simulation = profile.get("simulation", {})
        return MuJoCoHeadCameraSource(
            model,
            data,
            str(simulation.get("camera_name", "g1_d435_color")),
            width=width,
            height=height,
            vertical_fov_deg=float(stream["vertical_fov_deg"]),
            include_depth=include_depth,
        )

    if source == "real_d435i":
        real = profile.get("real_d435i", {})
        return RealSenseD435iSource(
            serial_number=real.get("serial_number"),
            width=width,
            height=height,
            fps=fps,
            include_depth=include_depth,
        )

    raise ValueError("active_source must be simulation or real_d435i")
