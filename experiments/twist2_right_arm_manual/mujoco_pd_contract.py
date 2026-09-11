"""SDK-free round-trip reference and the existing LowCmd position limiter.

No MuJoCo import here: the math can be checked against the C++ reference alone.
Simulation output must never be passed off as a physical PD measurement.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "references/lower_body/twist2_deploy/cpp_g1_twist2/twist2_common.hpp"
WRITER_DT = 0.002
REFERENCE_DT = 0.02
READY_DEGREES = [10, 22, 0, 55, 0, 0, 0, 10, -22, 0, 55, 0, 0, 0]
RATES = np.array([2.0] * 12 + [0.8] * 10 + [0.7] * 7)  # yesterday profile


@dataclass(frozen=True)
class Contract:
    baseline: np.ndarray
    kp: np.ndarray
    kd: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    torque: np.ndarray


def load_contract(path: Path = REFERENCE) -> Contract:
    """Read literal arrays, NOT execute/import SDK-dependent source code."""
    source = re.sub(r"//[^\n]*|/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)

    def array(name: str) -> np.ndarray:
        match = re.search(r"\b" + name + r"\s*=\s*\{([^}]+)\}", source)
        if not match:
            raise ValueError(f"C++ contract array missing: {name}")
        fields = [s.strip() for s in match[1].split(",") if s.strip()]
        if len(fields) != 29 or any(not re.fullmatch(r"[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?[fF]?", s) for s in fields):
            raise ValueError(f"Expected 29 numeric literals in {name}")
        value = np.array([float(s.rstrip("fF")) for s in fields])
        if not np.isfinite(value).all():
            raise ValueError(f"Non-finite {name}")
        return value

    baseline = array("kDefault")
    baseline[15:29] = np.deg2rad(READY_DEGREES)
    result = Contract(baseline, array("kKp"), array("kKd"),
                      array("kLower") + 0.05, array("kUpper") - 0.05, array("kTorqueLimit"))
    if not (np.all(result.kp > 0) and np.all(result.kd > 0) and np.all(result.torque > 0)
            and np.all(result.lower < baseline) and np.all(baseline < result.upper)):
        raise ValueError("Invalid C++ limits/gains/ready pose")
    if baseline[22] - RoundTrip.offset <= result.lower[22] or baseline[22] + RoundTrip.offset >= result.upper[22]:
        raise ValueError("Round trip crosses shoulder soft limits")
    return result


@dataclass(frozen=True)
class Point:
    offset: float = 0.0
    velocity: float = 0.0
    acceleration: float = 0.0
    phase: int = 1
    cycle: int = 0
    segment: str = "initial_hold"
    direction: int = 0


class RoundTrip:
    """Port of PdSmallSignalTrial; parity is tested against that actual header."""
    offset = math.radians(8)
    speed = math.radians(20)
    acceleration = math.radians(60)

    @staticmethod
    def duration(distance: float) -> float:
        return max(1.875 * distance / RoundTrip.speed,
                   math.sqrt((10 / math.sqrt(3)) * distance / RoundTrip.acceleration))

    def __init__(self) -> None:
        self.outbound = self.duration(self.offset)
        self.cross = self.duration(2 * self.offset)
        self.period = 2 * self.outbound + self.cross + 1.5
        self.total = 1 + 3 * self.period

    def at(self, elapsed: float) -> Point:
        if not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("Reference time must be finite and nonnegative")
        if elapsed < 1:
            return Point()
        if elapsed >= self.total:
            return Point(phase=6, cycle=3, segment="done")
        active = elapsed - 1
        cycle = int(active / self.period)
        t = active - cycle * self.period
        segments = ((self.outbound, 0., self.offset, 2, "out", 1),
                    (.5, self.offset, self.offset, 3, "positive_hold", 1),
                    (self.cross, self.offset, -self.offset, 4, "cross", -1),
                    (.5, -self.offset, -self.offset, 3, "negative_hold", -1),
                    (self.outbound, -self.offset, 0., 4, "return", 1),
                    (.5, 0., 0., 5, "ready_hold", 1))
        for duration, start, end, phase, segment, direction in segments:
            if t < duration:
                u = max(0., min(1., t / duration))
                delta = end - start
                return Point(start + delta * u**3 * (10 + u * (-15 + 6*u)),
                             delta / duration * 30*u*u*(1-u)**2,
                             delta / duration**2 * 60*u*(1-u)*(1-2*u),
                             phase, cycle, segment, direction)
            t -= duration
        return Point(phase=5, cycle=cycle, segment="ready_hold", direction=1)


def candidate_gains(contract: Contract, kp: float, kd: float) -> tuple[np.ndarray, np.ndarray]:
    if not (math.isfinite(kp) and 1 <= kp <= 100 and math.isfinite(kd) and .1 <= kd <= 20):
        raise ValueError("Candidate bounds: Kp 1..100, Kd 0.1..20; not hardware-approved gains")
    p, d = contract.kp.copy(), contract.kd.copy()
    p[22:26], d[22:26] = kp, kd
    return p, d


def writer_target(reference: np.ndarray, previous: np.ndarray, q: np.ndarray,
                  dq: np.ndarray, kp: np.ndarray, kd: np.ndarray,
                  contract: Contract) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Match normal write_cycle order; target dq=0, feedforward=0 in PD phase.

    The source's torque-based target clamp can override its prior slew clamp.
    Preserve and report that behavior, rather than silently changing the writer.
    """
    arrays = (reference, previous, q, dq, kp, kd)
    if any(a.shape != (29,) or not np.isfinite(a).all() for a in arrays) or np.any(kp <= 0):
        raise ValueError("Limiter requires finite 29-joint arrays and positive Kp")
    target = np.clip(reference, previous - RATES * WRITER_DT, previous + RATES * WRITER_DT)
    target = np.clip(target, contract.lower, contract.upper)
    before = target.copy()
    soft = .5 * contract.torque
    target = np.clip(target, q + (-soft + kd*dq)/kp, q + (soft + kd*dq)/kp)
    limited = np.abs(target - before) > 1e-7
    target = np.clip(target, contract.lower, contract.upper)
    slew_exceeded = np.abs(target - previous) > RATES * WRITER_DT + 1e-7
    return target, limited, slew_exceeded
