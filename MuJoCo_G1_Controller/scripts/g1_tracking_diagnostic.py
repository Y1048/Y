"""Bounded local JSONL snapshots of blocked IK/trajectory steps."""
import json
from pathlib import Path


class TrackingDiagnostic:
    def __init__(self, path):
        self.path = Path(path)
        self.file = self.path.open("x", encoding="utf-8", buffering=1)
        self.previous = float("-inf")
        self.count = 0
        self.latest = None

    def record(self, now, planner_status, accepted_steps, trajectory_status,
               current, goal_position, goal_rotation, ik_target, rejected,
               planner, trajectory):
        if accepted_steps > 0 and trajectory_status == "trajectory_following":
            return
        if now-self.previous < .25 or self.count >= 2400:
            return
        probe = current if rejected is None else rejected
        valid, clearance = planner.CheckConfigurationWithClearance(probe)
        violations = []
        for joint, address in zip(planner.joint_ids, planner.qpos_ids):
            low, high = planner.model.jnt_range[joint]
            if planner.model.jnt_limited[joint] and not low-1e-9 <= probe[address] <= high+1e-9:
                violations.append({"joint_id": int(joint), "q": float(probe[address]),
                                   "lower": float(low), "upper": float(high)})
        row = {"schema": "g1.mink.blocked_step.v1", "simulation_only": True,
               "time": now, "stage": "ik" if accepted_steps == 0 else "trajectory",
               "planner_status": planner_status, "accepted_steps": accepted_steps,
               "trajectory_status": trajectory_status,
               "current_q": current.tolist(), "goal_position": goal_position.tolist(),
               "goal_rotation": goal_rotation.tolist(), "ik_target_q": ik_target.tolist(),
               "rejected_q": None if rejected is None else rejected.tolist(),
               "probe_valid": bool(valid), "probe_clearance_m": clearance,
               "required_clearance_m": planner.clearance_m, "joint_violations": violations,
               "velocity_limits": list(trajectory.velocity_limits),
               "acceleration_limits": list(trajectory.acceleration_limits)}
        self.file.write(json.dumps(row)+"\n")
        self.latest = {key: row[key] for key in ("stage", "planner_status", "trajectory_status",
                       "probe_valid", "probe_clearance_m", "joint_violations", "time")}
        self.previous = now
        self.count += 1

    def close(self):
        self.file.close()
