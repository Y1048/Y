"""Mocked launcher tests: no WSL, DDS, network or physical output."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import gate6_weight_hold_trial as trial


class WeightHoldTrialTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((trial.PROJECT_ROOT / "config/g1_gate6_hold.json").read_text())

    def test_profiles_only_change_weight_and_remain_locked(self):
        for weight in (0.6, 0.8, 1.0):
            config = trial.BuildTrialConfig(self.source, weight)
            self.assertFalse(config["hardware_output_authorized"])
            self.assertEqual({**config, "maximum_weight": self.source["maximum_weight"]}, self.source)
        for weight in (0.0, 0.5, 1.1):
            with self.assertRaises(ValueError):
                trial.BuildTrialConfig(self.source, weight)

    def test_cancel_does_not_launch_processes(self):
        with patch.object(trial.subprocess, "Popen") as start, patch.object(trial.subprocess, "check_output") as check:
            self.assertEqual(trial.RunTrial(0.6, "N"), 0)
            start.assert_not_called()
            check.assert_not_called()

    def test_changed_gains_or_unlocked_base_block(self):
        for change in ({"proximal_kp": 999}, {"hardware_output_authorized": True}):
            with self.assertRaises(ValueError):
                trial.BuildTrialConfig({**self.source, **change}, 0.6)

    def RunMocked(self, weight, failure=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "config").mkdir()
            (root / "config/g1_gate6_hold.json").write_text(json.dumps(self.source))
            calls = []

            def Run(args, log_path):
                calls.append(args)
                config_path = log_path.parent / "config.json"
                config = json.loads(config_path.read_text())
                physical = "--enable-hardware-output" in args
                self.assertEqual(config["hardware_output_authorized"], physical)
                if failure == log_path.name:
                    raise RuntimeError("simulated failure")
                if physical:
                    (log_path.parent / "status.json").write_text(json.dumps({
                        "command_output_enabled": False, "fault": {"active": False},
                        "details": {"zero_release_completed": True, "release_zero_frames_sent": 25}}))

            forwarder = Mock()
            forwarder.poll.return_value = 124
            with patch.object(trial, "PROJECT_ROOT", root), patch.object(trial, "RunChecked", side_effect=Run), \
                 patch.object(trial.subprocess, "check_output", return_value=""), \
                 patch.object(trial.subprocess, "Popen", return_value=forwarder), \
                 patch.object(trial.time, "sleep"):
                if failure:
                    with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                        trial.RunTrial(weight, "Y")
                else:
                    self.assertEqual(trial.RunTrial(weight, "Y"), 0)
            configs = list((root / "logs/physical_tests").glob("*/config.json"))
            self.assertEqual(len(configs), 1)
            saved = json.loads(configs[0].read_text())
            self.assertFalse(saved["hardware_output_authorized"])
            self.assertEqual(saved["maximum_weight"], weight)
            self.assertEqual(json.loads((root / "config/g1_gate6_hold.json").read_text()), self.source)
            return calls

    def test_one_step_only_and_relocks_all_weights(self):
        for weight in (0.6, 0.8, 1.0):
            calls = self.RunMocked(weight)
            self.assertEqual(sum("--enable-hardware-output" in args for args in calls), 1)

    def test_precheck_failure_does_not_start_physical_output(self):
        calls = self.RunMocked(0.6, "precheck.log")
        self.assertFalse(any("--enable-hardware-output" in args for args in calls))

    def test_physical_child_error_still_relocks(self):
        self.RunMocked(0.6, "hold.log")


if __name__ == "__main__":
    unittest.main()
