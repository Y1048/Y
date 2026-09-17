"""Offline Mink-to-TWIST2 upper-target study; no socket, SDK or C++ integration."""

import math
import sys
from pathlib import Path

BRIDGE_PATH = Path(__file__).resolve().parents[2] / "hardware" / "g1_arm_bridge"
if str(BRIDGE_PATH) not in sys.path:
    sys.path.insert(0, str(BRIDGE_PATH))

from arm_sdk_teleop_contract import parse_mink_arm_sample
from arm_sdk_hold_contract import RIGHT_ARM_LIMITS_RAD


class VRInputStudy:
    """Explicit session baseline; stop latches until a new study is created.

    Input q is absolute motor radians, not wrist coordinates or relative deltas.
    Output is only the upper-target input to hybrid_target, never LowCmd.
    """

    def __init__(self, captured_q, *, session_id, initial_sequence, now_s,
                 maximum_delta_rad, timeout_s):
        q = tuple(float(x) for x in captured_q)
        if len(q) != 29 or not all(math.isfinite(x) for x in q):
            raise ValueError("29 finite captured joint angles required")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("explicit session required")
        if type(initial_sequence) is not int or initial_sequence < 0:
            raise ValueError("explicit initial sequence required")
        if not all(math.isfinite(x) and x > 0 for x in (maximum_delta_rad, timeout_s)):
            raise ValueError("explicit positive study limits required")
        if not math.isfinite(now_s) or now_s < 0:
            raise ValueError("finite monotonic start time required")
        for value, (lower, upper) in zip(q[22:29], RIGHT_ARM_LIMITS_RAD):
            if not lower <= value <= upper:
                raise ValueError("captured right arm outside model joint limits")
        self.captured_q = q
        self.target_q = q
        self.session_id = session_id.strip()
        self.sequence = initial_sequence
        self.time_s = now_s
        self.receipt_s = now_s
        self.maximum_delta_rad = maximum_delta_rad
        self.timeout_s = timeout_s
        self.reason = None

    def GetResult(self, mode):
        return {"schema": "g1.twist2.upper_target.offline.v1", "offline_only": True,
                "hardware_output_authorized": False, "mode": mode, "reason": self.reason,
                "upper_target_q_rad": self.target_q, "updated_indices": list(range(22, 29)),
                "joint_velocity_limit_rad_s": 0.08}

    def Step(self, payload, *, now_s, received_s=None):
        """Process one new packet at a simulated 50 Hz policy tick.

        Missing packets freeze the target; timeout or invalid packets latch stop.
        Receipt times must share the caller's monotonic clock. Sender wall time
        is not compared with it. This is not a physical safety gate.
        """
        if self.reason is not None:
            return self.GetResult("stopped")
        try:
            if not math.isfinite(now_s) or now_s <= self.time_s:
                raise ValueError("non_increasing_clock")
            dt = min(now_s - self.time_s, 0.02)
            self.time_s = now_s
            if now_s - self.receipt_s > self.timeout_s:
                raise ValueError("receiver_timeout")
            if payload is None:
                return self.GetResult("waiting")
            if (received_s is None or not math.isfinite(received_s)
                    or received_s < self.receipt_s or received_s > now_s):
                raise ValueError("invalid_receipt_time")
            sample = parse_mink_arm_sample(payload)
            if sample.session_id != self.session_id:
                raise ValueError("session_changed")
            if sample.sequence <= self.sequence:
                raise ValueError("sequence_not_increasing")
            if sample.input_command_mode != "active" or not sample.active:
                raise ValueError("input_disengaged")
            if (sample.input_packet_age_s is None
                    or sample.input_packet_age_s + now_s - received_s > self.timeout_s):
                raise ValueError("source_timeout")
            if sample.minimum_clearance_m is None or sample.minimum_clearance_m < 0:
                raise ValueError("invalid_candidate_clearance")
            for i, (lower, upper) in enumerate(RIGHT_ARM_LIMITS_RAD):
                value = sample.right_arm_q_rad[i]
                if not lower <= value <= upper:
                    raise ValueError("right_arm_joint_limit")
                if abs(value - self.captured_q[22 + i]) > self.maximum_delta_rad:
                    raise ValueError("start_relative_limit")
            target = list(self.target_q)
            for i, value in enumerate(sample.right_arm_q_rad, 22):
                difference = value - target[i]
                target[i] += max(-0.08 * dt, min(0.08 * dt, difference))
            self.target_q = tuple(target)
            self.sequence = sample.sequence
            self.receipt_s = received_s
            return self.GetResult("active")
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            self.reason = str(error)
            return self.GetResult("stopped")
