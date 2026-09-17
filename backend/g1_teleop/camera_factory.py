"""Build camera sources without leaking hardware details into teleoperation code."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .camera import MuJoCoHeadCameraSource, RealSenseD435iSource


SUPPORTED_CAMERA_SCHEMA = "g1.teleop.camera.v1"


def load_camera_profile(path: str | Path) -> dict[str, Any]:
    profile = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_camera_profile(profile)
    return profile


def validate_camera_profile(profile: dict[str, Any]) -> None:
    if not isinstance(profile, dict) or profile.get("schema") != SUPPORTED_CAMERA_SCHEMA:
        raise ValueError(f"camera profile schema must be {SUPPORTED_CAMERA_SCHEMA}")
    stream = profile.get("stream")
    if not isinstance(stream, dict):
        raise ValueError("camera profile stream must be an object")
    for field_name in ("width", "height", "fps"):
        value = stream.get(field_name)
        if type(value) is not int or value <= 0:
            raise ValueError(f"camera profile stream.{field_name} must be a positive integer")
    fov = stream.get("vertical_fov_deg")
    if type(fov) not in (int, float) or not math.isfinite(fov) or not 0 < fov < 180:
        raise ValueError("camera profile stream.vertical_fov_deg must be finite and between 0 and 180")
    if profile.get("active_source") not in ("simulation", "real_d435i"):
        raise ValueError("active_source must be simulation or real_d435i")


def validate_teleimager_profile(profile: dict[str, Any], settings: dict[str, Any], source: str) -> None:
    """Check the head-stream contract only; never instantiate a camera source."""
    validate_camera_profile(profile)
    if source not in ("simulation", "real_d435i"):
        raise ValueError("unknown TeleImager source")
    head = settings.get("head_camera") if isinstance(settings, dict) else None
    if not isinstance(head, dict):
        raise ValueError("TeleImager head_camera must be an object")
    stream = profile["stream"]
    if type(stream.get("binocular")) is not bool:
        raise ValueError("camera profile binocular must be boolean")
    shape = head.get("image_shape")
    if (not isinstance(shape, list) or len(shape) != 2
            or any(type(v) is not int for v in shape)
            or shape != [stream["height"], stream["width"]]):
        raise ValueError("TeleImager image_shape must match profile [height, width]")
    if type(head.get("fps")) is not int or head["fps"] != stream["fps"]:
        raise ValueError("TeleImager fps must match camera profile")
    if type(head.get("binocular")) is not bool or head["binocular"] != stream["binocular"]:
        raise ValueError("TeleImager binocular must match camera profile")
    expected = "isaacsim" if source == "simulation" else "realsense"
    if head.get("type") != expected:
        raise ValueError(f"TeleImager type must be {expected}")


def create_head_camera_source(
    profile: dict[str, Any],
    *,
    model: Any | None = None,
    data: Any | None = None,
    include_depth: bool = False,
):
    """Create the selected source while preserving one CameraFrame contract."""
    validate_camera_profile(profile)
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
