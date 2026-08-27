#!/usr/bin/env python3
"""MuJoCo에서 G1 오른팔 Startup Recovery 준비자세를 편집한다.

이 도구는 로컬 MuJoCo 모델과 ``config/startup_recovery.json``만 사용한다.
Unitree SDK, DDS, UDP, 네트워크 소켓 및 로봇 명령 경로는 만들지 않는다.
저장은 정적 관절 범위와 충돌 여유 검사만 통과시키며, 실제 복구 경로의 안전성은
저장 후 ``TEST_G1_STARTUP_RECOVERY_OFFLINE.bat``으로 별도 검증해야 한다.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import glfw
import mujoco
import mujoco.viewer
import numpy as np

import diagnose_initial_pose_collision as collision_diag
from safety_gate import JOINT_LIMITS_RAD, JOINT_NAMES, SafetyConfig


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SCRIPTS_DIR: Final[Path] = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
DEFAULT_CONFIG_PATH: Final[Path] = PROJECT_ROOT / "config" / "startup_recovery.json"
BACKUP_PATH: Final[Path] = (
    PROJECT_ROOT / "logs" / "runtime" / "startup_ready_pose_previous.json"
)

STEP_OPTIONS_DEG: Final[tuple[float, ...]] = (0.1, 0.5, 1.0, 2.0, 5.0)
DEFAULT_STEP_INDEX: Final[int] = 2
MARKER_RADIUS_M: Final[float] = 0.025
MARKER_VALID_RGBA: Final[np.ndarray] = np.asarray([1.0, 0.65, 0.05, 0.95])
MARKER_INVALID_RGBA: Final[np.ndarray] = np.asarray([0.90, 0.08, 0.08, 0.95])
MARKER_SAVED_RGBA: Final[np.ndarray] = np.asarray([0.05, 0.85, 0.20, 0.95])

DISPLAY_NAMES: Final[tuple[str, ...]] = (
    "shoulder pitch",
    "shoulder roll",
    "shoulder yaw",
    "elbow",
    "wrist roll",
    "wrist pitch",
    "wrist yaw",
)


@dataclass(frozen=True)
class PoseAssessment:
    valid: bool
    joint_reason: str
    nearest_distance_m: float
    nearest_pair: str
    blocked_pair_count: int


@dataclass
class EditorState:
    pose_deg: np.ndarray
    saved_pose_deg: np.ndarray
    selected_index: int = 0
    step_index: int = DEFAULT_STEP_INDEX
    assessment: PoseAssessment | None = None
    dirty: bool = False
    quit_requested: bool = False
    saved_flash_until: float = 0.0


def ParseArguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Edit the G1 Startup Recovery ready pose in MuJoCo"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate the saved pose without opening the MuJoCo Viewer",
    )
    return parser.parse_args()


def LoadPose(config_path: Path) -> np.ndarray:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    pose = payload.get("safe_ready_pose_deg")
    if not isinstance(pose, dict):
        raise RuntimeError("safe_ready_pose_deg must be a JSON object")

    missing = set(JOINT_NAMES) - set(pose)
    unknown = set(pose) - set(JOINT_NAMES)
    if missing or unknown:
        raise RuntimeError(
            "safe_ready_pose_deg joint mismatch: "
            f"missing={sorted(missing)}, unknown={sorted(unknown)}"
        )

    values = np.asarray([pose[name] for name in JOINT_NAMES], dtype=float)
    if values.shape != (7,) or not np.all(np.isfinite(values)):
        raise RuntimeError("safe_ready_pose_deg must contain seven finite values")
    return values


def SafeLimitsDegrees() -> np.ndarray:
    margin = SafetyConfig().joint_limit_margin_rad
    return np.asarray(
        [
            (math.degrees(low + margin), math.degrees(high - margin))
            for low, high in JOINT_LIMITS_RAD
        ],
        dtype=float,
    )


def ValidateJointRanges(pose_deg: np.ndarray) -> tuple[bool, str]:
    if pose_deg.shape != (7,) or not np.all(np.isfinite(pose_deg)):
        return False, "pose must contain seven finite joint values"

    for name, value, limits in zip(JOINT_NAMES, pose_deg, SafeLimitsDegrees()):
        low, high = limits
        if value < low or value > high:
            return False, (
                f"{name}={value:.2f} deg outside Safety Gate "
                f"[{low:.2f}, {high:.2f}] deg"
            )
    return True, "ok"


def ApplyPose(model, data, controller, pose_deg: np.ndarray) -> None:
    for joint_name, value_deg in zip(controller.g1.RIGHT_ARM_JOINTS, pose_deg):
        controller.g1.set_joint(
            model,
            data,
            joint_name,
            math.radians(float(value_deg)),
        )
    mujoco.mj_forward(model, data)


def AssessPose(model, data, controller, geom_pairs, pose_deg: np.ndarray) -> PoseAssessment:
    joint_ok, joint_reason = ValidateJointRanges(pose_deg)
    nearby = collision_diag._nearby_pairs(model, data, controller, geom_pairs)
    blocked = [
        item
        for item in nearby
        if float(item["distance_m"]) < controller.COLLISION_MIN_DISTANCE_M
    ]

    if nearby:
        nearest = nearby[0]
        nearest_distance = float(nearest["distance_m"])
        nearest_pair = f"{nearest['first_body']} <-> {nearest['second_body']}"
    else:
        nearest_distance = math.inf
        nearest_pair = "none within 40 mm"

    return PoseAssessment(
        valid=joint_ok and not blocked,
        joint_reason=joint_reason,
        nearest_distance_m=nearest_distance,
        nearest_pair=nearest_pair,
        blocked_pair_count=len(blocked),
    )


def SavePose(
    config_path: Path,
    pose_deg: np.ndarray,
    backup_path: Path = BACKUP_PATH,
) -> None:
    joint_ok, joint_reason = ValidateJointRanges(pose_deg)
    if not joint_ok:
        raise RuntimeError(joint_reason)

    original_text = config_path.read_text(encoding="utf-8")
    payload = json.loads(original_text)
    payload["safe_ready_pose_deg"] = {
        name: round(float(value), 4)
        for name, value in zip(JOINT_NAMES, pose_deg)
    }

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_temporary = backup_path.with_suffix(backup_path.suffix + ".tmp")
    backup_temporary.write_text(original_text, encoding="utf-8")
    backup_temporary.replace(backup_path)

    temporary = config_path.with_suffix(config_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(config_path)


def ClearanceText(assessment: PoseAssessment) -> str:
    if math.isinf(assessment.nearest_distance_m):
        return ">=40.0 mm"
    return (
        f"{assessment.nearest_distance_m * 1000.0:.1f} mm "
        f"({assessment.nearest_pair})"
    )


def PrintPose(state: EditorState) -> None:
    print("\nCurrent ready pose")
    print("------------------")
    for index, (name, value) in enumerate(zip(DISPLAY_NAMES, state.pose_deg)):
        marker = ">" if index == state.selected_index else " "
        print(f"{marker} {index + 1}. {name:<16} {value:+8.2f} deg")
    if state.assessment is not None:
        result = "VALID" if state.assessment.valid else "BLOCKED"
        print(f"Static check: {result}; nearest clearance {ClearanceText(state.assessment)}")


def PrintHelp() -> None:
    print(
        """
Keyboard controls (MuJoCo window focused)
-----------------------------------------
1..7 / Up,Down : select a right-arm joint
Left,Right     : decrease/increase the selected angle
A,D            : same as Left,Right
Comma,Period   : smaller/larger angle step
Z              : set selected joint toward zero (clamped to safe range)
R              : restore the last saved pose
V              : validate and print the full pose
S              : save only when joint and collision checks pass
H              : print this help again
Q / Esc        : close the editor

The yellow sphere marks the selected joint. It becomes red for an invalid
pose and briefly green after a successful save.
""".strip()
    )


def PrintSelection(state: EditorState) -> None:
    assessment = state.assessment
    validity = "VALID" if assessment is not None and assessment.valid else "BLOCKED"
    print(
        f"[{state.selected_index + 1}] {DISPLAY_NAMES[state.selected_index]}="
        f"{state.pose_deg[state.selected_index]:+.2f} deg | "
        f"step={STEP_OPTIONS_DEG[state.step_index]:.1f} deg | {validity} | "
        f"clearance={ClearanceText(assessment) if assessment else 'unknown'}"
    )


def UpdateSelectedJointMarker(viewer, model, data, controller, state: EditorState) -> None:
    scene = viewer.user_scn
    if scene is None:
        return

    joint_name = controller.g1.RIGHT_ARM_JOINTS[state.selected_index]
    joint_id = controller._joint_id(model, joint_name)
    position = np.asarray(data.xanchor[joint_id], dtype=float)
    if state.assessment is None or not state.assessment.valid:
        color = MARKER_INVALID_RGBA
    elif time.monotonic() < state.saved_flash_until:
        color = MARKER_SAVED_RGBA
    else:
        color = MARKER_VALID_RGBA

    scene.ngeom = 1
    mujoco.mjv_initGeom(
        scene.geoms[0],
        mujoco.mjtGeom.mjGEOM_SPHERE,
        np.asarray([MARKER_RADIUS_M, 0.0, 0.0]),
        position,
        np.eye(3).reshape(-1),
        color,
    )


def CreateModel(pose_deg: np.ndarray):
    os.environ.pop("G1_USE_HARDWARE_INITIAL_STATE", None)
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))

    import run_mink_g1_right_arm_prototype as controller

    controller._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(controller.g1.DEMO_XML))
    controller._apply_operational_joint_limits(model)
    data = mujoco.MjData(model)
    data.qpos[:] = controller._initial_configuration(model)
    ApplyPose(model, data, controller, pose_deg)
    _, geom_pairs = controller._build_collision_pairs(model)
    return controller, model, data, geom_pairs


def Main() -> int:
    args = ParseArguments()
    pose_deg = LoadPose(args.config)
    joint_ok, joint_reason = ValidateJointRanges(pose_deg)
    if not joint_ok:
        raise SystemExit(f"[FAIL] Saved pose is outside Safety Gate: {joint_reason}")

    controller, model, data, geom_pairs = CreateModel(pose_deg)
    state = EditorState(pose_deg=pose_deg.copy(), saved_pose_deg=pose_deg.copy())
    state.assessment = AssessPose(model, data, controller, geom_pairs, state.pose_deg)

    print("G1 Startup Recovery - interactive ready-pose editor")
    print("---------------------------------------------------")
    print(f"Config: {args.config.resolve()}")
    print("Unitree SDK / DDS / UDP / robot command: NONE")
    PrintPose(state)

    if args.validate_only:
        if state.assessment.valid:
            print("[PASS] Saved ready pose passes static joint/collision checks.")
            return 0
        print("[FAIL] Saved ready pose does not pass static checks.")
        return 1

    PrintHelp()
    command_queue: queue.SimpleQueue[str] = queue.SimpleQueue()

    key_commands = {
        glfw.KEY_LEFT: "decrease",
        glfw.KEY_A: "decrease",
        glfw.KEY_RIGHT: "increase",
        glfw.KEY_D: "increase",
        glfw.KEY_UP: "previous_joint",
        glfw.KEY_DOWN: "next_joint",
        glfw.KEY_COMMA: "smaller_step",
        glfw.KEY_MINUS: "smaller_step",
        glfw.KEY_PERIOD: "larger_step",
        glfw.KEY_EQUAL: "larger_step",
        glfw.KEY_Z: "zero",
        glfw.KEY_R: "restore",
        glfw.KEY_V: "validate",
        glfw.KEY_S: "save",
        glfw.KEY_H: "help",
        glfw.KEY_Q: "quit",
    }
    for index in range(7):
        key_commands[glfw.KEY_1 + index] = f"select:{index}"

    def KeyCallback(key: int) -> None:
        command = key_commands.get(int(key))
        if command is not None:
            command_queue.put(command)

    with mujoco.viewer.launch_passive(
        model,
        data,
        key_callback=KeyCallback,
        show_left_ui=False,
        show_right_ui=True,
    ) as viewer:
        viewer.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        viewer.cam.lookat[:] = np.asarray([0.0, 0.0, 0.95])
        viewer.cam.distance = 2.7
        viewer.cam.azimuth = 135.0
        viewer.cam.elevation = -10.0
        viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = True

        while viewer.is_running() and not state.quit_requested:
            while not command_queue.empty():
                command = command_queue.get()
                pose_changed = False
                if command.startswith("select:"):
                    state.selected_index = int(command.split(":", 1)[1])
                elif command == "previous_joint":
                    state.selected_index = (state.selected_index - 1) % 7
                elif command == "next_joint":
                    state.selected_index = (state.selected_index + 1) % 7
                elif command in {"decrease", "increase", "zero"}:
                    limits = SafeLimitsDegrees()[state.selected_index]
                    previous = float(state.pose_deg[state.selected_index])
                    if command == "zero":
                        requested = 0.0
                    else:
                        direction = -1.0 if command == "decrease" else 1.0
                        requested = previous + direction * STEP_OPTIONS_DEG[state.step_index]
                    state.pose_deg[state.selected_index] = float(
                        np.clip(requested, limits[0], limits[1])
                    )
                    if not math.isclose(requested, state.pose_deg[state.selected_index]):
                        print(
                            f"[LIMIT] {DISPLAY_NAMES[state.selected_index]} clamped to "
                            f"{state.pose_deg[state.selected_index]:.2f} deg"
                        )
                    state.dirty = not np.allclose(
                        state.pose_deg,
                        state.saved_pose_deg,
                        atol=1e-9,
                    )
                    pose_changed = True
                elif command == "smaller_step":
                    state.step_index = max(0, state.step_index - 1)
                elif command == "larger_step":
                    state.step_index = min(
                        len(STEP_OPTIONS_DEG) - 1,
                        state.step_index + 1,
                    )
                elif command == "restore":
                    state.pose_deg[:] = state.saved_pose_deg
                    state.dirty = False
                    pose_changed = True
                    print("[RESTORE] Returned to the last saved ready pose.")
                elif command == "validate":
                    PrintPose(state)
                elif command == "save":
                    if state.assessment is None or not state.assessment.valid:
                        print(
                            "[SAVE BLOCKED] Pose must satisfy Safety Gate joint ranges "
                            f"and {controller.COLLISION_MIN_DISTANCE_M * 1000.0:.0f} mm "
                            "static collision clearance."
                        )
                    else:
                        SavePose(args.config, state.pose_deg)
                        state.saved_pose_deg[:] = state.pose_deg
                        state.dirty = False
                        state.saved_flash_until = time.monotonic() + 1.0
                        print(f"[SAVED] {args.config.resolve()}")
                        print(f"[BACKUP] {BACKUP_PATH.resolve()}")
                        print(
                            "[NEXT] Run tools\\TEST_G1_STARTUP_RECOVERY_OFFLINE.bat "
                            "before treating this pose as a recovery goal."
                        )
                elif command == "help":
                    PrintHelp()
                elif command == "quit":
                    state.quit_requested = True

                if command not in {"validate", "help", "save", "quit"}:
                    if pose_changed:
                        with viewer.lock():
                            ApplyPose(model, data, controller, state.pose_deg)
                            state.assessment = AssessPose(
                                model,
                                data,
                                controller,
                                geom_pairs,
                                state.pose_deg,
                            )
                    PrintSelection(state)

            with viewer.lock():
                UpdateSelectedJointMarker(viewer, model, data, controller, state)
            viewer.sync()
            time.sleep(1.0 / 60.0)

    if state.dirty:
        print("[NOT SAVED] The editor closed with unsaved pose changes.")
    print(f"Config: {args.config.resolve()}")
    print("Robot command: NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(Main())
