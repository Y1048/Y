#!/usr/bin/env python3
"""SDK-neutral runtime base stability guard for supported physical paths.

The monitor itself imports no Unitree SDK. ``install_unitree_base_state_subscription``
performs a lazy SDK import only when a supported physical entrypoint is actually
executed. It adds one read-only ``rt/odommodestate`` subscriber alongside the
existing LowState subscriber and never creates a publisher.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Any

from g1_base_state import (
    BASE_STATE_TOPIC,
    BasePoseNormalizer,
    InvalidBaseStateError,
    NormalizedBaseState,
    YawFromQuaternionWXYZ,
)

DEFAULT_BASE_TIMEOUT_S = 0.25
DEFAULT_MAX_TRANSLATION_M = 0.05
DEFAULT_MAX_LINEAR_SPEED_MPS = 0.15
DEFAULT_MAX_YAW_SPEED_RAD_S = 0.25
DEFAULT_MAX_RELATIVE_YAW_RAD = math.radians(8.0)
DEFAULT_MINIMUM_BASE_SAMPLES = 3
LOWSTATE_TOPIC = "rt/lowstate"


@dataclass(frozen=True)
class RuntimeBaseSnapshot:
    state: NormalizedBaseState
    received_packets: int
    invalid_packets: int
    received_monotonic_s: float


class RuntimeBaseStateMonitor:
    """Track normalized odometry relative to the first runtime sample."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._normalizer = BasePoseNormalizer()
        self._snapshot: RuntimeBaseSnapshot | None = None
        self._received = 0
        self._invalid = 0

    def callback(self, message: Any) -> None:
        now = time.monotonic()
        try:
            state = self._normalizer.Normalize(
                message.position,
                message.imu_state.quaternion,
                message.velocity,
                message.yaw_speed,
            )
        except (AttributeError, TypeError, ValueError, InvalidBaseStateError):
            with self._lock:
                self._invalid += 1
            return
        with self._lock:
            self._received += 1
            self._snapshot = RuntimeBaseSnapshot(
                state=state,
                received_packets=self._received,
                invalid_packets=self._invalid,
                received_monotonic_s=now,
            )

    def snapshot(self) -> RuntimeBaseSnapshot | None:
        with self._lock:
            return self._snapshot


RUNTIME_BASE_MONITOR = RuntimeBaseStateMonitor()
_BASE_SUBSCRIBER = None
_CHANNEL_PROXY_INSTALLED = False


def _relative_yaw_rad(state: NormalizedBaseState) -> float:
    x_value, y_value, z_value, w_value = state.quaternion_xyzw
    return YawFromQuaternionWXYZ((w_value, x_value, y_value, z_value))


def validate_runtime_base_snapshot(
    snapshot: RuntimeBaseSnapshot,
    *,
    now_monotonic_s: float | None = None,
    maximum_age_s: float = DEFAULT_BASE_TIMEOUT_S,
    maximum_translation_m: float = DEFAULT_MAX_TRANSLATION_M,
    maximum_linear_speed_mps: float = DEFAULT_MAX_LINEAR_SPEED_MPS,
    maximum_yaw_speed_rad_s: float = DEFAULT_MAX_YAW_SPEED_RAD_S,
    maximum_relative_yaw_rad: float = DEFAULT_MAX_RELATIVE_YAW_RAD,
    minimum_samples: int = DEFAULT_MINIMUM_BASE_SAMPLES,
) -> None:
    """Raise when the runtime base is stale, moving, or has drifted materially."""

    limits = (
        maximum_age_s,
        maximum_translation_m,
        maximum_linear_speed_mps,
        maximum_yaw_speed_rad_s,
        maximum_relative_yaw_rad,
    )
    if not all(math.isfinite(value) and value > 0.0 for value in limits):
        raise ValueError("runtime base limits must be finite and positive")
    if not isinstance(minimum_samples, int) or isinstance(minimum_samples, bool) or minimum_samples < 1:
        raise ValueError("minimum_samples must be a positive integer")
    if snapshot.received_packets < minimum_samples:
        raise RuntimeError(
            f"runtime base samples {snapshot.received_packets} < {minimum_samples}"
        )
    if snapshot.invalid_packets > 0:
        raise RuntimeError(
            f"runtime base observed {snapshot.invalid_packets} invalid packet(s)"
        )

    now = time.monotonic() if now_monotonic_s is None else float(now_monotonic_s)
    age_s = max(0.0, now - snapshot.received_monotonic_s)
    if age_s > maximum_age_s:
        raise RuntimeError(
            f"runtime base state stale: {age_s:.3f}s > {maximum_age_s:.3f}s"
        )

    position = snapshot.state.position_m
    translation = math.sqrt(sum(value * value for value in position))
    if translation > maximum_translation_m:
        raise RuntimeError(
            f"runtime base translation {translation:.3f}m exceeds {maximum_translation_m:.3f}m"
        )

    velocity = snapshot.state.velocity_mps
    linear_speed = math.sqrt(sum(value * value for value in velocity))
    if linear_speed > maximum_linear_speed_mps:
        raise RuntimeError(
            f"runtime base speed {linear_speed:.3f}m/s exceeds {maximum_linear_speed_mps:.3f}m/s"
        )

    yaw_speed = abs(snapshot.state.yaw_speed_rad_s)
    if yaw_speed > maximum_yaw_speed_rad_s:
        raise RuntimeError(
            f"runtime base yaw speed {yaw_speed:.3f}rad/s exceeds {maximum_yaw_speed_rad_s:.3f}rad/s"
        )

    relative_yaw = abs(_relative_yaw_rad(snapshot.state))
    if relative_yaw > maximum_relative_yaw_rad:
        raise RuntimeError(
            f"runtime base yaw drift {relative_yaw:.3f}rad exceeds {maximum_relative_yaw_rad:.3f}rad"
        )


def require_latest_runtime_base_state() -> None:
    snapshot = RUNTIME_BASE_MONITOR.snapshot()
    if snapshot is None:
        raise RuntimeError("runtime base state has not been received")
    validate_runtime_base_snapshot(snapshot)


def install_unitree_base_state_subscription() -> None:
    """Install one lazy read-only odometry subscriber beside LowState.

    This function patches the SDK's ``ChannelSubscriber`` constructor before the
    core controller imports it. When the controller initializes its LowState
    subscriber, the proxy initializes a second read-only base-state subscriber.
    No publisher is created here.
    """

    global _CHANNEL_PROXY_INSTALLED
    if _CHANNEL_PROXY_INSTALLED:
        return

    from unitree_sdk2py.core import channel as channel_module
    from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_

    original_subscriber = channel_module.ChannelSubscriber

    def ensure_base_subscriber() -> None:
        global _BASE_SUBSCRIBER
        if _BASE_SUBSCRIBER is not None:
            return
        subscriber = original_subscriber(BASE_STATE_TOPIC, SportModeState_)
        subscriber.Init(RUNTIME_BASE_MONITOR.callback, 10)
        _BASE_SUBSCRIBER = subscriber

    class GuardedChannelSubscriber:
        def __init__(self, topic, message_type):
            self._topic = str(topic)
            self._inner = original_subscriber(topic, message_type)

        def Init(self, callback, queue_size):
            result = self._inner.Init(callback, queue_size)
            if self._topic == LOWSTATE_TOPIC:
                ensure_base_subscriber()
            return result

        def __getattr__(self, name):
            return getattr(self._inner, name)

    channel_module.ChannelSubscriber = GuardedChannelSubscriber
    _CHANNEL_PROXY_INSTALLED = True
