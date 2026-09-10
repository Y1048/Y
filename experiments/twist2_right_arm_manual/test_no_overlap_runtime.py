from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "experiments/twist2_right_arm_manual/twist2_mink_cycle_trial.cpp"
LAUNCHER = ROOT / "tools/START_TWIST2_MINK_CYCLE_CANDIDATE.ps1"


class NoOverlapRuntimeTest(unittest.TestCase):
    def test_live_controller_cannot_select_ai(self):
        source = CONTROLLER.read_text(encoding="utf-8")
        method = source[source.index("bool verified_regular_handoff()"):
                        source.index("void print_stats()")]
        self.assertLess(method.index("active_.store(false)"), method.index("writer_.reset()"))
        self.assertLess(method.index("write_cycle_mutex_"), method.index("writer_.reset()"))
        self.assertLess(method.index("writer_.reset()"), method.index('SelectMode("ai")'))
        self.assertEqual(source.count('SelectMode("ai")'), 1)
        self.assertIn("[Q SAFE HOLD]", source)

    def test_robot_launcher_is_blocked_before_ssh_command(self):
        source = LAUNCHER.read_text(encoding="utf-8")
        block = "if($Mode -eq 'All' -or $Mode -eq 'Robot'){throw $robotBlockedReason}"
        self.assertIn(block, source)
        self.assertLess(source.index(block), source.index('$command="cd /home/unitree/'))
        self.assertLess(source.index(block), source.index("Start-Process"))
        self.assertIn("$trialFlag=if($HandoffOnly){'--handoff-only-trial'}elseif($PdSweep){'--pd-sweep-trial'}else{'--udp-right-arm'}", source)


if __name__ == "__main__":
    unittest.main()
