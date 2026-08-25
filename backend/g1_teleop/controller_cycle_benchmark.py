"""Low-overhead rolling timing benchmark for the complete teleop solver stack."""

from __future__ import annotations

import time
from collections import deque
from types import ModuleType
from typing import Any

import numpy as np


WINDOW_CYCLES = 600


def install_controller_cycle_benchmark(base: ModuleType) -> None:
    """Measure the outermost solve call and expose rolling latency statistics."""
    if getattr(base, "_CONTROLLER_CYCLE_BENCHMARK_INSTALLED", False):
        return

    original_solver = base.solve_right_arm_target
    durations_ms: deque[float] = deque(maxlen=WINDOW_CYCLES)
    swept_samples: deque[int] = deque(maxlen=WINDOW_CYCLES)

    base.RUNTIME_CYCLE_BENCHMARK_WINDOW = 0
    base.RUNTIME_CYCLE_LAST_MS = None
    base.RUNTIME_CYCLE_MEAN_MS = None
    base.RUNTIME_CYCLE_P50_MS = None
    base.RUNTIME_CYCLE_P95_MS = None
    base.RUNTIME_CYCLE_P99_MS = None
    base.RUNTIME_CYCLE_WORST_MS = None
    base.RUNTIME_CYCLE_EFFECTIVE_HZ = None
    base.RUNTIME_CYCLE_SWEPT_SAMPLES_MEAN = None
    base.RUNTIME_CYCLE_SWEPT_SAMPLES_P95 = None
    base.RUNTIME_CYCLE_SWEPT_SAMPLES_MAX = None

    def timed_solver(*args: Any, **kwargs: Any):
        started = time.perf_counter_ns()
        try:
            return original_solver(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0
            durations_ms.append(float(elapsed_ms))
            swept_samples.append(int(getattr(base, "RUNTIME_SWEPT_PATH_SAMPLES", 0)))

            values = np.asarray(durations_ms, dtype=float)
            sample_values = np.asarray(swept_samples, dtype=float)
            mean_ms = float(np.mean(values))

            base.RUNTIME_CYCLE_BENCHMARK_WINDOW = int(values.size)
            base.RUNTIME_CYCLE_LAST_MS = float(values[-1])
            base.RUNTIME_CYCLE_MEAN_MS = mean_ms
            base.RUNTIME_CYCLE_P50_MS = float(np.percentile(values, 50))
            base.RUNTIME_CYCLE_P95_MS = float(np.percentile(values, 95))
            base.RUNTIME_CYCLE_P99_MS = float(np.percentile(values, 99))
            base.RUNTIME_CYCLE_WORST_MS = float(np.max(values))
            base.RUNTIME_CYCLE_EFFECTIVE_HZ = (
                float(1000.0 / mean_ms) if mean_ms > 1e-12 else None
            )
            base.RUNTIME_CYCLE_SWEPT_SAMPLES_MEAN = float(np.mean(sample_values))
            base.RUNTIME_CYCLE_SWEPT_SAMPLES_P95 = float(
                np.percentile(sample_values, 95)
            )
            base.RUNTIME_CYCLE_SWEPT_SAMPLES_MAX = int(np.max(sample_values))

    base.solve_right_arm_target = timed_solver
    base._CONTROLLER_CYCLE_BENCHMARK_INSTALLED = True

    original_writer = getattr(base, "write_runtime_status", None)
    if callable(original_writer) and not getattr(
        base, "_CONTROLLER_CYCLE_BENCHMARK_STATUS_INSTALLED", False
    ):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["controller_cycle_benchmark_enabled"] = True
            enriched["controller_cycle_window"] = int(
                base.RUNTIME_CYCLE_BENCHMARK_WINDOW
            )
            enriched["controller_cycle_last_ms"] = base.RUNTIME_CYCLE_LAST_MS
            enriched["controller_cycle_mean_ms"] = base.RUNTIME_CYCLE_MEAN_MS
            enriched["controller_cycle_p50_ms"] = base.RUNTIME_CYCLE_P50_MS
            enriched["controller_cycle_p95_ms"] = base.RUNTIME_CYCLE_P95_MS
            enriched["controller_cycle_p99_ms"] = base.RUNTIME_CYCLE_P99_MS
            enriched["controller_cycle_worst_ms"] = base.RUNTIME_CYCLE_WORST_MS
            enriched["controller_cycle_effective_hz"] = base.RUNTIME_CYCLE_EFFECTIVE_HZ
            enriched["controller_cycle_swept_samples_mean"] = (
                base.RUNTIME_CYCLE_SWEPT_SAMPLES_MEAN
            )
            enriched["controller_cycle_swept_samples_p95"] = (
                base.RUNTIME_CYCLE_SWEPT_SAMPLES_P95
            )
            enriched["controller_cycle_swept_samples_max"] = (
                base.RUNTIME_CYCLE_SWEPT_SAMPLES_MAX
            )
            original_writer(enriched)

        base.write_runtime_status = status_writer
        base._CONTROLLER_CYCLE_BENCHMARK_STATUS_INSTALLED = True
