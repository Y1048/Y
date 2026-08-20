"""Low-overhead runtime performance metrics for right-arm teleoperation."""

from __future__ import annotations

from dataclasses import dataclass, field
import math


@dataclass
class ScalarMetric:
    alpha: float = 0.15
    current: float = 0.0
    ema: float = 0.0
    peak: float = 0.0
    initialized: bool = False

    def update(self, value: float) -> None:
        value = float(value)
        if not math.isfinite(value):
            return
        self.current = value
        if not self.initialized:
            self.ema = value
            self.peak = value
            self.initialized = True
        else:
            self.ema = self.alpha * value + (1.0 - self.alpha) * self.ema
            self.peak = max(self.peak, value)

    def snapshot(self) -> dict[str, float]:
        return {
            "current": self.current,
            "ema": self.ema,
            "peak": self.peak,
        }


@dataclass
class TeleopPerformanceMonitor:
    """Collect metrics already available in the control loop with little overhead."""

    ema_alpha: float = 0.15
    position_error_m: ScalarMetric = field(init=False)
    rotation_error_deg: ScalarMetric = field(init=False)
    reference_lag_m: ScalarMetric = field(init=False)
    control_loop_hz: ScalarMetric = field(init=False)
    packet_rate_hz: ScalarMetric = field(init=False)
    samples: int = 0
    workspace_limited_samples: int = 0
    collision_limited_samples: int = 0
    accepted_packets: int = 0
    rejected_packets: int = 0
    _last_loop_time_s: float | None = None
    _last_packet_time_s: float | None = None

    def __post_init__(self) -> None:
        self.position_error_m = ScalarMetric(self.ema_alpha)
        self.rotation_error_deg = ScalarMetric(self.ema_alpha)
        self.reference_lag_m = ScalarMetric(self.ema_alpha)
        self.control_loop_hz = ScalarMetric(self.ema_alpha)
        self.packet_rate_hz = ScalarMetric(self.ema_alpha)

    def observe_loop(self, now_s: float) -> None:
        if self._last_loop_time_s is not None:
            dt = float(now_s) - self._last_loop_time_s
            if dt > 0.0:
                self.control_loop_hz.update(1.0 / dt)
        self._last_loop_time_s = float(now_s)

    def observe_packets(self, now_s: float, accepted: int, rejected: int = 0) -> None:
        accepted = max(0, int(accepted))
        rejected = max(0, int(rejected))
        self.accepted_packets += accepted
        self.rejected_packets += rejected
        if accepted > 0:
            if self._last_packet_time_s is not None:
                dt = float(now_s) - self._last_packet_time_s
                if dt > 0.0:
                    self.packet_rate_hz.update(accepted / dt)
            self._last_packet_time_s = float(now_s)

    def observe_control(
        self,
        *,
        position_error_m: float,
        rotation_error_deg: float,
        reference_lag_m: float,
        workspace_limited: bool,
        collision_limited: bool,
    ) -> None:
        self.position_error_m.update(position_error_m)
        self.rotation_error_deg.update(rotation_error_deg)
        self.reference_lag_m.update(reference_lag_m)
        self.samples += 1
        self.workspace_limited_samples += int(bool(workspace_limited))
        self.collision_limited_samples += int(bool(collision_limited))

    def snapshot(self) -> dict[str, object]:
        denominator = max(1, self.samples)
        return {
            "control_loop_hz": self.control_loop_hz.snapshot(),
            "packet_rate_hz": self.packet_rate_hz.snapshot(),
            "position_error_m": self.position_error_m.snapshot(),
            "rotation_error_deg": self.rotation_error_deg.snapshot(),
            "reference_lag_m": self.reference_lag_m.snapshot(),
            "workspace_limit_ratio": self.workspace_limited_samples / denominator,
            "collision_limit_ratio": self.collision_limited_samples / denominator,
            "accepted_packets": self.accepted_packets,
            "rejected_packets": self.rejected_packets,
            "samples": self.samples,
        }
