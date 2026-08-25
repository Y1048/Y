from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import mujoco
import numpy as np


ENABLE_ERROR_DEG = 20.0
MAX_PROXIMAL_STEP_DEG = 0.10
MAX_POSITION_DRIFT_M = 0.00020
DAMPING = 0.05
LINE_SEARCH_STEPS = 6


def _error_vector(base: ModuleType, target: np.ndarray, current: np.ndarray) -> np.ndarray:
    return np.asarray(base.calculate_rotation_error(target, current), dtype=float)


def _error_deg(base: ModuleType, target: np.ndarray, current: np.ndarray) -> float:
    magnitude = float(np.linalg.norm(_error_vector(base, target, current)))
    return math.degrees(math.asin(float(np.clip(magnitude, 0.0, 1.0))))


def install_orientation_recovery(base: ModuleType) -> None:
    if getattr(base, "_ORIENTATION_RECOVERY_INSTALLED", False):
        return

    original_solver = base.solve_right_arm_target
    base.RUNTIME_WRIST_ORIENTATION_ERROR_DEG = 0.0
    base.RUNTIME_ORIENTATION_ASSIST_ACTIVE = False
    base.RUNTIME_ORIENTATION_ASSIST_STEP_DEG = 0.0
    base.RUNTIME_ORIENTATION_ASSIST_POSITION_DRIFT_M = 0.0

    def assisted_solver(*args: Any, **kwargs: Any):
        target_rotation = kwargs.get("target_rotation")
        if target_rotation is None and len(args) > 5:
            target_rotation = args[5]

        result = original_solver(*args, **kwargs)
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        context = kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]

        base.RUNTIME_ORIENTATION_ASSIST_ACTIVE = False
        base.RUNTIME_ORIENTATION_ASSIST_STEP_DEG = 0.0
        base.RUNTIME_ORIENTATION_ASSIST_POSITION_DRIFT_M = 0.0

        if model is None or data is None or target_rotation is None or not isinstance(context, dict):
            return result

        dof_ids = np.asarray(context.get("right_dof_ids", []), dtype=int)
        qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        position_body = context.get("position_body")
        orientation_body = context.get("orientation_body")
        if dof_ids.size < 7 or qpos_ids.size < 7 or position_body is None or orientation_body is None:
            return result

        mujoco.mj_forward(model, data)
        target = np.asarray(target_rotation, dtype=float)
        current = data.xmat[int(orientation_body)].reshape(3, 3).copy()
        error_vector = _error_vector(base, target, current)
        error_deg = _error_deg(base, target, current)
        base.RUNTIME_WRIST_ORIENTATION_ERROR_DEG = error_deg
        context["wrist_orientation_error_deg"] = error_deg

        if error_deg < ENABLE_ERROR_DEG:
            return result

        start_q = data.qpos[qpos_ids].copy()
        start_position = data.xpos[int(position_body)].copy()
        start_error = float(np.linalg.norm(error_vector))

        jacp = np.zeros((3, model.nv))
        jacr = np.zeros((3, model.nv))
        mujoco.mj_jacBody(model, data, jacp, jacr, int(position_body))
        j_pos = jacp[:, dof_ids[:4]]
        j_pos_pinv = base.damped_pseudoinverse(j_pos, float(base.POSITION_DAMPING))
        nullspace = np.eye(4) - j_pos_pinv @ j_pos

        ojp = np.zeros((3, model.nv))
        ojr = np.zeros((3, model.nv))
        mujoco.mj_jacBody(model, data, ojp, ojr, int(orientation_body))
        j_rot_null = ojr[:, dof_ids[:4]] @ nullspace
        j_rot_pinv = base.damped_pseudoinverse(j_rot_null, DAMPING)
        delta = nullspace @ (j_rot_pinv @ error_vector)
        cap = math.radians(MAX_PROXIMAL_STEP_DEG)
        delta = np.clip(delta, -cap, cap)

        accepted = False
        accepted_drift = 0.0
        for index in range(LINE_SEARCH_STEPS):
            scale = 0.5 ** index
            data.qpos[qpos_ids] = start_q
            data.qpos[qpos_ids[:4]] = start_q[:4] + scale * delta
            base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
            mujoco.mj_forward(model, data)

            drift = float(np.linalg.norm(data.xpos[int(position_body)] - start_position))
            if drift > MAX_POSITION_DRIFT_M:
                continue
            if base.has_right_arm_core_contact(model, data, context):
                continue

            trial_rotation = data.xmat[int(orientation_body)].reshape(3, 3)
            trial_error = float(np.linalg.norm(_error_vector(base, target, trial_rotation)))
            if trial_error >= start_error - 1e-7:
                continue

            accepted = True
            accepted_drift = drift
            break

        if not accepted:
            data.qpos[qpos_ids] = start_q
            mujoco.mj_forward(model, data)
            return result

        step_deg = float(np.linalg.norm(np.degrees(data.qpos[qpos_ids[:4]] - start_q[:4])))
        final_rotation = data.xmat[int(orientation_body)].reshape(3, 3)
        final_error_deg = _error_deg(base, target, final_rotation)
        base.RUNTIME_WRIST_ORIENTATION_ERROR_DEG = final_error_deg
        base.RUNTIME_ORIENTATION_ASSIST_ACTIVE = True
        base.RUNTIME_ORIENTATION_ASSIST_STEP_DEG = step_deg
        base.RUNTIME_ORIENTATION_ASSIST_POSITION_DRIFT_M = accepted_drift
        context["wrist_orientation_error_deg"] = final_error_deg
        context["orientation_assist_active"] = True
        context["orientation_assist_step_deg"] = step_deg
        context["orientation_assist_position_drift_m"] = accepted_drift
        return data.xpos[int(position_body)].copy()

    base.solve_right_arm_target = assisted_solver
    base._ORIENTATION_RECOVERY_INSTALLED = True

    original_writer = getattr(base, "write_runtime_status", None)
    if callable(original_writer):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["wrist_orientation_error_deg"] = float(base.RUNTIME_WRIST_ORIENTATION_ERROR_DEG)
            enriched["orientation_assist_active"] = bool(base.RUNTIME_ORIENTATION_ASSIST_ACTIVE)
            enriched["orientation_assist_step_deg"] = float(base.RUNTIME_ORIENTATION_ASSIST_STEP_DEG)
            enriched["orientation_assist_position_drift_m"] = float(base.RUNTIME_ORIENTATION_ASSIST_POSITION_DRIFT_M)
            enriched["orientation_assist_enable_deg"] = ENABLE_ERROR_DEG
            original_writer(enriched)
        base.write_runtime_status = status_writer
