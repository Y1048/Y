#include "sysid_excitation_reference.hpp"

#include <cassert>
#include <cmath>
#include <limits>

int main() {
  constexpr double kPi = 3.14159265358979323846;
  const double amplitude = 8.0 * kPi / 180.0;
  const double velocity_limit = 20.0 * kPi / 180.0;
  const double acceleration_limit = 60.0 * kPi / 180.0;
  const double dt = 0.002;
  const double duration = sysid_excitation::GridDuration(
      amplitude, velocity_limit, acceleration_limit, dt);
  assert(std::abs(duration / dt - std::round(duration / dt)) < 1e-12);

  double peak_velocity = 0.0;
  double peak_acceleration = 0.0;
  double previous = 0.0;
  for (double elapsed = 0.0; elapsed <= duration + dt * 0.5;
       elapsed += dt) {
    const auto point =
        sysid_excitation::Quintic(0.0, amplitude, elapsed, duration);
    assert(point.position_rad >= -1e-12);
    assert(point.position_rad <= amplitude + 1e-12);
    assert(point.position_rad + 1e-12 >= previous);
    previous = point.position_rad;
    peak_velocity = std::max(peak_velocity, std::abs(point.velocity_rad_s));
    peak_acceleration =
        std::max(peak_acceleration, std::abs(point.acceleration_rad_s2));
  }
  assert(std::abs(previous - amplitude) < 1e-12);
  assert(peak_velocity <= velocity_limit + 1e-12);
  assert(peak_acceleration <= acceleration_limit + 1e-12);

  const auto before = sysid_excitation::Quintic(1.0, 2.0, -1.0, 1.0);
  const auto after = sysid_excitation::Quintic(1.0, 2.0, 2.0, 1.0);
  assert(before.position_rad == 1.0 && before.velocity_rad_s == 0.0 &&
         before.acceleration_rad_s2 == 0.0);
  assert(after.position_rad == 2.0 && after.velocity_rad_s == 0.0 &&
         after.acceleration_rad_s2 == 0.0);

  bool rejected = false;
  try {
    (void)sysid_excitation::GridDuration(
        amplitude, 0.0, acceleration_limit, dt);
  } catch (const std::invalid_argument&) {
    rejected = true;
  }
  assert(rejected);
  rejected = false;
  try {
    (void)sysid_excitation::Quintic(
        0.0, 1.0, std::numeric_limits<double>::quiet_NaN(), 1.0);
  } catch (const std::invalid_argument&) {
    rejected = true;
  }
  assert(rejected);
  return 0;
}
