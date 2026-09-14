"""Build a command-incapable, bounded excitation plan for later review.

This module only describes trajectories.  It has no SDK, DDS, socket, process,
controller, publisher, or execution path.
"""
from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path

from sysid_capture import JOINT_NAMES, canonical, decode


SCHEMA = "g1.sysid.excitation-request.v1"
PLAN_SCHEMA = "g1.sysid.excitation-plan.v1"
RIGHT_ARM = tuple(range(22, 29))
_MAX_QUINTIC_SPEED = 1.875
_MAX_QUINTIC_ACCELERATION = 10.0 / math.sqrt(3.0)


def _finite_vector(value, length, name, *, positive=False):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{name}_must_have_{length}_values")
    if not all(type(x) in (int, float) and math.isfinite(x) for x in value):
        raise ValueError(f"{name}_must_be_finite")
    result = [float(x) for x in value]
    if positive and any(x <= 0 for x in result):
        raise ValueError(f"{name}_must_be_positive")
    return result


def _validate(request):
    required = {
        "schema", "contract_id", "controller_source_sha256", "joint_indices",
        "start_q_rad", "soft_lower_q_rad", "soft_upper_q_rad", "kp_nm_rad",
        "kd_nm_s_rad", "amplitude_rad", "velocity_limit_rad_s",
        "acceleration_limit_rad_s2", "sample_period_s", "hold_s", "cycles",
        "termination_owner_contract",
    }
    if not isinstance(request, dict) or set(request) != required:
        raise ValueError("request_fields")
    if request["schema"] != SCHEMA:
        raise ValueError("request_schema")
    for key in ("contract_id", "controller_source_sha256"):
        if not isinstance(request[key], str) or not request[key].strip():
            raise ValueError(f"{key}_required")
    if len(request["controller_source_sha256"]) != 64 or any(
            x not in "0123456789abcdef" for x in request["controller_source_sha256"]):
        raise ValueError("controller_source_sha256")
    owner = request["termination_owner_contract"]
    if (not isinstance(owner, dict) or set(owner) != {"status", "description"} or
            owner["status"] not in ("unresolved", "reviewed") or
            not isinstance(owner["description"], str) or not owner["description"].strip()):
        raise ValueError("termination_owner_contract")
    if request["joint_indices"] != list(RIGHT_ARM):
        raise ValueError("right_arm_joint_order")
    start = _finite_vector(request["start_q_rad"], 29, "start_q_rad")
    lower = _finite_vector(request["soft_lower_q_rad"], 29, "soft_lower_q_rad")
    upper = _finite_vector(request["soft_upper_q_rad"], 29, "soft_upper_q_rad")
    kp = _finite_vector(request["kp_nm_rad"], 29, "kp_nm_rad", positive=True)
    kd = _finite_vector(request["kd_nm_s_rad"], 29, "kd_nm_s_rad", positive=True)
    amplitude = _finite_vector(request["amplitude_rad"], 7, "amplitude_rad", positive=True)
    velocity = _finite_vector(request["velocity_limit_rad_s"], 7, "velocity_limit_rad_s", positive=True)
    acceleration = _finite_vector(request["acceleration_limit_rad_s2"], 7, "acceleration_limit_rad_s2", positive=True)
    for index, q in enumerate(start):
        if not lower[index] < q < upper[index]:
            raise ValueError(f"start_outside_soft_limits_joint_{index}")
    for local, index in enumerate(RIGHT_ARM):
        if start[index] - amplitude[local] < lower[index] or start[index] + amplitude[local] > upper[index]:
            raise ValueError(f"excitation_outside_soft_limits_joint_{index}")
    dt = request["sample_period_s"]
    hold = request["hold_s"]
    cycles = request["cycles"]
    if type(dt) not in (int, float) or not math.isfinite(dt) or dt <= 0:
        raise ValueError("sample_period_s")
    if type(hold) not in (int, float) or not math.isfinite(hold) or hold < dt:
        raise ValueError("hold_s")
    if type(cycles) is not int or cycles < 1:
        raise ValueError("cycles")
    return start, lower, upper, kp, kd, amplitude, velocity, acceleration, float(dt), float(hold), cycles


def _duration(delta, velocity, acceleration, dt):
    raw = max(
        _MAX_QUINTIC_SPEED * abs(delta) / velocity,
        math.sqrt(_MAX_QUINTIC_ACCELERATION * abs(delta) / acceleration),
        2.0 * dt,
    )
    return math.ceil(raw / dt) * dt


def _episode(order, first_sign, amplitude, velocity, acceleration, dt, hold, cycles):
    order = tuple(order)
    segments = [{"kind": "hold", "offset_rad": 0.0, "duration_s": hold}]
    for local in order:
        index = RIGHT_ARM[local]
        for _ in range(cycles):
            positions = (0.0, first_sign * amplitude[local], 0.0,
                         -first_sign * amplitude[local], 0.0)
            for begin, end in zip(positions[:-1], positions[1:]):
                duration = _duration(end - begin, velocity[local], acceleration[local], dt)
                segments.append({
                    "kind": "quintic_move", "joint_index": index,
                    "joint_name": JOINT_NAMES[index], "start_offset_rad": begin,
                    "end_offset_rad": end, "duration_s": duration,
                    "analytic_peak_velocity_rad_s": _MAX_QUINTIC_SPEED * abs(end - begin) / duration,
                    "analytic_peak_acceleration_rad_s2": _MAX_QUINTIC_ACCELERATION * abs(end - begin) / duration**2,
                })
                segments.append({"kind": "hold", "joint_index": index,
                                 "joint_name": JOINT_NAMES[index],
                                 "offset_rad": end, "duration_s": hold})
    return {"joint_order": [RIGHT_ARM[x] for x in order], "segments": segments,
            "duration_s": sum(x["duration_s"] for x in segments)}


def build(request):
    (start, lower, upper, kp, kd, amplitude, velocity, acceleration,
     dt, hold, cycles) = _validate(request)
    request_hash = hashlib.sha256(canonical(request)).hexdigest()
    train = _episode(range(7), 1.0, amplitude, velocity, acceleration, dt, hold, cycles)
    validation = _episode(reversed(range(7)), -1.0, amplitude, velocity, acceleration, dt, hold, cycles)
    return {
        "schema": PLAN_SCHEMA,
        "request_sha256": request_hash,
        "contract_id": request["contract_id"],
        "command_capable": False,
        "execution_authorized": False,
        "joint_indices": list(RIGHT_ARM),
        "joint_names": [JOINT_NAMES[x] for x in RIGHT_ARM],
        "start_q_rad": start,
        "soft_lower_q_rad": lower,
        "soft_upper_q_rad": upper,
        "kp_nm_rad": kp,
        "kd_nm_s_rad": kd,
        "sample_period_s": dt,
        "termination_owner_contract": request["termination_owner_contract"].copy(),
        "episodes": {"training": train, "validation": validation},
        "recommended_hardware_gains": None,
        "limitations": [
            "trajectory description only; no controller or execution path",
            "bounds are only as valid as the supplied start pose and soft limits",
            "termination ownership must be independently reviewed before physical use",
            "validation thresholds must be frozen before validation data is opened",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build(decode(args.request.read_bytes()))
    with args.output.open("xb") as stream:
        stream.write(canonical(result))


if __name__ == "__main__":
    main()
