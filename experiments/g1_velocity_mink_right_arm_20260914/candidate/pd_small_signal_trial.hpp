#pragma once

#include "pd_joint_trial.hpp"

// SDK-free, deterministic identification reference. Only right shoulder pitch
// (joint 22) changes. Codes match PdReachTrial so existing CSV analysis can be
// reused: 1=start hold, 2=move, 3=hold, 4=move, 5=hold, 6=done.
class PdSmallSignalTrial {
  std::array<double, 29> baseline_;
  double previous_{-1.0};
  bool stopped_{false};

  static constexpr double kPi = 3.14159265358979323846;
  static constexpr double kOffset = 8.0 * kPi / 180.0;
  static constexpr double kSpeed = 20.0 * kPi / 180.0;
  static constexpr double kAcceleration = 60.0 * kPi / 180.0;
  static constexpr double kVelocityFactor = 1.875;
  static constexpr double kAccelerationFactor = 10.0 / 1.7320508075688772935;
  static constexpr double kInitialHold = 1.0;
  static constexpr double kHold = 0.5;

  static double Duration(double distance) {
    const double velocity_time = kVelocityFactor * distance / kSpeed;
    const double acceleration_time_squared =
        kAccelerationFactor * distance / kAcceleration;
    const double acceleration_time =
        acceleration_time_squared > 0.0
            ? std::sqrt(acceleration_time_squared)
            : 0.0;
    return velocity_time > acceleration_time ? velocity_time
                                              : acceleration_time;
  }

  static double Smooth(double u) {
    return u * u * u * (10.0 + u * (-15.0 + 6.0 * u));
  }

  static double SmoothVelocity(double u) {
    return 30.0 * u * u * (1.0 - u) * (1.0 - u);
  }

  static double SmoothAcceleration(double u) {
    return 60.0 * u * (1.0 - u) * (1.0 - 2.0 * u);
  }

  static PdTrialPoint Segment(const std::array<double, 29>& baseline,
                              double local, double start, double finish,
                              double duration, int phase, int cycle) {
    const double u = std::clamp(local / duration, 0.0, 1.0);
    const double delta = finish - start;
    PdTrialPoint point{baseline};
    point.phase = phase;
    point.cycle = cycle;
    point.q[22] += start + delta * Smooth(u);
    point.dq = delta / duration * SmoothVelocity(u);
    point.ddq = delta / (duration * duration) * SmoothAcceleration(u);
    return point;
  }

 public:
  static constexpr double positive_offset = kOffset;
  static constexpr double negative_offset = -kOffset;
  static constexpr double speed_limit = kSpeed;
  static constexpr double acceleration_limit = kAcceleration;
  inline static const double outbound_seconds = Duration(kOffset);
  inline static const double cross_seconds = Duration(2.0 * kOffset);
  inline static const double return_seconds = Duration(kOffset);
  inline static const double cycle_seconds =
      outbound_seconds + kHold + cross_seconds + kHold + return_seconds + kHold;

  explicit PdSmallSignalTrial(const std::array<double, 29>& q)
      : baseline_(q) {
    for (double value : q) {
      if (!std::isfinite(value)) {
        throw std::runtime_error("pd_small_signal_invalid_baseline");
      }
    }
  }

  double Total() const { return kInitialHold + 3.0 * cycle_seconds; }
  void Stop() { stopped_ = true; }

  PdTrialPoint At(double elapsed) {
    if (stopped_) throw std::runtime_error("pd_small_signal_stopped");
    if (!std::isfinite(elapsed) || elapsed < 0.0 || elapsed < previous_) {
      Stop();
      throw std::runtime_error("pd_small_signal_clock");
    }
    previous_ = elapsed;
    PdTrialPoint point{baseline_};
    if (elapsed < kInitialHold) return point;
    if (elapsed >= Total()) {
      point.phase = 6;
      point.cycle = 3;
      return point;
    }

    const double active = elapsed - kInitialHold;
    const int cycle = static_cast<int>(active / cycle_seconds);
    double local = active - cycle * cycle_seconds;
    if (local < outbound_seconds) {
      return Segment(baseline_, local, 0.0, kOffset, outbound_seconds, 2,
                     cycle);
    }
    local -= outbound_seconds;
    if (local < kHold) {
      point.q[22] += kOffset;
      point.phase = 3;
      point.cycle = cycle;
      return point;
    }
    local -= kHold;
    if (local < cross_seconds) {
      return Segment(baseline_, local, kOffset, -kOffset, cross_seconds, 4,
                     cycle);
    }
    local -= cross_seconds;
    if (local < kHold) {
      point.q[22] -= kOffset;
      point.phase = 3;
      point.cycle = cycle;
      return point;
    }
    local -= kHold;
    if (local < return_seconds) {
      return Segment(baseline_, local, -kOffset, 0.0, return_seconds, 4,
                     cycle);
    }
    point.phase = 5;
    point.cycle = cycle;
    return point;
  }
};
