#include "sysid_excitation_sequence.hpp"

#include <cassert>
#include <cmath>
#include <stdexcept>
#include <vector>

namespace {

using sysid_excitation::Segment;
using sysid_excitation::SegmentKind;

std::vector<Segment> ValidSegments(double move_duration) {
  std::vector<Segment> segments{
      {SegmentKind::kHold, -1, 0.0, 0.0, 0.0, 0.004}};
  for (int joint = 22; joint <= 28; ++joint) {
    const double amplitude = 0.01 * static_cast<double>(joint - 21);
    segments.push_back(
        {SegmentKind::kQuinticMove, joint, 0.0, amplitude, 0.0,
         move_duration});
    segments.push_back(
        {SegmentKind::kHold, joint, 0.0, 0.0, amplitude, 0.004});
    segments.push_back(
        {SegmentKind::kQuinticMove, joint, amplitude, 0.0, 0.0,
         move_duration});
    segments.push_back(
        {SegmentKind::kHold, joint, 0.0, 0.0, 0.0, 0.004});
  }
  return segments;
}

}  // namespace

int main() {
  std::array<double, sysid_excitation::kJointCount> start{};
  for (std::size_t i = 0; i < start.size(); ++i) {
    start[i] = static_cast<double>(i) * 0.01;
  }
  const double dt = 0.002;
  const double duration =
      sysid_excitation::GridDuration(0.1, 0.4, 1.2, dt);
  const sysid_excitation::Sequence sequence(start, ValidSegments(duration), dt);

  std::array<double, 7> maxima{};
  for (std::size_t local = 0; local < maxima.size(); ++local) {
    maxima[local] = start[22 + local];
  }
  for (std::uint64_t tick = 0; tick <= sequence.total_ticks(); ++tick) {
    const auto sample = sequence.AtTick(tick);
    for (std::size_t joint = 0; joint < start.size(); ++joint) {
      if (sample.active_joint < 22 ||
          joint != static_cast<std::size_t>(sample.active_joint)) {
        assert(sample.target_q_rad[joint] == start[joint]);
      }
    }
    if (sample.active_joint >= 22) {
      const auto local = static_cast<std::size_t>(sample.active_joint - 22);
      const double amplitude = 0.01 * static_cast<double>(local + 1);
      maxima[local] =
          std::max(maxima[local], sample.target_q_rad[sample.active_joint]);
      assert(sample.target_q_rad[sample.active_joint] >=
             start[sample.active_joint] - 1e-12);
      assert(sample.target_q_rad[sample.active_joint] <=
             start[sample.active_joint] + amplitude + 1e-12);
    }
  }
  for (std::size_t local = 0; local < maxima.size(); ++local) {
    const double amplitude = 0.01 * static_cast<double>(local + 1);
    assert(maxima[local] <= start[22 + local] + amplitude + 1e-12);
  }
  const auto final = sequence.AtTick(sequence.total_ticks());
  assert(final.complete);
  assert(final.target_q_rad == start);

  bool rejected = false;
  try {
    auto invalid = ValidSegments(duration);
    invalid[2].hold_offset_rad = 0.09;
    (void)sysid_excitation::Sequence(start, invalid, dt);
  } catch (const std::invalid_argument&) {
    rejected = true;
  }
  assert(rejected);

  rejected = false;
  try {
    auto invalid = ValidSegments(duration);
    invalid[1].joint_index = 21;
    (void)sysid_excitation::Sequence(start, invalid, dt);
  } catch (const std::invalid_argument&) {
    rejected = true;
  }
  assert(rejected);

  rejected = false;
  try {
    auto invalid = ValidSegments(duration);
    invalid.back().duration_s = 0.003;
    (void)sysid_excitation::Sequence(start, invalid, dt);
  } catch (const std::invalid_argument&) {
    rejected = true;
  }
  assert(rejected);
  return 0;
}
