#pragma once

// Detached state/provenance coordinator for offline writer-hook tests. It owns
// no clock, transport, publisher, full-body target or termination mechanism.
#include "sysid_excitation_writer_hook.hpp"

#include <array>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>

namespace sysid_excitation {

enum class RuntimeState { kDisarmed, kRunning, kCompleteHold, kFaultHold };

struct RuntimeSample {
  RuntimeState state{RuntimeState::kDisarmed};
  std::string plan_file_sha256;
  std::string request_sha256;
  std::string contract_id;
  std::string termination_owner_status;
  std::string episode;
  std::string fault_reason;
  std::uint64_t tick{};
  std::size_t segment_index{};
  int active_joint{-1};
  std::array<double, 7> right_arm_target_q_rad{};
  double active_velocity_rad_s{};
  double active_acceleration_rad_s2{};
};

class Runtime {
 public:
  Runtime(LoadedPlan plan, EpisodeKind episode, std::string plan_file_sha256,
          double expected_writer_period_s, double start_tolerance_rad,
          double gain_tolerance)
      : request_sha256_(plan.request_sha256),
        contract_id_(plan.contract_id),
        termination_owner_status_(plan.termination_owner_status),
        episode_(episode == EpisodeKind::kTraining ? "training" : "validation"),
        plan_file_sha256_(std::move(plan_file_sha256)),
        hook_(std::move(plan), episode, expected_writer_period_s,
              start_tolerance_rad, gain_tolerance) {
    if (!ValidHash(plan_file_sha256_)) {
      throw std::invalid_argument("invalid plan file hash");
    }
  }

  void Arm(const std::array<double, kJointCount>& measured_q_rad,
           const std::array<double, kJointCount>& active_kp_nm_rad,
           const std::array<double, kJointCount>& active_kd_nm_s_rad) {
    if (state_ != RuntimeState::kDisarmed) {
      throw std::logic_error("runtime is not disarmed");
    }
    hook_.Arm(measured_q_rad, active_kp_nm_rad, active_kd_nm_s_rad);
    state_ = RuntimeState::kRunning;
  }

  RuntimeSample Tick() {
    if (state_ == RuntimeState::kDisarmed) {
      throw std::logic_error("runtime is not armed");
    }
    if (state_ == RuntimeState::kFaultHold) {
      return HeldSample();
    }
    const auto sample = hook_.Next();
    last_ = sample;
    have_last_ = true;
    if (sample.complete) {
      state_ = RuntimeState::kCompleteHold;
    }
    return MakeSample(sample);
  }

  void LatchFault(std::string reason) {
    if (state_ == RuntimeState::kDisarmed || !have_last_) {
      throw std::logic_error("cannot fault-hold before first valid sample");
    }
    if (reason.empty()) {
      throw std::invalid_argument("fault reason is empty");
    }
    if (state_ != RuntimeState::kFaultHold) {
      fault_reason_ = std::move(reason);
      state_ = RuntimeState::kFaultHold;
    }
  }

  RuntimeState state() const { return state_; }

 private:
  static bool ValidHash(const std::string& text) {
    if (text.size() != 64) return false;
    for (const char value : text) {
      if (!((value >= '0' && value <= '9') ||
            (value >= 'a' && value <= 'f'))) return false;
    }
    return true;
  }

  RuntimeSample MakeSample(const WriterHookSample& sample) const {
    return {state_,
            plan_file_sha256_,
            request_sha256_,
            contract_id_,
            termination_owner_status_,
            episode_,
            fault_reason_,
            sample.tick,
            sample.segment_index,
            sample.active_joint,
            sample.right_arm_target_q_rad,
            sample.active_velocity_rad_s,
            sample.active_acceleration_rad_s2};
  }

  RuntimeSample HeldSample() const {
    auto result = MakeSample(last_);
    result.state = RuntimeState::kFaultHold;
    result.active_velocity_rad_s = 0.0;
    result.active_acceleration_rad_s2 = 0.0;
    return result;
  }

  std::string request_sha256_;
  std::string contract_id_;
  std::string termination_owner_status_;
  std::string episode_;
  std::string plan_file_sha256_;
  WriterHook hook_;
  WriterHookSample last_{};
  RuntimeState state_{RuntimeState::kDisarmed};
  std::string fault_reason_;
  bool have_last_{};
};

}  // namespace sysid_excitation
