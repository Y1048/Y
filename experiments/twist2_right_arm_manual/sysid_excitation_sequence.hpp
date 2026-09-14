#pragma once

// Offline excitation sequencing only. This header has no robot SDK, transport,
// controller, clock, file or process dependency.
#include "sysid_excitation_reference.hpp"

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>

namespace sysid_excitation {

constexpr std::size_t kJointCount = 29;
constexpr int kRightArmFirst = 22;
constexpr int kRightArmLast = 28;

enum class SegmentKind { kHold, kQuinticMove };

struct Segment {
  SegmentKind kind{};
  int joint_index{-1};
  double start_offset_rad{};
  double end_offset_rad{};
  double hold_offset_rad{};
  double duration_s{};
};

struct SequenceSample {
  double time_s{};
  std::size_t segment_index{};
  int active_joint{-1};
  std::array<double, kJointCount> target_q_rad{};
  double active_velocity_rad_s{};
  double active_acceleration_rad_s2{};
  bool complete{};
};

class Sequence {
 public:
  Sequence(std::array<double, kJointCount> start_q_rad,
           std::vector<Segment> segments, double sample_period_s)
      : start_q_rad_(start_q_rad), sample_period_s_(sample_period_s) {
    if (!std::isfinite(sample_period_s_) || sample_period_s_ <= 0.0) {
      throw std::invalid_argument("invalid sample period");
    }
    for (const double value : start_q_rad_) {
      if (!std::isfinite(value)) {
        throw std::invalid_argument("nonfinite start position");
      }
    }
    if (segments.empty()) {
      throw std::invalid_argument("empty excitation sequence");
    }

    std::array<double, 7> offsets{};
    std::uint64_t start_tick = 0;
    for (const auto& segment : segments) {
      ValidateFinite(segment);
      const auto steps = DurationSteps(segment.duration_s);
      if (segment.kind == SegmentKind::kHold) {
        if (segment.joint_index == -1) {
          if (segment.hold_offset_rad != 0.0) {
            throw std::invalid_argument("global hold offset must be zero");
          }
        } else {
          const auto local = LocalIndex(segment.joint_index);
          if (std::abs(offsets[local] - segment.hold_offset_rad) > 1e-12) {
            throw std::invalid_argument("hold discontinuity");
          }
        }
      } else if (segment.kind == SegmentKind::kQuinticMove) {
        const auto local = LocalIndex(segment.joint_index);
        if (std::abs(offsets[local] - segment.start_offset_rad) > 1e-12) {
          throw std::invalid_argument("move discontinuity");
        }
      } else {
        throw std::invalid_argument("unknown segment kind");
      }

      if (steps > std::numeric_limits<std::uint64_t>::max() - start_tick) {
        throw std::invalid_argument("excitation duration overflow");
      }
      compiled_.push_back({segment, offsets, start_tick, start_tick + steps});
      if (segment.kind == SegmentKind::kQuinticMove) {
        offsets[LocalIndex(segment.joint_index)] = segment.end_offset_rad;
      }
      start_tick += steps;
    }
    for (const double offset : offsets) {
      if (std::abs(offset) > 1e-12) {
        throw std::invalid_argument("sequence does not return to start");
      }
    }
    total_ticks_ = start_tick;
  }

  std::uint64_t total_ticks() const { return total_ticks_; }
  double duration_s() const { return total_ticks_ * sample_period_s_; }

  SequenceSample AtTick(std::uint64_t tick) const {
    if (tick > total_ticks_) {
      throw std::out_of_range("excitation tick exceeds sequence");
    }
    if (tick == total_ticks_) {
      return {duration_s(), compiled_.size(), -1, start_q_rad_, 0.0, 0.0,
              true};
    }

    const CompiledSegment* selected = nullptr;
    std::size_t index = 0;
    for (; index < compiled_.size(); ++index) {
      if (tick >= compiled_[index].start_tick &&
          tick < compiled_[index].end_tick) {
        selected = &compiled_[index];
        break;
      }
    }
    if (selected == nullptr) {
      throw std::logic_error("unmapped excitation tick");
    }

    SequenceSample sample;
    sample.time_s = tick * sample_period_s_;
    sample.segment_index = index;
    sample.active_joint = selected->segment.joint_index;
    sample.target_q_rad = start_q_rad_;
    for (std::size_t local = 0; local < selected->offsets_before.size();
         ++local) {
      sample.target_q_rad[kRightArmFirst + local] +=
          selected->offsets_before[local];
    }
    if (selected->segment.kind == SegmentKind::kQuinticMove) {
      const auto joint = selected->segment.joint_index;
      const auto point = Quintic(
          start_q_rad_[joint] + selected->segment.start_offset_rad,
          start_q_rad_[joint] + selected->segment.end_offset_rad,
          (tick - selected->start_tick) * sample_period_s_,
          selected->segment.duration_s);
      sample.target_q_rad[joint] = point.position_rad;
      sample.active_velocity_rad_s = point.velocity_rad_s;
      sample.active_acceleration_rad_s2 = point.acceleration_rad_s2;
    }
    return sample;
  }

 private:
  struct CompiledSegment {
    Segment segment;
    std::array<double, 7> offsets_before;
    std::uint64_t start_tick;
    std::uint64_t end_tick;
  };

  static std::size_t LocalIndex(int joint_index) {
    if (joint_index < kRightArmFirst || joint_index > kRightArmLast) {
      throw std::invalid_argument("joint outside right arm");
    }
    return static_cast<std::size_t>(joint_index - kRightArmFirst);
  }

  static void ValidateFinite(const Segment& segment) {
    if (!std::isfinite(segment.start_offset_rad) ||
        !std::isfinite(segment.end_offset_rad) ||
        !std::isfinite(segment.hold_offset_rad) ||
        !std::isfinite(segment.duration_s) || segment.duration_s <= 0.0) {
      throw std::invalid_argument("invalid excitation segment");
    }
  }

  std::uint64_t DurationSteps(double duration_s) const {
    const double raw_steps = duration_s / sample_period_s_;
    if (!std::isfinite(raw_steps) || raw_steps < 1.0 ||
        raw_steps > static_cast<double>(
                        std::numeric_limits<std::uint64_t>::max())) {
      throw std::invalid_argument("invalid excitation step count");
    }
    const auto steps = static_cast<std::uint64_t>(std::llround(raw_steps));
    if (steps == 0 ||
        std::abs(steps * sample_period_s_ - duration_s) > 1e-10) {
      throw std::invalid_argument("segment is off sample grid");
    }
    return steps;
  }

  std::array<double, kJointCount> start_q_rad_{};
  double sample_period_s_{};
  std::vector<CompiledSegment> compiled_;
  std::uint64_t total_ticks_{};
};

}  // namespace sysid_excitation
