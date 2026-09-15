#include "sysid_excitation_writer_hook.hpp"

#include <array>
#include <cassert>
#include <cmath>
#include <stdexcept>
#include <vector>

namespace {

sysid_excitation::LoadedPlan Plan() {
  using sysid_excitation::Segment;
  using sysid_excitation::SegmentKind;
  sysid_excitation::LoadedPlan plan;
  for (std::size_t joint = 0; joint < plan.start_q_rad.size(); ++joint) {
    plan.start_q_rad[joint] = 0.01 * static_cast<double>(joint);
    plan.kp_nm_rad[joint] = 40.0;
    plan.kd_nm_s_rad[joint] = 5.0;
  }
  plan.sample_period_s = 0.002;
  plan.training.push_back(
      {SegmentKind::kHold, -1, 0.0, 0.0, 0.0, 0.004});
  for (int joint = 22; joint <= 28; ++joint) {
    const double amplitude = 0.01 * static_cast<double>(joint - 21);
    plan.training.push_back(
        {SegmentKind::kQuinticMove, joint, 0.0, amplitude, 0.0, 0.2});
    plan.training.push_back(
        {SegmentKind::kHold, joint, 0.0, 0.0, amplitude, 0.004});
    plan.training.push_back(
        {SegmentKind::kQuinticMove, joint, amplitude, 0.0, 0.0, 0.2});
    plan.training.push_back(
        {SegmentKind::kHold, joint, 0.0, 0.0, 0.0, 0.004});
  }
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

}  // namespace

int main() {
  auto plan = Plan();
  const auto expected_start = plan.start_q_rad;
  const auto gains_kp = plan.kp_nm_rad;
  const auto gains_kd = plan.kd_nm_s_rad;
  sysid_excitation::WriterHook hook(
      plan, sysid_excitation::EpisodeKind::kTraining, 0.002, 0.01, 1e-6);
  MustReject([&]() { (void)hook.Next(); });
  hook.Arm(expected_start, gains_kp, gains_kd);
  assert(hook.armed());

  std::array<double, 7> maxima{};
  for (std::size_t local = 0; local < maxima.size(); ++local) {
    maxima[local] = expected_start[22 + local];
  }
  for (std::uint64_t tick = 0; tick <= hook.total_ticks(); ++tick) {
    const auto sample = hook.Next();
    assert(sample.tick == tick);
    for (std::size_t local = 0; local < maxima.size(); ++local) {
      maxima[local] = std::max(maxima[local], sample.right_arm_target_q_rad[local]);
      const double amplitude = 0.01 * static_cast<double>(local + 1);
      assert(sample.right_arm_target_q_rad[local] >=
             expected_start[22 + local] - 1e-12);
      assert(sample.right_arm_target_q_rad[local] <=
             expected_start[22 + local] + amplitude + 1e-12);
    }
    if (tick == hook.total_ticks()) {
      assert(sample.complete);
      for (std::size_t local = 0; local < 7; ++local) {
        assert(sample.right_arm_target_q_rad[local] ==
               expected_start[22 + local]);
      }
    }
  }
  const auto held = hook.Next();
  assert(held.complete && held.tick == hook.total_ticks());

  MustReject([&]() {
    (void)sysid_excitation::WriterHook(
        Plan(), sysid_excitation::EpisodeKind::kTraining, 0.02, 0.01, 1e-6);
  });
  MustReject([&]() {
    auto bad_q = expected_start;
    bad_q[22] += 0.02;
    sysid_excitation::WriterHook bad(
        Plan(), sysid_excitation::EpisodeKind::kTraining, 0.002, 0.01, 1e-6);
    bad.Arm(bad_q, gains_kp, gains_kd);
  });
  MustReject([&]() {
    auto bad_kp = gains_kp;
    bad_kp[25] += 0.1;
    sysid_excitation::WriterHook bad(
        Plan(), sysid_excitation::EpisodeKind::kTraining, 0.002, 0.01, 1e-6);
    bad.Arm(expected_start, bad_kp, gains_kd);
  });
  return 0;
}
