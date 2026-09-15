#pragma once

// Fixed-size adapter from the detached excitation runtime into the asynchronous
// file observer. It does not own or modify any command, SDK or transport path.
#include "sysid_excitation_runtime.hpp"
#include "sysid_native_observer.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>

namespace sysid_excitation {

inline sysid::ExcitationRuntimeState ObserverState(RuntimeState state) {
  switch (state) {
    case RuntimeState::kDisarmed:
      return sysid::ExcitationRuntimeState::kDisarmed;
    case RuntimeState::kRunning:
      return sysid::ExcitationRuntimeState::kRunning;
    case RuntimeState::kCompleteHold:
      return sysid::ExcitationRuntimeState::kCompleteHold;
    case RuntimeState::kFaultHold:
      return sysid::ExcitationRuntimeState::kFaultHold;
  }
  throw std::invalid_argument("invalid runtime state");
}

inline sysid::ExcitationContext MakeObserverContext(
    const RuntimeSample& sample) {
  const auto valid_hash = [](const std::string& text) {
    if (text.size() != 64) return false;
    for (const char value : text) {
      if (!((value >= '0' && value <= '9') ||
            (value >= 'a' && value <= 'f'))) return false;
    }
    return true;
  };
  if (!valid_hash(sample.plan_file_sha256) ||
      !valid_hash(sample.request_sha256) || sample.contract_id.empty() ||
      (sample.termination_owner_status != "unresolved" &&
       sample.termination_owner_status != "reviewed") ||
      (sample.episode != "training" && sample.episode != "validation")) {
    throw std::invalid_argument("incomplete excitation provenance");
  }
  return {true,
          sample.plan_file_sha256,
          sample.request_sha256,
          sample.contract_id,
          sample.termination_owner_status,
          sample.episode};
}

inline void AttachObserverTag(const RuntimeSample& sample,
                              const sysid::ExcitationContext& context,
                              sysid::Frame& frame) {
  if (!context.present || sample.plan_file_sha256 != context.plan_file_sha256 ||
      sample.request_sha256 != context.request_sha256 ||
      sample.contract_id != context.contract_id ||
      sample.termination_owner_status != context.termination_owner_status ||
      sample.episode != context.episode) {
    throw std::invalid_argument("excitation provenance changed");
  }
  if ((sample.active_joint != -1 &&
       (sample.active_joint < kRightArmFirst ||
        sample.active_joint > kRightArmLast)) ||
      !std::isfinite(sample.active_velocity_rad_s) ||
      !std::isfinite(sample.active_acceleration_rad_s2)) {
    throw std::invalid_argument("invalid excitation sample");
  }
  if (sample.fault_reason.size() >= frame.excitation.fault_reason.size() ||
      sample.fault_reason.find('\0') != std::string::npos) {
    throw std::invalid_argument("excitation fault reason too long");
  }

  sysid::ExcitationTag tag;
  tag.present = true;
  tag.runtime_state = ObserverState(sample.state);
  tag.plan_tick = sample.tick;
  tag.segment_index = static_cast<std::uint64_t>(sample.segment_index);
  tag.active_joint = sample.active_joint;
  for (std::size_t i = 0; i < tag.right_arm_target_q_rad.size(); ++i) {
    if (!std::isfinite(sample.right_arm_target_q_rad[i])) {
      throw std::invalid_argument("invalid excitation target");
    }
    tag.right_arm_target_q_rad[i] = sample.right_arm_target_q_rad[i];
  }
  tag.active_velocity_rad_s = sample.active_velocity_rad_s;
  tag.active_acceleration_rad_s2 = sample.active_acceleration_rad_s2;
  std::copy(sample.fault_reason.begin(), sample.fault_reason.end(),
            tag.fault_reason.begin());
  frame.excitation = tag;
}

}  // namespace sysid_excitation
