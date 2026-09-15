#pragma once

// Candidate 500-Hz writer-side math only. It returns seven right-arm targets
// and cannot initialize a robot, publish data, modify gains or own termination.
#include "sysid_excitation_plan_adapter.hpp"

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace sysid_excitation {

enum class EpisodeKind { kTraining, kValidation };

struct WriterHookSample {
  std::uint64_t tick{};
  std::size_t segment_index{};
  int active_joint{-1};
  std::array<double, 7> right_arm_target_q_rad{};
  double active_velocity_rad_s{};
  double active_acceleration_rad_s2{};
  bool complete{};
};

class WriterHook {
 public:
  WriterHook(LoadedPlan plan, EpisodeKind episode,
             double expected_writer_period_s, double start_tolerance_rad,
             double gain_tolerance)
      : planned_start_(plan.start_q_rad),
        planned_kp_(plan.kp_nm_rad),
        planned_kd_(plan.kd_nm_s_rad),
        start_tolerance_rad_(start_tolerance_rad),
        gain_tolerance_(gain_tolerance),
        sequence_(plan.start_q_rad,
                  episode == EpisodeKind::kTraining
                      ? std::move(plan.training)
                      : std::move(plan.validation),
                  plan.sample_period_s) {
    if (!std::isfinite(expected_writer_period_s) ||
        expected_writer_period_s <= 0.0 ||
        std::abs(plan.sample_period_s - expected_writer_period_s) > 1e-12) {
      throw std::invalid_argument("plan/writer period mismatch");
    }
    if (!std::isfinite(start_tolerance_rad_) || start_tolerance_rad_ < 0.0 ||
        !std::isfinite(gain_tolerance_) || gain_tolerance_ < 0.0) {
      throw std::invalid_argument("invalid explicit runtime tolerance");
    }
  }

  void Arm(const std::array<double, kJointCount>& measured_q_rad,
           const std::array<double, kJointCount>& active_kp_nm_rad,
           const std::array<double, kJointCount>& active_kd_nm_s_rad) {
    if (armed_) {
      throw std::logic_error("writer hook already armed");
    }
    for (int joint = kRightArmFirst; joint <= kRightArmLast; ++joint) {
      if (!std::isfinite(measured_q_rad[joint]) ||
          !std::isfinite(active_kp_nm_rad[joint]) ||
          !std::isfinite(active_kd_nm_s_rad[joint])) {
        throw std::invalid_argument("nonfinite writer arming input");
      }
      if (std::abs(measured_q_rad[joint] - planned_start_[joint]) >
          start_tolerance_rad_) {
        throw std::invalid_argument("right-arm start mismatch");
      }
      if (std::abs(active_kp_nm_rad[joint] - planned_kp_[joint]) >
              gain_tolerance_ ||
          std::abs(active_kd_nm_s_rad[joint] - planned_kd_[joint]) >
              gain_tolerance_) {
        throw std::invalid_argument("right-arm gain mismatch");
      }
    }
    armed_ = true;
  }

  WriterHookSample Next() {
    if (!armed_) {
      throw std::logic_error("writer hook is not armed");
    }
    const auto sample = sequence_.AtTick(next_tick_);
    WriterHookSample result;
    result.tick = next_tick_;
    result.segment_index = sample.segment_index;
    result.active_joint = sample.active_joint;
    for (std::size_t local = 0; local < result.right_arm_target_q_rad.size();
         ++local) {
      result.right_arm_target_q_rad[local] =
          sample.target_q_rad[kRightArmFirst + local];
    }
    result.active_velocity_rad_s = sample.active_velocity_rad_s;
    result.active_acceleration_rad_s2 = sample.active_acceleration_rad_s2;
    result.complete = sample.complete;
    if (!sample.complete) {
      ++next_tick_;
    }
    return result;
  }

  bool armed() const { return armed_; }
  std::uint64_t total_ticks() const { return sequence_.total_ticks(); }

 private:
  std::array<double, kJointCount> planned_start_{};
  std::array<double, kJointCount> planned_kp_{};
  std::array<double, kJointCount> planned_kd_{};
  double start_tolerance_rad_{};
  double gain_tolerance_{};
  Sequence sequence_;
  std::uint64_t next_tick_{};
  bool armed_{};
};

}  // namespace sysid_excitation
