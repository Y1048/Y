from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import sys
from multiprocessing import shared_memory
from pathlib import Path

import mujoco
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
DEMO_PATH = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts" / "g1_right_arm_udp_ik_demo.py"
PROFILE_PATH = PROJECT_ROOT / "config" / "camera_profile.json"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop import (  # noqa: E402
    G1_D435I_CAMERA_NAME,
    G1_D435I_ISAACLAB_ROS_QUAT_WXYZ,
    G1_D435I_MUJOCO_QUAT_WXYZ,
    G1_D435I_PITCH_RAD,
    G1_D435I_POSITION_M,
    G1_D435I_VERTICAL_FOV_DEG,
    UnitreeSimImageWriter,
    create_head_camera_source,
    load_camera_profile,
    save_bgr_bmp,
)
from g1_teleop.unitree_image_transport import (  # noqa: E402
    UnitreeImageHeader,
    shared_memory_name,
)


def load_demo_module():
    spec = importlib.util.spec_from_file_location("g1_camera_validation_demo", DEMO_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load demo module: {DEMO_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args():
    parser = argparse.ArgumentParser(description="Validate the simulated G1 D435i path")
    parser.add_argument(
        "--preview",
        type=Path,
        default=PROJECT_ROOT / "logs" / "camera" / "g1_head_camera_preview.bmp",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "logs" / "camera" / "camera_validation_report.json",
    )
    return parser.parse_args()


def quaternion_rotation_matrix(quaternion_wxyz):
    w, x, y, z = quaternion_wxyz
    return np.asarray(
        [
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
            [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
            [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
        ],
        dtype=float,
    )


def official_optical_axes():
    pitch = G1_D435I_PITCH_RAD
    mount_rotation = np.asarray(
        [
            [np.cos(pitch), 0.0, np.sin(pitch)],
            [0.0, 1.0, 0.0],
            [-np.sin(pitch), 0.0, np.cos(pitch)],
        ],
        dtype=float,
    )
    optical_rotation = mount_rotation @ quaternion_rotation_matrix(
        G1_D435I_ISAACLAB_ROS_QUAT_WXYZ
    )
    return optical_rotation @ np.asarray([0.0, 0.0, 1.0]), optical_rotation @ np.asarray(
        [0.0, -1.0, 0.0]
    )


def verify_transport(frame):
    image_name = "verify_head"
    writer = UnitreeSimImageWriter()
    reader = None
    try:
        timestamp_ms = writer.write_frame(frame, image_name)
        reader = shared_memory.SharedMemory(name=shared_memory_name(image_name))
        header_size = ctypes.sizeof(UnitreeImageHeader)
        header = UnitreeImageHeader.from_buffer_copy(bytes(reader.buf[:header_size]))
        first_pixel = list(reader.buf[header_size : header_size + 3])
        expected_pixel = frame.color_bgr[0, 0].tolist()
        passed = (
            header.timestamp == timestamp_ms
            and (header.height, header.width, header.channels) == frame.color_bgr.shape
            and header.data_size == frame.color_bgr.nbytes
            and header.encoding == 0
            and first_pixel == expected_pixel
        )
        return {
            "passed": passed,
            "shared_memory_name": shared_memory_name(image_name),
            "header_size_bytes": header_size,
            "payload_size_bytes": int(header.data_size),
            "encoding": "raw_bgr" if header.encoding == 0 else int(header.encoding),
        }
    finally:
        if reader is not None:
            reader.close()
        writer.close(unlink=True)


def main():
    args = parse_args()
    demo = load_demo_module()
    model, data, initial_qpos, preferred = demo.initialize_model("camera_validation")
    target = np.asarray(demo.SCENES["camera_validation"]["target_pos"], dtype=float)
    tool_position = demo.solve_right_arm_target(
        model,
        data,
        initial_qpos,
        preferred,
        target,
        iterations=300,
    )
    ik_error_m = float(np.linalg.norm(target - tool_position))

    profile = load_camera_profile(PROFILE_PATH)
    profile["active_source"] = "simulation"
    source = create_head_camera_source(profile, model=model, data=data)
    try:
        frame = source.read()
    finally:
        source.close()
    save_bgr_bmp(args.preview, frame.color_bgr)

    camera_id = mujoco.mj_name2id(
        model,
        mujoco.mjtObj.mjOBJ_CAMERA,
        G1_D435I_CAMERA_NAME,
    )
    camera_rotation = data.cam_xmat[camera_id].reshape(3, 3)
    camera_forward = -camera_rotation[:, 2]
    camera_up = camera_rotation[:, 1]
    official_forward, official_up = official_optical_axes()
    optical_axes_passed = bool(
        np.allclose(camera_forward, official_forward, atol=1e-7)
        and np.allclose(camera_up, official_up, atol=1e-7)
    )
    transport = verify_transport(frame)
    image_standard_deviation = float(np.std(frame.color_bgr))
    nonblank_ratio = float(np.count_nonzero(frame.color_bgr) / frame.color_bgr.size)

    mount_passed = bool(
        np.allclose(model.cam_pos[camera_id], G1_D435I_POSITION_M, atol=1e-8)
        and np.allclose(model.cam_quat[camera_id], G1_D435I_MUJOCO_QUAT_WXYZ, atol=1e-8)
        and abs(float(model.cam_fovy[camera_id]) - G1_D435I_VERTICAL_FOV_DEG) < 1e-8
        and optical_axes_passed
    )
    stream_passed = bool(
        frame.color_bgr.shape == (480, 640, 3)
        and frame.color_bgr.dtype == np.uint8
        and image_standard_deviation > 5.0
        and nonblank_ratio > 0.25
    )
    ik_passed = ik_error_m <= 0.03
    passed = mount_passed and stream_passed and ik_passed and transport["passed"]

    report = {
        "schema": "g1.teleop.camera.validation.v1",
        "status": "PASS" if passed else "FAIL",
        "camera": {
            "source": frame.source,
            "frame_id": frame.frame_id,
            "resolution": [frame.intrinsics.width, frame.intrinsics.height],
            "fps_profile": int(profile["stream"]["fps"]),
            "pixel_format": profile["stream"]["pixel_format"],
            "mount_parent": profile["mount"]["parent_link"],
            "mount_position_m": model.cam_pos[camera_id].tolist(),
            "mount_quaternion_wxyz": model.cam_quat[camera_id].tolist(),
            "world_position_m": data.cam_xpos[camera_id].tolist(),
            "world_forward": camera_forward.tolist(),
            "world_up": camera_up.tolist(),
            "unitree_isaaclab_forward": official_forward.tolist(),
            "unitree_isaaclab_up": official_up.tolist(),
            "optical_axes_passed": optical_axes_passed,
            "vertical_fov_deg": float(model.cam_fovy[camera_id]),
            "mount_passed": mount_passed,
        },
        "scene": {
            "name": "camera_validation",
            "target_position_m": target.tolist(),
            "tool_position_m": tool_position.tolist(),
            "ik_error_m": ik_error_m,
            "ik_passed": ik_passed,
        },
        "image": {
            "standard_deviation": image_standard_deviation,
            "nonblank_ratio": nonblank_ratio,
            "stream_passed": stream_passed,
            "preview": str(args.preview.resolve()),
        },
        "transport": transport,
        "real_camera_transition": {
            "adapter": "real_d435i",
            "requires_hardware_measurement": profile["hardware_acceptance"][
                "measure_on_first_connection"
            ],
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Camera simulation validation: {report['status']}")
    print(f"Preview: {args.preview.resolve()}")
    print(f"Report:  {args.report.resolve()}")
    print(f"IK error: {ik_error_m * 1000.0:.1f} mm")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
