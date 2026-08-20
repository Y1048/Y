"""Common head-camera contract for MuJoCo and a physical RealSense device."""

from __future__ import annotations

import math
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np


CAMERA_FRAME_ID = "g1/d435_color_optical_frame"


@dataclass(frozen=True)
class CameraIntrinsics:
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    distortion_model: str = "none"
    distortion_coefficients: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        values = (self.fx, self.fy, self.cx, self.cy, *self.distortion_coefficients)
        if self.width <= 0 or self.height <= 0:
            raise ValueError("camera dimensions must be positive")
        if self.fx <= 0.0 or self.fy <= 0.0 or not np.all(np.isfinite(values)):
            raise ValueError("camera intrinsics must be finite with positive focal lengths")

    @classmethod
    def from_vertical_fov(cls, width: int, height: int, vertical_fov_deg: float) -> "CameraIntrinsics":
        if not 0.0 < vertical_fov_deg < 180.0:
            raise ValueError("vertical_fov_deg must be in (0, 180)")
        focal_length = 0.5 * height / math.tan(math.radians(vertical_fov_deg) * 0.5)
        return cls(
            width=width,
            height=height,
            fx=focal_length,
            fy=focal_length,
            cx=(width - 1.0) * 0.5,
            cy=(height - 1.0) * 0.5,
        )


@dataclass(frozen=True)
class CameraFrame:
    sequence: int
    capture_time_ns: int
    source: str
    color_bgr: np.ndarray
    intrinsics: CameraIntrinsics
    depth_mm: np.ndarray | None = None
    frame_id: str = CAMERA_FRAME_ID
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        color = np.asarray(self.color_bgr)
        expected_shape = (self.intrinsics.height, self.intrinsics.width, 3)
        if self.sequence < 0 or self.capture_time_ns < 0:
            raise ValueError("camera sequence and capture time must be non-negative")
        if color.dtype != np.uint8 or color.shape != expected_shape:
            raise ValueError(f"color_bgr must be uint8 with shape {expected_shape}")
        object.__setattr__(self, "color_bgr", np.ascontiguousarray(color))

        if self.depth_mm is not None:
            depth = np.asarray(self.depth_mm)
            if depth.dtype != np.uint16 or depth.shape != expected_shape[:2]:
                raise ValueError(f"depth_mm must be uint16 with shape {expected_shape[:2]}")
            object.__setattr__(self, "depth_mm", np.ascontiguousarray(depth))


class HeadCameraSource(Protocol):
    def start(self) -> None:
        ...

    def read(self) -> CameraFrame:
        ...

    def close(self) -> None:
        ...


class MuJoCoHeadCameraSource:
    """Render the named MuJoCo camera using the same frame contract as RealSense."""

    def __init__(
        self,
        model: Any,
        data: Any,
        camera_name: str,
        width: int = 640,
        height: int = 480,
        vertical_fov_deg: float = 42.5,
        include_depth: bool = False,
    ) -> None:
        self.model = model
        self.data = data
        self.camera_name = camera_name
        self.width = width
        self.height = height
        self.include_depth = include_depth
        self.intrinsics = CameraIntrinsics.from_vertical_fov(width, height, vertical_fov_deg)
        self._renderer = None
        self._sequence = 0

    def start(self) -> None:
        if self._renderer is not None:
            return
        import mujoco

        camera_id = mujoco.mj_name2id(
            self.model,
            mujoco.mjtObj.mjOBJ_CAMERA,
            self.camera_name,
        )
        if camera_id < 0:
            raise ValueError(f"MuJoCo camera not found: {self.camera_name}")
        self._renderer = mujoco.Renderer(self.model, height=self.height, width=self.width)

    def read(self) -> CameraFrame:
        if self._renderer is None:
            self.start()

        self._renderer.disable_depth_rendering()
        self._renderer.update_scene(self.data, camera=self.camera_name)
        color_rgb = self._renderer.render().copy()
        color_bgr = np.ascontiguousarray(color_rgb[:, :, ::-1])

        depth_mm = None
        if self.include_depth:
            self._renderer.enable_depth_rendering()
            self._renderer.update_scene(self.data, camera=self.camera_name)
            depth_m = self._renderer.render().copy()
            depth_mm = np.clip(np.rint(depth_m * 1000.0), 0, 65535).astype(np.uint16)
            self._renderer.disable_depth_rendering()

        frame = CameraFrame(
            sequence=self._sequence,
            capture_time_ns=time.monotonic_ns(),
            source="mujoco",
            color_bgr=color_bgr,
            depth_mm=depth_mm,
            intrinsics=self.intrinsics,
            metadata={"camera_name": self.camera_name},
        )
        self._sequence += 1
        return frame

    def close(self) -> None:
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None

    def __enter__(self) -> "MuJoCoHeadCameraSource":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class RealSenseD435iSource:
    """Optional physical source; pyrealsense2 is imported only when started."""

    def __init__(
        self,
        serial_number: str | None = None,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        include_depth: bool = False,
    ) -> None:
        self.serial_number = serial_number
        self.width = width
        self.height = height
        self.fps = fps
        self.include_depth = include_depth
        self.intrinsics: CameraIntrinsics | None = None
        self._rs = None
        self._pipeline = None
        self._align = None
        self._depth_scale_m = 0.001
        self._sequence = 0

    def start(self) -> None:
        if self._pipeline is not None:
            return
        try:
            import pyrealsense2 as rs
        except ImportError as error:
            raise RuntimeError(
                "pyrealsense2 is required only for source=real_d435i; "
                "keep source=simulation until the camera is available"
            ) from error

        pipeline = rs.pipeline()
        config = rs.config()
        if self.serial_number:
            config.enable_device(self.serial_number)
        config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)
        if self.include_depth:
            config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, self.fps)

        profile = pipeline.start(config)
        video_profile = profile.get_stream(rs.stream.color).as_video_stream_profile()
        intrinsic = video_profile.get_intrinsics()
        self.intrinsics = CameraIntrinsics(
            width=intrinsic.width,
            height=intrinsic.height,
            fx=intrinsic.fx,
            fy=intrinsic.fy,
            cx=intrinsic.ppx,
            cy=intrinsic.ppy,
            distortion_model=str(intrinsic.model),
            distortion_coefficients=tuple(float(value) for value in intrinsic.coeffs),
        )
        self._rs = rs
        self._pipeline = pipeline
        self._align = rs.align(rs.stream.color) if self.include_depth else None
        if self.include_depth:
            self._depth_scale_m = float(profile.get_device().first_depth_sensor().get_depth_scale())

    def read(self) -> CameraFrame:
        if self._pipeline is None:
            self.start()

        frames = self._pipeline.wait_for_frames()
        if self._align is not None:
            frames = self._align.process(frames)
        color_frame = frames.get_color_frame()
        if not color_frame:
            raise RuntimeError("RealSense did not return a color frame")

        color_bgr = np.ascontiguousarray(np.asanyarray(color_frame.get_data()))
        depth_mm = None
        if self.include_depth:
            depth_frame = frames.get_depth_frame()
            if not depth_frame:
                raise RuntimeError("RealSense did not return an aligned depth frame")
            depth_raw = np.asanyarray(depth_frame.get_data()).astype(np.float64)
            depth_mm = np.clip(
                np.rint(depth_raw * self._depth_scale_m * 1000.0),
                0,
                65535,
            ).astype(np.uint16)
            depth_mm = np.ascontiguousarray(depth_mm)

        frame = CameraFrame(
            sequence=self._sequence,
            capture_time_ns=time.monotonic_ns(),
            source="real_d435i",
            color_bgr=color_bgr,
            depth_mm=depth_mm,
            intrinsics=self.intrinsics,
            metadata={
                "device_timestamp_ms": float(color_frame.get_timestamp()),
                "serial_number": self.serial_number,
            },
        )
        self._sequence += 1
        return frame

    def close(self) -> None:
        if self._pipeline is not None:
            self._pipeline.stop()
        self._pipeline = None
        self._align = None
        self._rs = None

    def __enter__(self) -> "RealSenseD435iSource":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def save_bgr_bmp(path: str | Path, image_bgr: np.ndarray) -> None:
    """Save a uint8 BGR frame without adding an image-library dependency."""
    image = np.asarray(image_bgr)
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image_bgr must be a uint8 HxWx3 array")

    height, width, _ = image.shape
    row_stride = (width * 3 + 3) & ~3
    padding = b"\x00" * (row_stride - width * 3)
    pixel_rows = [image[row].tobytes() + padding for row in range(height - 1, -1, -1)]
    pixel_data = b"".join(pixel_rows)
    data_offset = 14 + 40
    file_size = data_offset + len(pixel_data)
    file_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, data_offset)
    info_header = struct.pack(
        "<IIIHHIIIIII",
        40,
        width,
        height,
        1,
        24,
        0,
        len(pixel_data),
        2835,
        2835,
        0,
        0,
    )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(file_header + info_header + pixel_data)
