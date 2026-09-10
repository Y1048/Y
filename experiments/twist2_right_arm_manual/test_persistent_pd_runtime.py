from pathlib import Path
import unittest

SOURCE = Path(__file__).with_name("twist2_mink_cycle_trial.cpp")
SAFETY = Path(__file__).with_name("regular_handoff_safety.hpp")


class PersistentPdRuntimeTest(unittest.TestCase):
    def test_pd_mode_is_enabled_without_damping(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn('switcher_->SelectMode("ai")', text)
        self.assertNotIn("send_damping", text)

    def test_artifact_failures_do_not_unwind_owner(self):
        text = SOURCE.read_text(encoding="utf-8")
        block = text[text.rindex('if(controller.handoff_requested())'):]
        self.assertLess(block.index("regular_handoff::TryArtifact"), block.index("csv.Finish();"))
        self.assertLess(block.index("csv.Finish();"), block.index("controller.finish();"))
        self.assertIn('"record_kind","pre_handoff_checkpoint"', block)
        self.assertIn('"owner_state","persistent_twist2_position_hold"', block)
        self.assertIn('csv_directory / "handoff.json"', block)
        self.assertIn("if (verified) return artifacts_sealed && outcome_recorded ? 0 : 1", block)

    def test_sweep_uses_one_owner_and_three_fixed_candidates(self):
        text = SOURCE.read_text(encoding="utf-8")
        for expected in ('"--pd-sweep-trial"', "controller.set_proximal_pd(next_kp,5.F)",
                         "pd_candidate==1?48.F:56.F", 'controller.latch("pd sweep completed",true)',
                         "controller.verified_regular_handoff();", "PdSmallSignalTrial",
                         "udp_target->Feedback(measured_q,measured_dq",
                         "joint 22 only, +8 deg -> -8 deg -> ready"):
            self.assertIn(expected, text)

    def test_handoff_uses_fresh_writer_snapshot_and_settle_window(self):
        text = SOURCE.read_text(encoding="utf-8")
        method = text[text.index("bool verified_regular_handoff()"):
                      text.index("void print_stats()")]
        settle = method[:method.index("active_.store(false)")]
        self.assertIn("const WriterFrame command_frame = writer_frame()", settle)
        self.assertNotIn("last_target_[joint]", settle)
        self.assertIn("ContinuousObservationWindow window(1.0, 0.05)", settle)
        self.assertIn("command_frame.write_returned_s", settle)
        self.assertIn("catch (...) { settled = false; }", settle)
        self.assertIn("return false", settle)

    def test_fallback_requires_new_empty_query_after_inactive_prepare(self):
        helper = SAFETY.read_text(encoding="utf-8")
        start = helper.index("bool ResumeOnFreshEmpty")
        method = helper[start:helper.index("// Artifact failures", start)]
        self.assertLess(method.index("PrepareInactiveWriter()"), method.index("CheckMode(name)"))
        self.assertLess(method.index("CheckMode(name)"), method.index("result == 0 && name.empty()"))
        self.assertIn("FreshInterval(started, backend.Now())", method)
        self.assertIn("backend.EnablePreparedWriter(started)", method)
        self.assertNotIn("GetFsmId", method)
        text = SOURCE.read_text(encoding="utf-8")
        enable = text[text.index("bool EnablePreparedWriter("):text.index("int regular_fsm_id()")]
        self.assertIn("FreshInterval(observation_started, now)", enable)
        self.assertLess(enable.index("FreshInterval"), enable.index("active_.store(true)"))
        self.assertNotIn("CheckMode", enable.split("// No RPC")[0])

    def test_handoff_only_has_no_udp_or_arm_trajectory_but_keeps_leg_blend(self):
        text = SOURCE.read_text(encoding="utf-8")
        for expected in ('"--handoff-only-trial"', 'controller.latch("handoff-only completed",true)',
                         "No arm trajectory and no UDP input", "NOT a whole-body no-motion test",
                         "const bool controlled_trial=pd_trial||handoff_only;",
                         "if(!pd_active)enable_udp();", "if(handoff_only&&alpha>=1.0F)",
                         "alpha * full_policy_target[i]"):
            self.assertIn(expected, text)
        self.assertNotIn("Hold all 29 captured targets through capture/blend", text)

    def test_owner_guard_covers_activation_and_post_loop_handoff(self):
        text = SOURCE.read_text(encoding="utf-8")
        guard = text.index("return regular_handoff::RunOwnerProtected(controller")
        self.assertLess(guard, text.index("controller.handoff_and_activate();"))
        self.assertLess(guard, text.index("controller.verified_regular_handoff();"))
        helper = SAFETY.read_text(encoding="utf-8")
        self.assertIn("catch (...) {}", helper)
        self.assertIn("owner.ProtectOwnerLifetime();", helper)
        protect = text[text.index("void ProtectOwnerLifetime()"):text.index("bool verified_regular_handoff()")]
        self.assertIn("OwnerPhase::Holding) finish()", protect)
        self.assertIn("monitor_regular_handoff()", protect)
        self.assertNotIn("EnablePreparedWriter", protect)


if __name__ == "__main__":
    unittest.main()
