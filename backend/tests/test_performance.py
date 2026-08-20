from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.performance import ScalarMetric, TeleopPerformanceMonitor  # noqa: E402


class PerformanceMonitorTest(unittest.TestCase):
    def test_scalar_metric_tracks_current_ema_and_peak(self):
        metric = ScalarMetric(alpha=0.5)
        metric.update(2.0)
        metric.update(4.0)
        self.assertEqual(metric.current, 4.0)
        self.assertEqual(metric.ema, 3.0)
        self.assertEqual(metric.peak, 4.0)

    def test_monitor_tracks_loop_and_packet_rates(self):
        monitor = TeleopPerformanceMonitor(ema_alpha=0.5)
        monitor.observe_loop(1.0)
        monitor.observe_loop(1.01)
        monitor.observe_packets(2.0, 1, 0)
        monitor.observe_packets(2.02, 1, 2)
        snapshot = monitor.snapshot()
        self.assertAlmostEqual(snapshot["control_loop_hz"]["current"], 100.0)
        self.assertAlmostEqual(snapshot["packet_rate_hz"]["current"], 50.0)
        self.assertEqual(snapshot["accepted_packets"], 2)
        self.assertEqual(snapshot["rejected_packets"], 2)

    def test_monitor_tracks_errors_and_safety_ratios(self):
        monitor = TeleopPerformanceMonitor()
        monitor.observe_control(
            position_error_m=0.01,
            rotation_error_deg=2.0,
            reference_lag_m=0.02,
            workspace_limited=True,
            collision_limited=False,
        )
        monitor.observe_control(
            position_error_m=0.03,
            rotation_error_deg=4.0,
            reference_lag_m=0.01,
            workspace_limited=False,
            collision_limited=True,
        )
        snapshot = monitor.snapshot()
        self.assertEqual(snapshot["samples"], 2)
        self.assertEqual(snapshot["workspace_limit_ratio"], 0.5)
        self.assertEqual(snapshot["collision_limit_ratio"], 0.5)
        self.assertEqual(snapshot["position_error_m"]["peak"], 0.03)
        self.assertEqual(snapshot["rotation_error_deg"]["peak"], 4.0)


if __name__ == "__main__":
    unittest.main()
