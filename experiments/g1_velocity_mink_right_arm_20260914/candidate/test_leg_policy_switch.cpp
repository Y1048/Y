#include "leg_policy_switch.hpp"

#include <cassert>
#include <iostream>
#include <string>

int main() {
  using namespace twist2;

  LegPolicyMode mode = LegPolicyMode::kStaticStand;
  assert(!velocity_policy_active(mode));
  assert(std::string(leg_policy_mode_name(mode)) == "twist2");
  assert(requested_transition(mode, false) == LegPolicyTransition::kNone);

  mode = apply_transition(mode, requested_transition(mode, true));
  assert(mode == LegPolicyMode::kVelocityBlend);
  assert(std::string(leg_policy_mode_name(mode)) == "to_velocity");
  assert(velocity_policy_active(mode));
  assert(completed_blend_transition(mode, false) ==
         LegPolicyTransition::kNone);
  mode = apply_transition(mode, completed_blend_transition(mode, true));
  assert(mode == LegPolicyMode::kVelocity);
  assert(std::string(leg_policy_mode_name(mode)) == "velocity");

  mode = apply_transition(mode, requested_transition(mode, false));
  assert(mode == LegPolicyMode::kVelocitySettle);
  assert(std::string(leg_policy_mode_name(mode)) == "settle");
  assert(after_velocity_frame_transition(mode, false, true) ==
         LegPolicyTransition::kNone);
  mode = apply_transition(
      mode, after_velocity_frame_transition(mode, false, false));
  assert(mode == LegPolicyMode::kStaticBlend);
  assert(std::string(leg_policy_mode_name(mode)) == "to_twist2");
  mode = apply_transition(mode, completed_blend_transition(mode, true));
  assert(mode == LegPolicyMode::kStaticStand);

  mode = apply_transition(mode, requested_transition(mode, true));
  assert(mode == LegPolicyMode::kVelocityBlend);
  mode = apply_transition(mode, requested_transition(mode, false));
  assert(mode == LegPolicyMode::kStaticBlend);
  mode = apply_transition(mode, requested_transition(mode, true));
  assert(mode == LegPolicyMode::kVelocityBlend);

  mode = LegPolicyMode::kVelocitySettle;
  mode = apply_transition(mode, requested_transition(mode, true));
  assert(mode == LegPolicyMode::kVelocity);

  std::cout << "leg policy switch: PASS\n";
}
