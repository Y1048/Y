"""Offline latched waist guard and saved-log threshold study, not a runtime gate."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


class WaistGuardStudy:
    def __init__(self, initial_waist, *, angle_deg, velocity_deg_s, timeout_s,
                 initial_imu_rpy=None, tilt_deg=None):
        values = tuple(float(q) for q in initial_waist)
        if len(values) != 3 or not all(math.isfinite(q) for q in values):
            raise ValueError("three finite initial waist angles required")
        if not all(math.isfinite(x) and x > 0 for x in (angle_deg, velocity_deg_s, timeout_s)):
            raise ValueError("explicit positive study limits required")
        self.initial_waist = values
        self.angle_rad = math.radians(angle_deg)
        self.velocity_rad_s = math.radians(velocity_deg_s)
        self.timeout_s = timeout_s
        self.reason = None
        self.initial_imu_rpy = None
        self.tilt_rad = None
        if (initial_imu_rpy is None) != (tilt_deg is None):
            raise ValueError("IMU baseline and explicit tilt study limit required together")
        if initial_imu_rpy is not None:
            imu = tuple(float(x) for x in initial_imu_rpy)
            if len(imu) != 3 or not all(math.isfinite(x) for x in imu):
                raise ValueError("three finite initial IMU angles required")
            if not math.isfinite(tilt_deg) or tilt_deg <= 0:
                raise ValueError("explicit positive tilt study limit required")
            self.initial_imu_rpy = imu
            self.tilt_rad = math.radians(tilt_deg)

    def Evaluate(self, waist_q, waist_dq, age_s, *, imu_rpy=None):
        """Latch a stop; optional IMU uses the same sample age, angles in radians.

        Roll/pitch deviations are axis-wise, not a certified balance metric.
        Once enabled, missing IMU is invalid rather than silently ignored.
        """
        if self.reason is not None:
            return self.reason
        try:
            q, dq = tuple(float(x) for x in waist_q), tuple(float(x) for x in waist_dq)
            if len(q) != 3 or len(dq) != 3 or not all(math.isfinite(x) for x in q + dq):
                raise ValueError("invalid waist sample")
            if not math.isfinite(age_s) or age_s < 0:
                raise ValueError("invalid sample age")
            tilt = 0.0
            if self.initial_imu_rpy is not None:
                imu = tuple(float(x) for x in imu_rpy)
                if len(imu) != 3 or not all(math.isfinite(x) for x in imu):
                    raise ValueError("invalid IMU sample")
                tilt = max(abs(math.remainder(x - origin, 2 * math.pi))
                           for x, origin in zip(imu[:2], self.initial_imu_rpy[:2]))
            if age_s > self.timeout_s:
                self.reason = "stale_state"
            elif max(abs(x - origin) for x, origin in zip(q, self.initial_waist)) > self.angle_rad:
                self.reason = "waist_angle"
            elif max(abs(x) for x in dq) > self.velocity_rad_s:
                self.reason = "waist_velocity"
            elif self.tilt_rad is not None and tilt > self.tilt_rad:
                self.reason = "imu_tilt"
        except (TypeError, ValueError):
            self.reason = "invalid_state"
        return self.reason


def AnalyzeCapture(rows, *, angle_deg, velocity_deg_s, timeout_s):
    ready = next((r for r in rows if r.get("details", {}).get("schedule_phase") == "READY"), None)
    if ready is None:
        raise ValueError("READY baseline missing")
    guard = WaistGuardStudy(ready["details"]["measured_all_q_rad"][12:15],
        angle_deg=angle_deg, velocity_deg_s=velocity_deg_s, timeout_s=timeout_s)
    first_stop = None
    samples = 0
    for row in rows:
        details = row.get("details", {})
        if not details.get("sampled_command"):
            continue
        samples += 1
        reason = guard.Evaluate(details.get("measured_all_q_rad", [])[12:15],
            details.get("measured_all_dq_rad_s", [])[12:15], details.get("lowstate_age_s"))
        if reason is not None:
            first_stop = {"reason": reason, "phase": details["schedule_phase"],
                "weight": details["weight"],
                "sample_write_unix_ns": details.get("last_successful_write_unix_ns"),
                "seconds_after_ready": row["updated_at_unix"] - ready["updated_at_unix"]}
            break
    if samples == 0:
        raise ValueError("no command samples; cannot report a clean capture")
    return {"angle_deg": angle_deg, "velocity_deg_s": velocity_deg_s,
            "timeout_s": timeout_s, "first_stop": first_stop}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    captures = []
    for path in sorted(args.capture_root.glob("gate6_hold_*/events.jsonl")):
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        config = json.loads((path.parent / "config.json").read_text(encoding="utf-8"))
        captures.append({"path": str(path.resolve()), "weight": config["maximum_weight"],
            "studies": [AnalyzeCapture(rows, angle_deg=angle, velocity_deg_s=speed, timeout_s=0.25)
                        for angle in (1.0, 2.0, 3.0) for speed in (5.0, 10.0, 20.0)]})
    if not captures:
        raise ValueError("no saved HOLD captures; no hardware will be started")
    result = {"schema": "g1.waist_guard.offline_study.v1", "offline_only": True,
        "hardware_authorized": False, "captures": captures,
        "limitations": ["Thresholds are exploratory, not physical authorization.",
            "Sparse recorded samples cannot establish peak values or real detection latency.",
            "No prediction of motion after a hypothetical stop or of balance recovery."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for capture in captures:
        count = sum(item["first_stop"] is not None for item in capture["studies"])
        print(f"weight={capture['weight']}: {count}/9 study settings detect a stop")
    print("Offline only: no SDK, network or robot commands.")
    print(f"Result saved to: {args.output.resolve()}")


if __name__ == "__main__":
    main()
