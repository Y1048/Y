"""Local, fixed-pelvis MuJoCo PD experiment. NEVER creates DDS or robot I/O.

The existing VR/Mink/relay/hardware programs are not imported or modified.
qpos is initialized once; subsequent states are produced only by mj_step.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np

from mujoco_pd_contract import (ROOT, REFERENCE, REFERENCE_DT, WRITER_DT,
                                RoundTrip, candidate_gains, load_contract, writer_target)

from mujoco_pd_fixture import ROOT_PARENT_PAIRS, preserve_root_parent_filter

MODEL = ROOT / "MuJoCo_G1_Controller/external/unitree_mujoco/unitree_robots/g1/g1_29dof.xml"
# This shared module contains only the canonical tuple and typing imports.
sys.path.insert(0, str(ROOT / "hardware/g1_arm_bridge"))
from g1_joint_contract import G1_29_JOINT_NAMES

WARMUP = 3.0
JOINTS = tuple(name + "_joint" for name in G1_29_JOINT_NAMES)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(paths: list[Path]) -> dict[str, str]:
    """Normalize runpy's relative __file__ before writing repository-relative keys."""
    resolved = [path.resolve() for path in paths]
    return {str(path.relative_to(ROOT)): sha256(path) for path in resolved}


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_model(path: Path, timestep: float):
    """Modify an XML copy in memory. Preserve masses, inertias and collisions."""
    import mujoco

    if not math.isfinite(timestep) or timestep <= 0 or timestep > WRITER_DT:
        raise ValueError("timestep must be finite, positive and <= 0.002 s")
    if not math.isclose(WRITER_DT / timestep, round(WRITER_DT / timestep), abs_tol=1e-9):
        raise ValueError("timestep must divide the 0.002 s writer period exactly")
    path = path.resolve()
    tree = ET.fromstring(path.read_text(encoding="utf-8"))
    if tree.findall(".//include"):
        raise ValueError("Use the standalone g1_29dof.xml, not an included scene")
    pelvis = tree.find("./worldbody/body[@name='pelvis']")
    if pelvis is None:
        raise ValueError("Model is missing pelvis")
    free = pelvis.find("joint[@name='floating_base_joint']")
    if free is None or free.get("type") != "free":
        raise ValueError("Expected the unmodified G1 free-base source model")
    preserve_root_parent_filter(tree, pelvis)
    pelvis.remove(free)  # fixed fixture; NOT evidence about standing balance
    compiler = tree.find("compiler")
    if compiler is None:
        raise ValueError("Model compiler settings missing")
    meshdir = (path.parent / compiler.get("meshdir", ".")).resolve()
    compiler.set("meshdir", str(meshdir))
    manifest = {str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path): sha256(path)}
    for mesh in tree.findall("./asset/mesh"):
        asset = meshdir / mesh.attrib["file"]
        manifest[str(asset.relative_to(path.parent))] = sha256(asset)
    option = tree.find("option")
    if option is None:
        option = ET.SubElement(tree, "option")
    option.set("timestep", str(timestep))
    option.set("integrator", "implicitfast")
    option.set("gravity", "0 0 -9.81")
    ET.SubElement(tree.find("worldbody"), "light", pos="1 -1 3", dir="-1 1 -2")
    model = mujoco.MjModel.from_xml_string(ET.tostring(tree, encoding="unicode"))
    if model.nq != 29 or model.nv != 29 or model.nu != 29:
        raise ValueError("Expected 29 hinges and 29 motors after fixing pelvis")
    joint_ids = np.array([mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name) for name in JOINTS])
    if np.any(joint_ids < 0) or len(set(joint_ids)) != 29:
        raise ValueError("Canonical G1 joints missing or duplicated")
    qadr, vadr = model.jnt_qposadr[joint_ids].copy(), model.jnt_dofadr[joint_ids].copy()
    motor_ids = []
    for joint in joint_ids:
        matches = np.flatnonzero(model.actuator_trnid[:, 0] == joint)
        if len(matches) != 1:
            raise ValueError("Require exactly one torque motor per hinge")
        motor_ids.append(int(matches[0]))
    motors = np.array(motor_ids)
    if (np.any(model.jnt_type[joint_ids] != mujoco.mjtJoint.mjJNT_HINGE)
        or np.any(model.actuator_trntype[motors] != mujoco.mjtTrn.mjTRN_JOINT)
        or np.any(model.actuator_dyntype[motors] != mujoco.mjtDyn.mjDYN_NONE)
        or np.any(model.actuator_biastype[motors] != mujoco.mjtBias.mjBIAS_NONE)
        or np.any(model.actuator_gaintype[motors] != mujoco.mjtGain.mjGAIN_FIXED)
        or not np.allclose(model.actuator_gainprm[motors, 0], 1)
        or not np.allclose(model.actuator_gear[motors], np.tile([1, 0, 0, 0, 0, 0], (29, 1)))
        or not np.all(model.actuator_ctrllimited[motors])):
        raise ValueError("Model must use unit-gear direct torque motors, not hidden position servos")
    return model, qadr, vadr, motors, manifest


def summarize(rows: list[dict], completed: bool, reason: str, max_limit_ratio: float) -> dict:
    samples = [r for r in rows if r["trial_time_s"] >= 0]
    result = {"completed": completed, "reason": reason, "samples": len(samples),
              "eligible": False, "exclusion_reasons": [], "metrics": None}
    if not samples:
        result["exclusion_reasons"] = [reason or "no_trial_samples"]
        return result
    error = np.array([r["ref_22"] - r["q_22"] for r in samples])
    cmd_error = np.array([r["cmd_22"] - r["q_22"] for r in samples])
    holds = [r for r in samples if r["phase"] in (3, 5)]
    overshoot = max([0.] + [r["direction"] * (r["q_22"] - r["ref_22"]) for r in holds])
    end_holds = []
    for cycle in range(3):
        for segment in ("positive_hold", "negative_hold", "ready_hold"):
            window = [r for r in holds if r["cycle"] == cycle and r["segment"] == segment]
            if not window:
                continue
            # Time until the remaining recorded hold stays inside this band.
            ok = np.array([abs(r["q_22"]-r["ref_22"]) <= .02 and abs(r["dq_22"]) <= .1 for r in window])
            suffix_ok = np.logical_and.accumulate(ok[::-1])[::-1]
            indices = np.flatnonzero(suffix_ok)
            settling = None if not indices.size else window[int(indices[0])]["time_s"] - window[0]["time_s"]
            end_holds.append({"cycle": cycle, "segment": segment, "settling_time_s": settling,
                              "recorded_hold_duration_s": window[-1]["time_s"]-window[0]["time_s"],
                              "terminal_error_rad": window[-1]["q_22"]-window[-1]["ref_22"]})
    limited = float(np.mean([r["torque_target_limited_arm"] for r in samples]))
    slew = float(np.mean([r["slew_exceeded_arm"] for r in samples]))
    metrics = {
        "reference_rmse_joint22_rad": float(np.sqrt(np.mean(error**2))),
        "command_rmse_joint22_rad": float(np.sqrt(np.mean(cmd_error**2))),
        "peak_reference_error_joint22_rad": float(np.max(np.abs(error))),
        "peak_hold_overshoot_joint22_rad": float(overshoot),
        "peak_speed_joint22_rad_s": max(abs(r["dq_22"]) for r in samples),
        "peak_torque_joint22_nm": max(abs(r["actual_tau_22"]) for r in samples),
        "rms_torque_joint22_nm": float(np.sqrt(np.mean([r["actual_tau_22"]**2 for r in samples]))),
        "torque_target_limit_arm_sample_ratio": limited,
        "hard_clip_arm_sample_ratio": float(np.mean([r["hard_clipped_arm"] for r in samples])),
        "slew_exceeded_arm_sample_ratio": slew,
        "contact_sample_ratio": float(np.mean([r["contacts"] > 0 for r in samples])),
        "endpoint_holds": end_holds,
        "joints": [{"joint": j,
                     "reference_rmse_rad": float(np.sqrt(np.mean([(r[f"ref_{j}"]-r[f"q_{j}"])**2 for r in samples]))),
                     "peak_abs_speed_rad_s": max(abs(r[f"dq_{j}"]) for r in samples),
                     "peak_abs_torque_nm": max(abs(r[f"actual_tau_{j}"]) for r in samples)} for j in range(22, 29)]}
    result["metrics"] = metrics
    if not completed:
        result["exclusion_reasons"].append(reason)
    if limited > max_limit_ratio or metrics["hard_clip_arm_sample_ratio"] > max_limit_ratio:
        result["exclusion_reasons"].append("excessive_torque_limiting")
    # A contact-influenced result is visible but never silently ranked as free-space tuning.
    if metrics["contact_sample_ratio"] > 0:
        result["exclusion_reasons"].append("contact_influenced")
    result["eligible"] = not result["exclusion_reasons"]
    return result


def run_candidate(model, qadr, vadr, motors, contract, kp_value: float, kd_value: float,
                  *, viewer: bool = False, max_limit_ratio: float = .05) -> tuple[dict, list[dict]]:
    import mujoco

    kp, kd = candidate_gains(contract, kp_value, kd_value)
    data = mujoco.MjData(model)  # reset simulation, controller, and warm starts for EVERY candidate
    data.qpos[qadr] = contract.baseline
    data.qvel[:] = 0
    mujoco.mj_forward(model, data)
    path = RoundTrip()
    dt = float(model.opt.timestep)
    writer_stride = round(WRITER_DT / dt)
    reference_stride = round(REFERENCE_DT / dt)
    warmup_steps = round(WARMUP / dt)
    total_steps = warmup_steps + math.ceil(path.total / dt)
    reference = contract.baseline.copy()
    command = reference.copy()
    limited = np.zeros(29, dtype=bool)
    slew = limited.copy()
    point = path.at(0)
    rows, warmup_tail = [], []
    reason, completed = "", False
    handle = None
    wall_start = time.monotonic()
    try:
        if viewer:
            import mujoco.viewer
            handle = mujoco.viewer.launch_passive(model, data)
            handle.cam.lookat[:] = [0, 0, 1.0]
            handle.cam.distance = 2.4
            handle.cam.azimuth = 135
            handle.cam.elevation = -12
        for step in range(total_steps):
            sim_time = step * dt
            trial_time = (step - warmup_steps) * dt
            q, dq = data.qpos[qadr].copy(), data.qvel[vadr].copy()
            if not np.isfinite(q).all() or not np.isfinite(dq).all():
                reason = "nonfinite_state"
                break
            if np.any(q < contract.lower) or np.any(q > contract.upper):
                reason = "joint_soft_limit"
                break
            if np.max(np.abs(dq[12:])) > 1.5 or np.max(np.abs(dq[:12])) > 12:
                reason = "measured_velocity_limit"
                break
            if step == warmup_steps:
                if not warmup_tail or not all(warmup_tail):
                    reason = "ready_pose_not_settled_in_final_warmup_second"
                    break
            if step % reference_stride == 0:
                point = path.at(max(0., trial_time))
                reference = contract.baseline.copy()
                if trial_time >= 0:
                    reference[22] += point.offset
            if np.max(np.abs(q[12:]-reference[12:])) > .25:
                reason = "upper_reference_error_over_0.25_rad"
                break
            if step % writer_stride == 0:
                command, limited, slew = writer_target(reference, command, q, dq, kp, kd, contract)
            # Ideal PD motor at physics rate; command held at 500 Hz, reference at 50 Hz.
            # dq_cmd=0 and tau_ff=0: no analytic desired velocity/gravity compensation.
            requested = kp * (command - q) - kd * dq
            ctrl = np.clip(requested, model.actuator_ctrlrange[motors, 0], model.actuator_ctrlrange[motors, 1])
            data.ctrl[motors] = ctrl
            mujoco.mj_step(model, data)
            if np.any(data.warning.number) or not math.isclose(data.time, sim_time+dt, abs_tol=1e-7):
                reason = "mujoco_warning_or_state_reset"
                break
            if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                reason = "nonfinite_integrated_state"
                break
            if WARMUP-1 <= sim_time < WARMUP:
                warmup_tail.append(bool(np.max(np.abs(q[15:]-reference[15:])) <= .1 and np.max(np.abs(dq[15:])) <= .1))
            if step % writer_stride == 0:
                row = {"time_s": sim_time, "trial_time_s": trial_time,
                       "phase": point.phase if trial_time >= 0 else 0,
                       "cycle": point.cycle, "segment": point.segment if trial_time >= 0 else "warmup",
                       "direction": point.direction, "kp_proximal": kp_value, "kd_proximal": kd_value,
                       "analytic_reference_dq22": point.velocity if trial_time >= 0 else 0.,
                       "torque_target_limited_arm": int(np.any(limited[22:])),
                       "slew_exceeded_arm": int(np.any(slew[22:])),
                       "hard_clipped_arm": int(np.any(np.abs(requested[22:]-ctrl[22:]) > 1e-7)),
                       "contacts": int(data.ncon)}
                for j in range(29):
                    row.update({f"ref_{j}": float(reference[j]), f"cmd_{j}": float(command[j]),
                                f"q_{j}": float(q[j]), f"dq_{j}": float(dq[j]),
                                f"tau_requested_{j}": float(requested[j]), f"actual_tau_{j}": float(data.actuator_force[motors[j]])})
                rows.append(row)
            if handle is not None and step % reference_stride == 0:
                if not handle.is_running():
                    reason = "viewer_closed"
                    break
                handle.sync()
                time.sleep(max(0., wall_start + sim_time - time.monotonic()))
        else:
            completed = True
    finally:
        if handle is not None:
            handle.close()
    result = summarize(rows, completed, reason, max_limit_ratio)
    result.update({"kp_proximal": kp_value, "kd_proximal": kd_value,
                   "gains_kp": kp.tolist(), "gains_kd": kd.tolist()})
    return result, rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kp-values", nargs="+", type=float, default=[40, 48, 56])
    parser.add_argument("--kd-values", nargs="+", type=float, default=[5])
    parser.add_argument("--timestep", type=float, default=.001)
    parser.add_argument("--max-limit-ratio", type=float, default=.05)
    parser.add_argument("--viewer", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.max_limit_ratio) or not 0 <= args.max_limit_ratio <= 1:
            raise ValueError("max-limit-ratio must be finite and in [0,1]")
        contract = load_contract()
        grid = list(itertools.product(args.kp_values, args.kd_values))
        if len(grid) > 100 or len(set(grid)) != len(grid):
            raise ValueError("Use 1..100 unique gain pairs")
        for kp, kd in grid:
            candidate_gains(contract, kp, kd)
        import mujoco
        model, qadr, vadr, motors, assets = load_model(MODEL, args.timestep)
        out = args.output or ROOT / "logs/test_results/mujoco_pd" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        out = out.resolve()
        out.mkdir(parents=True, exist_ok=False)
        source_paths = [Path(__file__), Path(__file__).with_name("mujoco_pd_contract.py"), REFERENCE,
                        Path(__file__).with_name("mujoco_pd_fixture.py"),
                        Path(__file__).with_name("pd_small_signal_trial.hpp"),
                        ROOT / "hardware/g1_arm_bridge/g1_joint_contract.py"]
        manifest = {"schema": "g1.mujoco.pd.run.v1", "simulation_only": True, "status": "running",
                    "model": "g1_29dof, fixed pelvis; all 29 hinges torque-driven",
                    "balance_validated": False, "hardware_validated": False,
                    "restored_source_parent_filter": list(ROOT_PARENT_PAIRS),
                    "mujoco": mujoco.__version__, "numpy": np.__version__, "python": platform.python_version(),
                    "platform": platform.platform(), "timestep_s": args.timestep,
                    "reference_hz": 50, "writer_hz": 500, "ideal_motor_hz": 1/args.timestep,
                    "warmup_s": WARMUP, "reference": "joint22 ready -> +8deg -> -8deg -> ready, 3 cycles",
                    "candidate_reset": "same ready q, zero dq; independent 3 s warmup for every pair",
                    "target_dq": 0, "feedforward_torque": 0, "profile": "yesterday",
                    "gain_joints": [22,23,24,25], "gain_pairs": grid,
                    "max_limit_ratio": args.max_limit_ratio, "initial_q": contract.baseline.tolist(),
                    "asset_sha256": assets, "source_sha256": source_hashes(source_paths),
                    "state_pairing": "q/dq at command evaluation; actual_tau from that mj_step, not a device acknowledgement",
                    "limitations": ["fixed pelvis cannot validate balance", "ideal torque motors, uncalibrated XML parameters",
                                    "no motor delay/backlash/temperature model", "no Regular service or TWIST2 leg policy"]}
        write_json(out / "run.json", manifest)
        results = []
        print(f"SIMULATION ONLY / NO DDS / output: {out}")
        for number, (kp, kd) in enumerate(grid):
            print(f"[{number+1}/{len(grid)}] fixed-pelvis round trip Kp={kp:g}, Kd={kd:g}", flush=True)
            result, rows = run_candidate(model, qadr, vadr, motors, contract, kp, kd,
                                         viewer=args.viewer, max_limit_ratio=args.max_limit_ratio)
            csv_path = out / f"candidate_{number:03d}.csv"
            if rows:
                with csv_path.open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                result["csv"] = csv_path.name
                result["csv_sha256"] = sha256(csv_path)
            results.append(result)
            print(json.dumps({k: result[k] for k in ("kp_proximal","kd_proximal","completed","eligible","reason","exclusion_reasons")}), flush=True)
            if result["reason"] == "viewer_closed":
                break
        ranked = sorted([r for r in results if r["eligible"]], key=lambda r: r["metrics"]["reference_rmse_joint22_rad"])
        summary = {"schema": "g1.mujoco.pd.sweep.v1", "simulation_only": True,
                   "sweep_complete": len(results) == len(grid) and all(r["reason"] != "viewer_closed" for r in results),
                   "candidates": results,
                   "ranking": [{"kp": r["kp_proximal"], "kd": r["kd_proximal"],
                                "reference_rmse_joint22_rad": r["metrics"]["reference_rmse_joint22_rad"]} for r in ranked],
                   "ranking_rule": "completed, no contact/numerical/guard failure, limiting <= threshold; sort joint22 ORIGINAL reference RMSE",
                   "recommended_hardware_gains": None, "hardware_config_modified": False,
                   "run_sha256": sha256(out / "run.json")}
        write_json(out / "summary.json", summary)
        print(json.dumps({"ranking": summary["ranking"], "summary": str(out / "summary.json")}, indent=2))
        return 0 if summary["sweep_complete"] and ranked else 2
    except (OSError, ValueError, ImportError, RuntimeError) as error:
        print(f"OFFLINE PD ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
