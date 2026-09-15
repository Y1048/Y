#include "sysid_excitation_runtime.hpp"

#include <array>
#include <cassert>
#include <stdexcept>
#include <string>

namespace {

sysid_excitation::LoadedPlan Plan() {
  using sysid_excitation::SegmentKind;
  sysid_excitation::LoadedPlan plan;
  plan.request_sha256 = std::string(64, '1');
  plan.contract_id = "offline-runtime-fixture";
  plan.termination_owner_status = "unresolved";
  for (std::size_t joint = 0; joint < 29; ++joint) {
    plan.start_q_rad[joint] = 0.01 * static_cast<double>(joint);
    plan.kp_nm_rad[joint] = 40.0;
    plan.kd_nm_s_rad[joint] = 5.0;
  }
  plan.sample_period_s = 0.002;
  plan.training = {
      {SegmentKind::kHold, -1, 0.0, 0.0, 0.0, 0.004},
      {SegmentKind::kQuinticMove, 22, 0.0, 0.05, 0.0, 0.2},
      {SegmentKind::kHold, 22, 0.0, 0.0, 0.05, 0.004},
      {SegmentKind::kQuinticMove, 22, 0.05, 0.0, 0.0, 0.2},
      {SegmentKind::kHold, 22, 0.0, 0.0, 0.0, 0.004},
  };
  plan.validation = plan.training;
  return plan;
}

template <typename Function>
void MustReject(Function&& function) {
  bool rejected = false;
  try {
    function();
  } catch (const std::exception&) {
    rejected = true;
  }
  assert(rejected);
}

sysid_excitation::Runtime Runtime() {
  return sysid_excitation::Runtime(
      Plan(), sysid_excitation::EpisodeKind::kTraining, std::string(64, 'a'),
      0.002, 0.01, 1e-6);
}

}  // namespace

int main() {
  const auto plan = Plan();
  auto runtime = Runtime();
  MustReject([&]() { (void)runtime.Tick(); });
  runtime.Arm(plan.start_q_rad, plan.kp_nm_rad, plan.kd_nm_s_rad);
  const auto first = runtime.Tick();
  assert(first.state == sysid_excitation::RuntimeState::kRunning);
  assert(first.plan_file_sha256 == std::string(64, 'a'));
  assert(first.request_sha256 == std::string(64, '1'));
  assert(first.contract_id == "offline-runtime-fixture");
  assert(first.termination_owner_status == "unresolved");
  assert(first.episode == "training");

  const auto moving = runtime.Tick();
  runtime.LatchFault("generated fault");
  const auto held_a = runtime.Tick();
  const auto held_b = runtime.Tick();
  assert(held_a.state == sysid_excitation::RuntimeState::kFaultHold);
  assert(held_a.fault_reason == "generated fault");
  assert(held_a.tick == moving.tick && held_b.tick == moving.tick);
  assert(held_a.right_arm_target_q_rad == moving.right_arm_target_q_rad);
  assert(held_b.right_arm_target_q_rad == moving.right_arm_target_q_rad);
  assert(held_a.active_velocity_rad_s == 0.0);
  assert(held_a.active_acceleration_rad_s2 == 0.0);
  runtime.LatchFault("ignored later fault");
  assert(runtime.Tick().fault_reason == "generated fault");

  auto completed = Runtime();
  completed.Arm(plan.start_q_rad, plan.kp_nm_rad, plan.kd_nm_s_rad);
  sysid_excitation::RuntimeSample final;
  do {
    final = completed.Tick();
  } while (final.state != sysid_excitation::RuntimeState::kCompleteHold);
  const auto repeated = completed.Tick();
  assert(repeated.state == sysid_excitation::RuntimeState::kCompleteHold);
  assert(repeated.tick == final.tick);
  assert(repeated.right_arm_target_q_rad == final.right_arm_target_q_rad);
  for (std::size_t local = 0; local < 7; ++local) {
    assert(repeated.right_arm_target_q_rad[local] == plan.start_q_rad[22 + local]);
  }

  MustReject([&]() {
    (void)sysid_excitation::Runtime(
        Plan(), sysid_excitation::EpisodeKind::kTraining, "bad", 0.002,
        0.01, 1e-6);
  });
  auto before_first = Runtime();
  before_first.Arm(plan.start_q_rad, plan.kp_nm_rad, plan.kd_nm_s_rad);
  MustReject([&]() { before_first.LatchFault("too early"); });
  return 0;
}
