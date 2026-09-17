"""Synthetic guard faults and fake-clock release; no robot dependencies."""

import math
import unittest

from arm_sdk_release_contract import execute_release_sequence
from waist_guard_offline import WaistGuardStudy, AnalyzeCapture
from waist_hold_offline import BuildStudyFrame


class WaistGuardTests(unittest.TestCase):
    def MakeGuard(self):
        return WaistGuardStudy((0, 0, 0), angle_deg=2, velocity_deg_s=10, timeout_s=0.25)

    def MakeImuGuard(self, baseline=(0, 0, 0)):
        # Synthetic thresholds only; no physical profile consumes these values.
        return WaistGuardStudy((0, 0, 0), angle_deg=2, velocity_deg_s=10,
                               timeout_s=0.25, initial_imu_rpy=baseline, tilt_deg=2)

    def test_imu_detects_body_tilt_without_waist_joint_motion(self):
        for axis in (0, 1):
            for direction in (-1, 1):
                with self.subTest(axis=axis, direction=direction):
                    guard = self.MakeImuGuard()
                    imu = [0, 0, 0]
                    imu[axis] = direction * math.radians(2)
                    self.assertIsNone(guard.Evaluate((0, 0, 0), (0, 0, 0), 0, imu_rpy=imu))
                    imu[axis] = direction * math.radians(2.01)
                    self.assertEqual(guard.Evaluate((0, 0, 0), (0, 0, 0), 0, imu_rpy=imu), "imu_tilt")
                    self.assertEqual(guard.Evaluate((0, 0, 0), (0, 0, 0), 0, imu_rpy=(0, 0, 0)), "imu_tilt")
                    self.assertEqual(guard.initial_imu_rpy, (0, 0, 0))

    def test_imu_yaw_wrap_and_missing_samples(self):
        guard = self.MakeImuGuard()
        self.assertIsNone(guard.Evaluate((0, 0, 0), (0, 0, 0), 0, imu_rpy=(0, 0, math.pi)))
        guard = self.MakeImuGuard((math.radians(179.5), 0, 0))
        self.assertIsNone(guard.Evaluate((0, 0, 0), (0, 0, 0), 0,
                                        imu_rpy=(math.radians(-179.5), 0, 0)))
        for imu in (None, (), (0, 0), (math.nan, 0, 0), (0, math.inf, 0), (0, 0, math.nan)):
            with self.subTest(imu=imu):
                guard = self.MakeImuGuard()
                self.assertEqual(guard.Evaluate((0, 0, 0), (0, 0, 0), 0, imu_rpy=imu), "invalid_state")
        guard = self.MakeImuGuard()
        self.assertEqual(guard.Evaluate((0, 0, 0), (0, 0, 0), 0.3, imu_rpy=(0, 0, 0)), "stale_state")

    def test_imu_requires_explicit_configuration(self):
        for options in ({"initial_imu_rpy": (0, 0, 0)}, {"tilt_deg": 2},
                        {"initial_imu_rpy": (0, 0), "tilt_deg": 2},
                        {"initial_imu_rpy": (0, 0, 0), "tilt_deg": 0},
                        {"initial_imu_rpy": (0, 0, 0), "tilt_deg": math.nan}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                WaistGuardStudy((0, 0, 0), angle_deg=2, velocity_deg_s=10,
                                timeout_s=0.25, **options)

    def test_imu_fault_routes_to_fake_release_without_reengage(self):
        guard = self.MakeImuGuard()
        clock, frames = [0.0], []
        def Build(weight):
            return BuildStudyFrame([0.0]*29, [0.0]*14, guard.initial_waist,
                                   weight=weight, kp=60, kd=1.5, mode=1)
        def Sleep(seconds):
            clock[0] += seconds
        self.assertIsNone(guard.Evaluate((0, 0, 0), (0, 0, 0), 0, imu_rpy=(0, 0, 0)))
        frames.append(Build(0.2))
        reason = guard.Evaluate((0, 0, 0), (0, 0, 0), 0, imu_rpy=(0, 0.1, 0))
        self.assertEqual(reason, "imu_tilt")
        result = execute_release_sequence(start_weight=frames[-1]["fields"]["weight"],
            ramp_s=3, zero_cycles=25, publish_hz=250, build_ramp_frame=Build,
            build_zero_frame=lambda: Build(0), publish_frame=frames.append,
            monotonic=lambda: clock[0], sleep=Sleep, unix_time_ns=lambda: int(clock[0]*1e9))
        self.assertTrue(result.zero_release_completed)
        self.assertEqual(result.release_zero_frames_sent, 25)
        self.assertFalse(result.external_authority_handoff_confirmed)
        weights = [frame["fields"]["weight"] for frame in frames]
        self.assertTrue(all(a >= b for a, b in zip(weights, weights[1:])))
        for frame in frames:
            self.assertEqual(frame["fields"]["motor_q_rad"][12:15], [0, 0, 0])
            self.assertFalse(frame["hardware_authorized"])
        self.assertEqual(guard.Evaluate((0, 0, 0), (0, 0, 0), 0, imu_rpy=(0, 0, 0)), "imu_tilt")

    def test_healthy_and_exact_boundaries(self):
        guard = self.MakeGuard()
        self.assertIsNone(guard.Evaluate((0, math.radians(2), 0), (math.radians(10), 0, 0), 0.25))

    def test_angle_velocity_stale_and_invalid_latch(self):
        cases = [((0, 0.1, 0), (0, 0, 0), 0, "waist_angle"),
                 ((0, 0, 0), (0, 1, 0), 0, "waist_velocity"),
                 ((0, 0, 0), (0, 0, 0), 0.251, "stale_state"),
                 ((math.nan, 0, 0), (0, 0, 0), 0, "invalid_state"),
                 ((0, 0, 0), (0, 0, 0), -1, "invalid_state"),
                 (None, None, 0, "invalid_state")]
        for q, dq, age, expected in cases:
            guard = self.MakeGuard()
            self.assertEqual(guard.Evaluate(q, dq, age), expected)
            self.assertEqual(guard.Evaluate((0, 0, 0), (0, 0, 0), 0), expected)
            self.assertEqual(guard.initial_waist, (0, 0, 0))

    def test_bad_config_and_missing_baseline(self):
        with self.assertRaises(ValueError):
            WaistGuardStudy((0, 0, 0), angle_deg=math.nan, velocity_deg_s=10, timeout_s=0.25)
        with self.assertRaisesRegex(ValueError, "READY"):
            AnalyzeCapture([], angle_deg=2, velocity_deg_s=10, timeout_s=0.25)
        with self.assertRaisesRegex(ValueError, "no command samples"):
            AnalyzeCapture([{"details": {"schedule_phase": "READY", "measured_all_q_rad": [0]*29}}],
                           angle_deg=2, velocity_deg_s=10, timeout_s=0.25)

    def test_partial_release_failure_evidence(self):
        # A successful zero write is not proof that the entire release tail completed.
        for failure in ("ramp_middle", "zero_first", "zero_middle", "zero_last"):
            with self.subTest(failure=failure):
                clock = [0.0]
                attempts = []
                successful = []
                tail_count = [0]
                guard = self.MakeGuard()
                self.assertEqual(guard.Evaluate((0, 0, 0), (0, 0, 0), 0.3), "stale_state")

                def Build(weight, phase):
                    frame = BuildStudyFrame([0.0]*29, [0.0]*14, guard.initial_waist,
                                            weight=weight, kp=60, kd=1.5, mode=1)
                    return phase, frame

                def FakeWrite(item):
                    phase, frame = item
                    attempts.append(item)
                    if phase == "tail":
                        tail_count[0] += 1
                    failure_index = {"zero_first": 1, "zero_middle": 13, "zero_last": 25}
                    if ((failure == "ramp_middle" and phase == "ramp"
                         and frame["fields"]["weight"] <= 0.5)
                        or (phase == "tail" and tail_count[0] == failure_index.get(failure))):
                        raise OSError("offline partial release failure")
                    successful.append((item, int(clock[0]*1e9)))

                def Sleep(seconds):
                    clock[0] += seconds

                result = execute_release_sequence(start_weight=1, ramp_s=3, zero_cycles=25,
                    publish_hz=250, build_ramp_frame=lambda weight: Build(weight, "ramp"),
                    build_zero_frame=lambda: Build(0, "tail"), publish_frame=FakeWrite,
                    monotonic=lambda: clock[0], sleep=Sleep,
                    unix_time_ns=lambda: int(clock[0]*1e9))
                expected_zeros = {"ramp_middle": 25, "zero_first": 0,
                                  "zero_middle": 12, "zero_last": 24}[failure]
                self.assertEqual(result.release_zero_frames_sent, expected_zeros)
                self.assertEqual(result.zero_release_completed, failure == "ramp_middle")
                self.assertEqual(result.release_ramp_completed, failure != "ramp_middle")
                self.assertEqual(result.output_state_unknown, failure != "ramp_middle")
                self.assertFalse(result.external_authority_handoff_confirmed)
                self.assertIn("ramp:" if failure == "ramp_middle" else "zero_tail:", result.release_fault)
                self.assertEqual(result.last_successful_write_unix_ns, successful[-1][1])
                self.assertEqual(result.last_successful_weight, successful[-1][0][1]["fields"]["weight"])
                weights = [frame["fields"]["weight"] for _, frame in attempts]
                self.assertTrue(all(a >= b for a, b in zip(weights, weights[1:])))
                for _, frame in attempts:
                    self.assertEqual(frame["fields"]["motor_q_rad"][12:15], [0, 0, 0])
                    self.assertFalse(frame["hardware_authorized"])
                self.assertEqual(guard.Evaluate((0, 0, 0), (0, 0, 0), 0), "stale_state")

    def test_latched_fault_release_and_transport_failure(self):
        for failure in (None, "first", "all"):
            clock = [0.0]
            frames = []
            guard = self.MakeGuard()
            self.assertEqual(guard.Evaluate((0, 0.1, 0), (0, 0, 0), 0), "waist_angle")

            def Build(weight):
                return BuildStudyFrame([0.0]*29, [0.0]*14, guard.initial_waist,
                                      weight=weight, kp=60, kd=1.5, mode=1)

            def FakeWrite(frame):
                frames.append(frame)
                if failure == "all" or (failure == "first" and len(frames) == 1):
                    raise OSError("offline injected transport failure")

            def Sleep(seconds):
                clock[0] += seconds

            result = execute_release_sequence(start_weight=1, ramp_s=3, zero_cycles=25,
                publish_hz=250, build_ramp_frame=Build, build_zero_frame=lambda: Build(0),
                publish_frame=FakeWrite, monotonic=lambda: clock[0], sleep=Sleep,
                unix_time_ns=lambda: int(clock[0]*1e9))
            self.assertFalse(result.external_authority_handoff_confirmed)
            self.assertEqual(result.zero_release_completed, failure != "all")
            self.assertEqual(result.output_state_unknown, failure == "all")
            if failure is not None:
                self.assertIsNotNone(result.release_fault)
            for frame in frames:
                self.assertEqual(frame["fields"]["motor_q_rad"][12:15], [0, 0, 0])
                self.assertFalse(frame["hardware_authorized"])
            weights = [frame["fields"]["weight"] for frame in frames]
            self.assertTrue(all(a >= b for a, b in zip(weights, weights[1:])))
            self.assertEqual(guard.Evaluate((0, 0, 0), (0, 0, 0), 0), "waist_angle")


if __name__ == "__main__":
    unittest.main()
