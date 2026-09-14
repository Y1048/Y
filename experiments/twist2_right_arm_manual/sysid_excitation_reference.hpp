#pragma once

// Pure trajectory math for offline parity tests. No SDK, DDS, publisher,
// controller, clock, concurrency, file or network dependency.
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace sysid_excitation {

struct Point {
  double position_rad{};
  double velocity_rad_s{};
  double acceleration_rad_s2{};
};

inline double GridDuration(double delta_rad, double velocity_limit_rad_s,
                           double acceleration_limit_rad_s2,
                           double sample_period_s) {
  if (!std::isfinite(delta_rad) ||
      !std::isfinite(velocity_limit_rad_s) || velocity_limit_rad_s <= 0.0 ||
      !std::isfinite(acceleration_limit_rad_s2) ||
          acceleration_limit_rad_s2 <= 0.0 ||
      !std::isfinite(sample_period_s) || sample_period_s <= 0.0) {
    throw std::invalid_argument("invalid excitation duration input");
  }
  constexpr double kPeakSpeedFactor = 1.875;
  constexpr double kPeakAccelerationFactor =
      10.0 / 1.7320508075688772935274463415059;
  const double distance = std::abs(delta_rad);
  const double raw = std::max(
      {kPeakSpeedFactor * distance / velocity_limit_rad_s,
       std::sqrt(kPeakAccelerationFactor * distance /
                 acceleration_limit_rad_s2),
       2.0 * sample_period_s});
  return std::ceil(raw / sample_period_s) * sample_period_s;
}

inline Point Quintic(double start_rad, double end_rad, double elapsed_s,
                     double duration_s) {
  if (!std::isfinite(start_rad) || !std::isfinite(end_rad) ||
      !std::isfinite(elapsed_s) || !std::isfinite(duration_s) ||
      duration_s <= 0.0) {
    throw std::invalid_argument("invalid excitation segment input");
  }
  const double u = std::clamp(elapsed_s / duration_s, 0.0, 1.0);
  const double delta = end_rad - start_rad;
  const double smooth = u * u * u * (10.0 + u * (-15.0 + 6.0 * u));
  const double speed = 30.0 * u * u * (1.0 - u) * (1.0 - u);
  const double acceleration = 60.0 * u * (1.0 - u) * (1.0 - 2.0 * u);
  return {start_rad + delta * smooth,
          delta / duration_s * speed,
          delta / (duration_s * duration_s) * acceleration};
}

}  // namespace sysid_excitation
