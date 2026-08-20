"""Typed loader and validation for config/teleop.json."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


@dataclass(frozen=True)
class NetworkConfig:
    udp_host: str
    udp_port: int
    unity_state_host: str
    unity_state_port: int
    unity_state_hz: float


@dataclass(frozen=True)
class RuntimeConfig:
    input_timeout_s: float
    workspace_exit_confirm_s: float
    status_hz: float
    head_camera_fps: float
    neutral_solve_iterations: int


@dataclass(frozen=True)
class MotionConfig:
    position_max_speed_mps: float
    rotation_max_speed_deg_s: float


@dataclass(frozen=True)
class IKConfig:
    position_damping: float
    orientation_damping: float
    ik_step_gain: float
    ik_max_step_deg: float
    posture_gain: float
    elbow_pole_gain: float
    elbow_pole_damping: float
    elbow_avoidance_weight: float


@dataclass(frozen=True)
class CollisionConfig:
    margin_m: float
    structural_neighbor_distance: int
    environment_obstacles_enabled: bool
    tangential_slide_enabled: bool
    task_contact_enabled: bool
    task_contact_tool_body_names: tuple[str, ...]
    task_contact_target_geom_names: tuple[str, ...]


@dataclass(frozen=True)
class WorkspaceConfig:
    voxel_size_m: float
    allowed_classes: tuple[int, ...]
    workspace_file: str
    clutch_delta_min_m: tuple[float, float, float]
    clutch_delta_max_m: tuple[float, float, float]
    right_elbow_lateral_limit_m: float
    right_wrist_lateral_limit_m: float
    torso_keep_out_x_m: tuple[float, float]
    torso_keep_out_z_m: tuple[float, float]


@dataclass(frozen=True)
class TeleopConfig:
    network: NetworkConfig
    runtime: RuntimeConfig
    motion: MotionConfig
    ik: IKConfig
    collision: CollisionConfig
    workspace: WorkspaceConfig


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _number(value: Any, name: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise ValueError(f"{name} must be > 0")
    if nonnegative and result < 0.0:
        raise ValueError(f"{name} must be >= 0")
    return result


def _integer(value: Any, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return int(value)


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _port(value: Any, name: str) -> int:
    port = _integer(value, name, minimum=1)
    if port > 65535:
        raise ValueError(f"{name} must be <= 65535")
    return port


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _string_tuple(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    result = tuple(_string(item, f"{name}[{index}]") for index, item in enumerate(value))
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must not contain duplicates")
    return result


def _vector(value: Any, name: str, size: int) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"{name} must be an array of length {size}")
    return tuple(_number(item, f"{name}[{index}]") for index, item in enumerate(value))


def load_teleop_config(path: str | Path) -> TeleopConfig:
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"teleoperation config not found: {config_path}")
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid teleoperation config JSON: {exc}") from exc

    root = _mapping(payload, "teleop config")
    network = _mapping(root.get("network"), "network")
    runtime = _mapping(root.get("runtime"), "runtime")
    motion = _mapping(root.get("motion"), "motion")
    ik = _mapping(root.get("ik"), "ik")
    collision = _mapping(root.get("collision"), "collision")
    task_contact = _mapping(collision.get("task_contact"), "collision.task_contact")
    workspace = _mapping(root.get("workspace"), "workspace")

    allowed_raw = workspace.get("allowed_classes")
    if not isinstance(allowed_raw, list) or not allowed_raw:
        raise ValueError("workspace.allowed_classes must be a non-empty array")
    allowed_classes = tuple(
        _integer(value, f"workspace.allowed_classes[{index}]", minimum=1)
        for index, value in enumerate(allowed_raw)
    )
    if len(set(allowed_classes)) != len(allowed_classes):
        raise ValueError("workspace.allowed_classes must not contain duplicates")
    if any(value not in (1, 2) for value in allowed_classes):
        raise ValueError("workspace.allowed_classes may only contain 1 or 2")

    clutch_min = _vector(workspace.get("clutch_delta_min_m"), "workspace.clutch_delta_min_m", 3)
    clutch_max = _vector(workspace.get("clutch_delta_max_m"), "workspace.clutch_delta_max_m", 3)
    if any(low >= high for low, high in zip(clutch_min, clutch_max)):
        raise ValueError("workspace clutch min values must be lower than max values")

    torso_x = _vector(workspace.get("torso_keep_out_x_m"), "workspace.torso_keep_out_x_m", 2)
    torso_z = _vector(workspace.get("torso_keep_out_z_m"), "workspace.torso_keep_out_z_m", 2)
    if torso_x[0] >= torso_x[1] or torso_z[0] >= torso_z[1]:
        raise ValueError("workspace torso keep-out ranges must be ordered")

    task_contact_enabled = _boolean(task_contact.get("enabled"), "collision.task_contact.enabled")
    tool_body_names = _string_tuple(task_contact.get("tool_body_names"), "collision.task_contact.tool_body_names")
    target_geom_names = _string_tuple(task_contact.get("target_geom_names"), "collision.task_contact.target_geom_names")
    if task_contact_enabled and (not tool_body_names or not target_geom_names):
        raise ValueError("enabled task contact requires at least one tool body and target geom")

    return TeleopConfig(
        network=NetworkConfig(
            udp_host=_string(network.get("udp_host"), "network.udp_host"),
            udp_port=_port(network.get("udp_port"), "network.udp_port"),
            unity_state_host=_string(network.get("unity_state_host"), "network.unity_state_host"),
            unity_state_port=_port(network.get("unity_state_port"), "network.unity_state_port"),
            unity_state_hz=_number(network.get("unity_state_hz"), "network.unity_state_hz", positive=True),
        ),
        runtime=RuntimeConfig(
            input_timeout_s=_number(runtime.get("input_timeout_s"), "runtime.input_timeout_s", positive=True),
            workspace_exit_confirm_s=_number(runtime.get("workspace_exit_confirm_s"), "runtime.workspace_exit_confirm_s", nonnegative=True),
            status_hz=_number(runtime.get("status_hz"), "runtime.status_hz", positive=True),
            head_camera_fps=_number(runtime.get("head_camera_fps"), "runtime.head_camera_fps", positive=True),
            neutral_solve_iterations=_integer(runtime.get("neutral_solve_iterations"), "runtime.neutral_solve_iterations", minimum=1),
        ),
        motion=MotionConfig(
            position_max_speed_mps=_number(motion.get("position_max_speed_mps"), "motion.position_max_speed_mps", positive=True),
            rotation_max_speed_deg_s=_number(motion.get("rotation_max_speed_deg_s"), "motion.rotation_max_speed_deg_s", positive=True),
        ),
        ik=IKConfig(
            position_damping=_number(ik.get("position_damping"), "ik.position_damping", positive=True),
            orientation_damping=_number(ik.get("orientation_damping"), "ik.orientation_damping", positive=True),
            ik_step_gain=_number(ik.get("ik_step_gain"), "ik.ik_step_gain", positive=True),
            ik_max_step_deg=_number(ik.get("ik_max_step_deg"), "ik.ik_max_step_deg", positive=True),
            posture_gain=_number(ik.get("posture_gain"), "ik.posture_gain", nonnegative=True),
            elbow_pole_gain=_number(ik.get("elbow_pole_gain"), "ik.elbow_pole_gain", nonnegative=True),
            elbow_pole_damping=_number(ik.get("elbow_pole_damping"), "ik.elbow_pole_damping", positive=True),
            elbow_avoidance_weight=_number(ik.get("elbow_avoidance_weight"), "ik.elbow_avoidance_weight", nonnegative=True),
        ),
        collision=CollisionConfig(
            margin_m=_number(collision.get("margin_m"), "collision.margin_m", positive=True),
            structural_neighbor_distance=_integer(collision.get("structural_neighbor_distance"), "collision.structural_neighbor_distance", minimum=1),
            environment_obstacles_enabled=_boolean(collision.get("environment_obstacles_enabled"), "collision.environment_obstacles_enabled"),
            tangential_slide_enabled=_boolean(collision.get("tangential_slide_enabled"), "collision.tangential_slide_enabled"),
            task_contact_enabled=task_contact_enabled,
            task_contact_tool_body_names=tool_body_names,
            task_contact_target_geom_names=target_geom_names,
        ),
        workspace=WorkspaceConfig(
            voxel_size_m=_number(workspace.get("voxel_size_m"), "workspace.voxel_size_m", positive=True),
            allowed_classes=allowed_classes,
            workspace_file=_string(workspace.get("workspace_file"), "workspace.workspace_file"),
            clutch_delta_min_m=clutch_min,
            clutch_delta_max_m=clutch_max,
            right_elbow_lateral_limit_m=_number(workspace.get("right_elbow_lateral_limit_m"), "workspace.right_elbow_lateral_limit_m"),
            right_wrist_lateral_limit_m=_number(workspace.get("right_wrist_lateral_limit_m"), "workspace.right_wrist_lateral_limit_m"),
            torso_keep_out_x_m=torso_x,
            torso_keep_out_z_m=torso_z,
        ),
    )


def apply_to_base_module(base: ModuleType, config: TeleopConfig) -> None:
    """Apply validated tuning values to the legacy helper module before runtime starts."""
    import numpy as np

    base.UDP_HOST = config.network.udp_host
    base.UDP_PORT = config.network.udp_port
    base.UNITY_STATE_HOST = config.network.unity_state_host
    base.UNITY_STATE_PORT = config.network.unity_state_port
    base.UNITY_STATE_HZ = config.network.unity_state_hz
    base.RUNTIME_STATUS_HZ = config.runtime.status_hz
    base.HEAD_CAMERA_FPS = config.runtime.head_camera_fps
    base.NEUTRAL_SOLVE_ITERATIONS = config.runtime.neutral_solve_iterations
    base.INPUT_TIMEOUT_SECONDS = config.runtime.input_timeout_s
    base.WORKSPACE_EXIT_CONFIRM_SECONDS = config.runtime.workspace_exit_confirm_s
    base.POSITION_MAX_SPEED = config.motion.position_max_speed_mps
    base.ROTATION_MAX_SPEED = math.radians(config.motion.rotation_max_speed_deg_s)
    base.POSITION_DAMPING = config.ik.position_damping
    base.ORIENTATION_DAMPING = config.ik.orientation_damping
    base.IK_STEP_GAIN = config.ik.ik_step_gain
    base.IK_MAX_STEP_RADIANS = math.radians(config.ik.ik_max_step_deg)
    base.POSTURE_GAIN = config.ik.posture_gain
    base.ELBOW_POLE_GAIN = config.ik.elbow_pole_gain
    base.ELBOW_POLE_DAMPING = config.ik.elbow_pole_damping
    base.ELBOW_AVOIDANCE_WEIGHT = config.ik.elbow_avoidance_weight
    base.COLLISION_MARGIN = config.collision.margin_m
    base.CLUTCH_POSITION_DELTA_MIN = np.asarray(config.workspace.clutch_delta_min_m, dtype=float)
    base.CLUTCH_POSITION_DELTA_MAX = np.asarray(config.workspace.clutch_delta_max_m, dtype=float)
    base.RIGHT_ELBOW_LATERAL_LIMIT = config.workspace.right_elbow_lateral_limit_m
    base.RIGHT_WRIST_LATERAL_LIMIT = config.workspace.right_wrist_lateral_limit_m
    base.TORSO_KEEP_OUT_X = tuple(config.workspace.torso_keep_out_x_m)
    base.TORSO_KEEP_OUT_Z = tuple(config.workspace.torso_keep_out_z_m)


def apply_to_projected_runtime(runtime: ModuleType, config: TeleopConfig, project_root: str | Path) -> None:
    root = Path(project_root)
    workspace_path = Path(config.workspace.workspace_file)
    if not workspace_path.is_absolute():
        workspace_path = root / workspace_path
    runtime.WORKSPACE_PATH = workspace_path
    runtime.WORKSPACE_VOXEL_SIZE_M = config.workspace.voxel_size_m
    runtime.WORKSPACE_ALLOWED_CLASSES = tuple(config.workspace.allowed_classes)
