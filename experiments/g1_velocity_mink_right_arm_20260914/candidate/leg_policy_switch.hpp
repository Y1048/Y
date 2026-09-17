#pragma once

namespace twist2 {

enum class LegPolicyMode {
  kStaticStand,
  kVelocityBlend,
  kVelocity,
  kVelocitySettle,
  kStaticBlend,
};

enum class LegPolicyTransition {
  kNone,
  kStartVelocityBlend,
  kResumeVelocity,
  kStartVelocitySettle,
  kStartStaticBlend,
  kFinishVelocityBlend,
  kFinishStaticBlend,
};

constexpr LegPolicyTransition requested_transition(
    LegPolicyMode mode, bool velocity_requested) {
  if (velocity_requested) {
    if (mode == LegPolicyMode::kStaticStand ||
        mode == LegPolicyMode::kStaticBlend) {
      return LegPolicyTransition::kStartVelocityBlend;
    }
    if (mode == LegPolicyMode::kVelocitySettle) {
      return LegPolicyTransition::kResumeVelocity;
    }
    return LegPolicyTransition::kNone;
  }
  if (mode == LegPolicyMode::kVelocity) {
    return LegPolicyTransition::kStartVelocitySettle;
  }
  if (mode == LegPolicyMode::kVelocityBlend) {
    return LegPolicyTransition::kStartStaticBlend;
  }
  return LegPolicyTransition::kNone;
}

constexpr LegPolicyTransition after_velocity_frame_transition(
    LegPolicyMode mode, bool velocity_requested, bool gait_clock_running) {
  return mode == LegPolicyMode::kVelocitySettle && !velocity_requested &&
                 !gait_clock_running
             ? LegPolicyTransition::kStartStaticBlend
             : LegPolicyTransition::kNone;
}

constexpr LegPolicyTransition completed_blend_transition(
    LegPolicyMode mode, bool blend_complete) {
  if (!blend_complete) return LegPolicyTransition::kNone;
  if (mode == LegPolicyMode::kVelocityBlend) {
    return LegPolicyTransition::kFinishVelocityBlend;
  }
  if (mode == LegPolicyMode::kStaticBlend) {
    return LegPolicyTransition::kFinishStaticBlend;
  }
  return LegPolicyTransition::kNone;
}

constexpr LegPolicyMode apply_transition(
    LegPolicyMode current, LegPolicyTransition transition) {
  switch (transition) {
    case LegPolicyTransition::kStartVelocityBlend:
      return LegPolicyMode::kVelocityBlend;
    case LegPolicyTransition::kResumeVelocity:
    case LegPolicyTransition::kFinishVelocityBlend:
      return LegPolicyMode::kVelocity;
    case LegPolicyTransition::kStartVelocitySettle:
      return LegPolicyMode::kVelocitySettle;
    case LegPolicyTransition::kStartStaticBlend:
      return LegPolicyMode::kStaticBlend;
    case LegPolicyTransition::kFinishStaticBlend:
      return LegPolicyMode::kStaticStand;
    case LegPolicyTransition::kNone:
      return current;
  }
  return current;
}

constexpr bool velocity_policy_active(LegPolicyMode mode) {
  return mode == LegPolicyMode::kVelocityBlend ||
         mode == LegPolicyMode::kVelocity ||
         mode == LegPolicyMode::kVelocitySettle;
}

inline const char* leg_policy_mode_name(LegPolicyMode mode) {
  switch (mode) {
    case LegPolicyMode::kStaticStand: return "twist2";
    case LegPolicyMode::kVelocityBlend: return "to_velocity";
    case LegPolicyMode::kVelocity: return "velocity";
    case LegPolicyMode::kVelocitySettle: return "settle";
    case LegPolicyMode::kStaticBlend: return "to_twist2";
  }
  return "unknown";
}

}  // namespace twist2
