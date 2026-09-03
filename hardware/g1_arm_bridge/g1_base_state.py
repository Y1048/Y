#!/usr/bin/env python3
"""G1 odometry를 실행 시작점 기준의 상대 base pose로 정규화한다.

이 모듈은 Unitree SDK나 네트워크를 import하지 않는다. DDS에서 읽은 값의
검증과 좌표 정규화만 담당하므로 Windows 오프라인 테스트에서도 사용할 수 있다.
Unitree IMU quaternion 입력 순서는 WXYZ이고 외부 패킷은 XYZW를 사용한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Sequence


BASE_STATE_TOPIC: Final[str] = "rt/odommodestate"
LOW_FREQUENCY_BASE_STATE_TOPIC: Final[str] = "rt/lf/odommodestate"
QUATERNION_EPSILON: Final[float] = 1e-8


class InvalidBaseStateError(ValueError):
    """입력 odometry가 유한한 3D pose 계약을 만족하지 않을 때 발생한다."""


@dataclass(frozen=True)
class NormalizedBaseState:
    """첫 유효 odometry frame을 원점으로 한 G1 상대 base state."""

    position_m: tuple[float, float, float]
    quaternion_xyzw: tuple[float, float, float, float]
    velocity_mps: tuple[float, float, float]
    yaw_speed_rad_s: float

    def ToPacket(self) -> dict[str, object]:
        return {
            "position_m": list(self.position_m),
            "quaternion_xyzw": list(self.quaternion_xyzw),
            "velocity_mps": list(self.velocity_mps),
            "yaw_speed_rad_s": self.yaw_speed_rad_s,
        }


def _FiniteVector(
    value: Sequence[float],
    expected_length: int,
    name: str,
) -> tuple[float, ...]:
    if len(value) != expected_length:
        raise InvalidBaseStateError(
            f"{name} must contain exactly {expected_length} values"
        )
    try:
        vector = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise InvalidBaseStateError(f"{name} contains a non-numeric value") from exc
    if not all(math.isfinite(item) for item in vector):
        raise InvalidBaseStateError(f"{name} contains a non-finite value")
    return vector


def NormalizeQuaternionWXYZ(
    quaternion_wxyz: Sequence[float],
) -> tuple[float, float, float, float]:
    quaternion = _FiniteVector(quaternion_wxyz, 4, "quaternion_wxyz")
    norm = math.sqrt(sum(value * value for value in quaternion))
    if norm <= QUATERNION_EPSILON:
        raise InvalidBaseStateError("quaternion_wxyz has zero length")
    normalized = tuple(value / norm for value in quaternion)
    return (
        normalized[0],
        normalized[1],
        normalized[2],
        normalized[3],
    )


def MultiplyQuaternionWXYZ(
    left: Sequence[float],
    right: Sequence[float],
) -> tuple[float, float, float, float]:
    left_w, left_x, left_y, left_z = _FiniteVector(left, 4, "left_quaternion")
    right_w, right_x, right_y, right_z = _FiniteVector(
        right, 4, "right_quaternion"
    )
    return (
        left_w * right_w
        - left_x * right_x
        - left_y * right_y
        - left_z * right_z,
        left_w * right_x
        + left_x * right_w
        + left_y * right_z
        - left_z * right_y,
        left_w * right_y
        - left_x * right_z
        + left_y * right_w
        + left_z * right_x,
        left_w * right_z
        + left_x * right_y
        - left_y * right_x
        + left_z * right_w,
    )


def ConjugateQuaternionWXYZ(
    quaternion: Sequence[float],
) -> tuple[float, float, float, float]:
    w_value, x_value, y_value, z_value = _FiniteVector(
        quaternion, 4, "quaternion"
    )
    return (w_value, -x_value, -y_value, -z_value)


def YawFromQuaternionWXYZ(quaternion: Sequence[float]) -> float:
    w_value, x_value, y_value, z_value = NormalizeQuaternionWXYZ(quaternion)
    return math.atan2(
        2.0 * (w_value * z_value + x_value * y_value),
        1.0 - 2.0 * (y_value * y_value + z_value * z_value),
    )


def _RotateHorizontal(
    vector: Sequence[float],
    yaw_rad: float,
) -> tuple[float, float, float]:
    x_value, y_value, z_value = _FiniteVector(vector, 3, "vector")
    cosine = math.cos(yaw_rad)
    sine = math.sin(yaw_rad)
    return (
        cosine * x_value - sine * y_value,
        sine * x_value + cosine * y_value,
        z_value,
    )


class BasePoseNormalizer:
    """첫 유효 sample을 원점/identity로 만들어 실행 간 절대 odom 차이를 제거한다."""

    def __init__(self) -> None:
        self._origin_position: tuple[float, float, float] | None = None
        self._origin_quaternion: tuple[float, float, float, float] | None = None
        self._origin_yaw_rad = 0.0

    @property
    def HasOrigin(self) -> bool:
        return self._origin_position is not None

    def Normalize(
        self,
        position_m: Sequence[float],
        quaternion_wxyz: Sequence[float],
        velocity_mps: Sequence[float],
        yaw_speed_rad_s: float,
    ) -> NormalizedBaseState:
        position = _FiniteVector(position_m, 3, "position_m")
        quaternion = NormalizeQuaternionWXYZ(quaternion_wxyz)
        velocity = _FiniteVector(velocity_mps, 3, "velocity_mps")
        yaw_speed = float(yaw_speed_rad_s)
        if not math.isfinite(yaw_speed):
            raise InvalidBaseStateError("yaw_speed_rad_s is non-finite")

        if self._origin_position is None:
            self._origin_position = (position[0], position[1], position[2])
            self._origin_quaternion = quaternion
            self._origin_yaw_rad = YawFromQuaternionWXYZ(quaternion)

        assert self._origin_position is not None
        assert self._origin_quaternion is not None
        position_delta = (
            position[0] - self._origin_position[0],
            position[1] - self._origin_position[1],
            position[2] - self._origin_position[2],
        )
        relative_position = _RotateHorizontal(
            position_delta,
            -self._origin_yaw_rad,
        )
        relative_velocity = _RotateHorizontal(
            velocity,
            -self._origin_yaw_rad,
        )
        relative_quaternion = NormalizeQuaternionWXYZ(
            MultiplyQuaternionWXYZ(
                ConjugateQuaternionWXYZ(self._origin_quaternion),
                quaternion,
            )
        )
        # q와 -q는 같은 회전이다. 부호를 고정해 보간 시 불연속 점프를 막는다.
        if relative_quaternion[0] < 0.0:
            relative_quaternion = tuple(
                -value for value in relative_quaternion
            )

        return NormalizedBaseState(
            position_m=(
                relative_position[0],
                relative_position[1],
                relative_position[2],
            ),
            quaternion_xyzw=(
                relative_quaternion[1],
                relative_quaternion[2],
                relative_quaternion[3],
                relative_quaternion[0],
            ),
            velocity_mps=(
                relative_velocity[0],
                relative_velocity[1],
                relative_velocity[2],
            ),
            yaw_speed_rad_s=yaw_speed,
        )
