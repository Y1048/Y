from pathlib import Path
import unittest


SOURCE = Path(__file__).with_name("twist2_mink_cycle_trial.cpp")


class PersistentPdRuntimeTest(unittest.TestCase):
    def test_pd_mode_is_enabled_without_ai_or_damping(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("cycle candidate supports UDP only", text)
        self.assertIn('switcher_->SelectMode("ai")', text)
        self.assertNotIn("send_damping", text)

    def test_artifacts_are_sealed_before_nonreturning_hold(self):
        text = SOURCE.read_text(encoding="utf-8")
        marker = 'if(controller.handoff_requested())'
        block = text[text.rindex(marker):]
        self.assertLess(block.index("csv.Finish();"), block.index("controller.finish();"))
        self.assertIn('"owner_state","persistent_twist2_position_hold"', block)

    def test_sweep_uses_one_owner_and_three_fixed_candidates(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn('"--pd-sweep-trial"', text)
        self.assertIn("controller.set_proximal_pd(next_kp,5.F)", text)
        self.assertIn("pd_candidate==1?48.F:56.F", text)
        self.assertIn('controller.latch("pd sweep completed",true)', text)
        self.assertIn("controller.verified_regular_handoff();", text)
        self.assertIn("udp_target->Feedback(measured_q,measured_dq", text)
        self.assertIn("PdSmallSignalTrial", text)
        self.assertIn("joint 22 only, +8 deg -> -8 deg -> ready", text)

    def test_regular_handoff_stops_writer_before_select_and_verifies_state(self):
        text = SOURCE.read_text(encoding="utf-8")
        method = text[text.index("void verified_regular_handoff()"):
                      text.index("void print_stats()")]
        self.assertLess(method.index("writer_.reset()"),
                        method.index('switcher_->SelectMode("ai")'))
        self.assertIn("VerifiedRegularHandoffGate gate(start_fsm_id_)", method)
        self.assertIn("publisher_.reset()", method)
        self.assertIn("resume_position_hold_after_failed_regular_handoff", method)
        self.assertIn("LowCmd remains stopped to prevent owner overlap", method)
        self.assertIn("const WriterFrame command_frame = writer_frame()", method)
        settle = method[:method.index("writer_.reset()")]
        self.assertNotIn("last_target_[joint]", settle)

    def test_failed_handoff_restarts_only_after_empty_service_confirmation(self):
        text = SOURCE.read_text(encoding="utf-8")
        method = text[text.index("void verified_regular_handoff()"):
                      text.index("void print_stats()")]
        empty_check = 'last_mode_result == 0 && last_name.empty()'
        self.assertIn(empty_check, method)
        self.assertLess(method.index(empty_check),
                        method.index('resume_position_hold_after_failed_regular_handoff(\n          "SelectMode result="'))
        self.assertNotIn("throw std::runtime_error(\n        \"Regular handoff unverified", method)

    def test_handoff_only_has_no_udp_or_arm_trajectory(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn('"--handoff-only-trial"', text)
        self.assertIn('controller.latch("handoff-only completed",true)', text)
        self.assertIn('controller.reason()=="handoff-only completed"', text)
        self.assertIn("No arm trajectory and no UDP input", text)


if __name__ == "__main__":
    unittest.main()
