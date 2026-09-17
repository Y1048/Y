"""In-process kinematic return, sharing the checked tracking trajectory.

No transport or physical control. The supplied configuration is the local model.
"""
import numpy as np

SAFE_RIGHT_ARM_RAD = np.deg2rad([10., -35., 0., 70., 0., 0., 0.])


class SimulationReturnCycle:
    def __init__(self, home, trajectory, ack_ready=None, safe_waypoint=None):
        self.ack_ready = ack_ready
        self.home = np.asarray(home, dtype=float).copy()
        self.trajectory = trajectory
        self.safe_waypoint = self.home.copy()
        right_ids = np.asarray(self.trajectory.right_qpos_ids, dtype=int)
        waypoint_right = (SAFE_RIGHT_ARM_RAD if safe_waypoint is None
                          else np.asarray(safe_waypoint, dtype=float))
        if waypoint_right.shape != (7,) or not np.isfinite(waypoint_right).all():
            raise ValueError("safe_waypoint must contain seven finite joints")
        self.safe_waypoint[right_ids] = waypoint_right
        self.epoch = -1
        self.started = None
        self.previous = None
        self.settled = 0.
        self.reason = ""
        self.rejection = None
        self.stage = "inactive"

    def step(self, stream, configuration, now):
        if stream.return_state != "returning":
            return None
        if self.epoch != stream.return_epoch:
            self.epoch = stream.return_epoch
            self.started = self.previous = now
            self.settled = 0.
            self.stage = "safe_waypoint"
            if hasattr(self.trajectory, "BeginReturn"):
                self.trajectory.BeginReturn(configuration.q.copy())
            elif hasattr(self.trajectory, "Reset"):
                self.trajectory.Reset(configuration.q.copy())
        if not np.isfinite(now) or now < self.previous or now-self.previous > .25:
            self.reason = "return_clock"
        elif now-self.started > 30.:
            self.reason = "return_timeout"
        if self.reason:
            stream.return_state = "fault"
            return None
        dt = now-self.previous
        self.previous = now
        target = self.safe_waypoint if self.stage == "safe_waypoint" else self.home
        step = self.trajectory.Step(configuration.q.copy(), target)
        if not step.applied:
            self.reason = step.status
            sample = self.trajectory.rejected_sample
            planner = self.trajectory.planner
            if sample is not None:
                self.rejection = {"q": sample.tolist(), "home": self.home.tolist(),
                                  "stage": self.stage,
                                  "stage_target": target.tolist(),
                                  "current": configuration.q.tolist(),
                                  "clearance_m": float(planner.GetClearance(sample)),
                                  "required_clearance_m": planner.clearance_m}
            stream.return_state = "fault"
            return step
        configuration.update(step.q)
        ids = self.trajectory.right_qpos_ids
        reached = (np.max(np.abs(configuration.q[ids]-target[ids])) < 1e-6
                   and max(abs(x) for x in step.velocity_rad_s) < 1e-6)
        if reached and self.stage == "safe_waypoint":
            self.stage = "home"
            self.settled = 0.
            if hasattr(self.trajectory, "Reset"):
                self.trajectory.Reset(configuration.q.copy())
            return step
        self.settled = self.settled+dt if reached else 0.
        if self.settled >= .5 and (self.ack_ready is None or self.ack_ready(self.epoch, stream.return_session)):
            if not stream.acknowledge_simulation_return(self.epoch, stream.return_session):
                self.reason = "return_ack_rejected"
                stream.return_state = "fault"
            else:
                self.stage = "complete"
        return step
