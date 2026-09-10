#include "pd_small_signal_trial.hpp"

#include <cassert>
#include <cmath>
#include <limits>
#include <stdexcept>

int main() {
  std::array<double, 29> baseline{};
  for (std::size_t i = 0; i < baseline.size(); ++i) baseline[i] = 0.01 * i;
  PdSmallSignalTrial trial(baseline);

  double min_offset = 0.0;
  double max_offset = 0.0;
  double max_speed = 0.0;
  double max_acceleration = 0.0;
  int max_cycle = 0;
  constexpr double dt = 0.0005;
  for (double t = 0.0; t < trial.Total(); t += dt) {
    const auto point = trial.At(t);
    for (std::size_t joint = 0; joint < baseline.size(); ++joint) {
      if (joint != 22) assert(point.q[joint] == baseline[joint]);
    }
    const double offset = point.q[22] - baseline[22];
    min_offset = std::min(min_offset, offset);
    max_offset = std::max(max_offset, offset);
    max_speed = std::max(max_speed, std::abs(point.dq));
    max_acceleration = std::max(max_acceleration, std::abs(point.ddq));
    max_cycle = std::max(max_cycle, point.cycle);
  }
  const auto done = trial.At(trial.Total());
  assert(done.phase == 6 && done.cycle == 3);
  assert(done.q == baseline);
  assert(max_cycle == 2);
  assert(std::abs(max_offset - PdSmallSignalTrial::positive_offset) < 1e-8);
  assert(std::abs(min_offset - PdSmallSignalTrial::negative_offset) < 1e-8);
  assert(max_speed <= PdSmallSignalTrial::speed_limit + 1e-12);
  assert(max_acceleration <= PdSmallSignalTrial::acceleration_limit + 1e-12);

  bool reversed = false;
  try {
    trial.At(trial.Total() - 0.1);
  } catch (const std::runtime_error&) {
    reversed = true;
  }
  assert(reversed);

  baseline[4] = std::numeric_limits<double>::quiet_NaN();
  bool invalid = false;
  try {
    PdSmallSignalTrial bad(baseline);
  } catch (const std::runtime_error&) {
    invalid = true;
  }
  assert(invalid);
}
