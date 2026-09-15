#include "sysid_excitation_plan_adapter.hpp"

#include <cassert>
#include <cmath>
#include <stdexcept>

namespace {

using sysid_excitation::Json;

const char* Name(int joint) {
  return sysid_excitation::detail::kRightArmNames[joint - 22];
}

Json Episode(const std::array<int, 7>& order) {
  Json segments = Json::array();
  segments.push_back({{"kind", "hold"}, {"offset_rad", 0.0},
                      {"duration_s", 0.004}});
  constexpr double kDuration = 0.4;
  constexpr double kOffset = 0.05;
  const double velocity = 1.875 * kOffset / kDuration;
  const double acceleration =
      (10.0 / std::sqrt(3.0)) * kOffset / (kDuration * kDuration);
  for (const int joint : order) {
    for (const auto endpoints :
         {std::array<double, 2>{0.0, kOffset},
          std::array<double, 2>{kOffset, 0.0}}) {
      segments.push_back(
          {{"kind", "quintic_move"},
           {"joint_index", joint},
           {"joint_name", Name(joint)},
           {"start_offset_rad", endpoints[0]},
           {"end_offset_rad", endpoints[1]},
           {"duration_s", kDuration},
           {"analytic_peak_velocity_rad_s", velocity},
           {"analytic_peak_acceleration_rad_s2", acceleration}});
      segments.push_back({{"kind", "hold"},
                          {"joint_index", joint},
                          {"joint_name", Name(joint)},
                          {"offset_rad", endpoints[1]},
                          {"duration_s", 0.004}});
    }
  }
  return {{"joint_order", order}, {"segments", segments}};
}

Json Plan() {
  const std::array<int, 7> training = {22, 23, 24, 25, 26, 27, 28};
  const std::array<int, 7> validation = {28, 27, 26, 25, 24, 23, 22};
  Json names = Json::array();
  for (int joint = 22; joint <= 28; ++joint) {
    names.push_back(Name(joint));
  }
  return {{"schema", "g1.sysid.excitation-plan.v1"},
          {"request_sha256", std::string(64, '0')},
          {"contract_id", "generated-native-fixture"},
          {"termination_owner_contract",
           {{"status", "unresolved"}, {"description", "offline fixture"}}},
          {"command_capable", false},
          {"execution_authorized", false},
          {"recommended_hardware_gains", nullptr},
          {"joint_indices", training},
          {"joint_names", names},
          {"start_q_rad", std::vector<double>(29, 0.0)},
          {"kp_nm_rad", std::vector<double>(29, 40.0)},
          {"kd_nm_s_rad", std::vector<double>(29, 5.0)},
          {"soft_lower_q_rad", std::vector<double>(29, -1.0)},
          {"soft_upper_q_rad", std::vector<double>(29, 1.0)},
          {"sample_period_s", 0.002},
          {"episodes", {{"training", Episode(training)},
                        {"validation", Episode(validation)}}}};
}

void MustReject(const Json& value) {
  bool rejected = false;
  try {
    (void)sysid_excitation::LoadPlan(value);
  } catch (const std::invalid_argument&) {
    rejected = true;
  }
  assert(rejected);
}

}  // namespace

int main() {
  const auto loaded = sysid_excitation::LoadPlan(Plan());
  const sysid_excitation::Sequence training(
      loaded.start_q_rad, loaded.training, loaded.sample_period_s);
  const sysid_excitation::Sequence validation(
      loaded.start_q_rad, loaded.validation, loaded.sample_period_s);
  assert(training.total_ticks() == 2830);
  assert(training.total_ticks() == validation.total_ticks());
  assert(training.AtTick(training.total_ticks()).target_q_rad ==
         loaded.start_q_rad);
  assert(validation.AtTick(validation.total_ticks()).target_q_rad ==
         loaded.start_q_rad);

  auto invalid = Plan();
  invalid["command_capable"] = true;
  MustReject(invalid);
  invalid = Plan();
  invalid["joint_names"][0] = "wrong";
  MustReject(invalid);
  invalid = Plan();
  invalid["episodes"]["training"]["segments"][1]
         ["analytic_peak_velocity_rad_s"] = 0.0;
  MustReject(invalid);
  invalid = Plan();
  invalid["soft_upper_q_rad"][22] = 0.01;
  MustReject(invalid);
  invalid = Plan();
  invalid["episodes"]["training"]["segments"][2]["offset_rad"] = 0.04;
  MustReject(invalid);
  invalid = Plan();
  invalid["start_q_rad"][0] = std::numeric_limits<double>::quiet_NaN();
  MustReject(invalid);
  invalid = Plan();
  invalid["kp_nm_rad"][22] = 0.0;
  MustReject(invalid);
  invalid = Plan();
  invalid["request_sha256"] = "short";
  MustReject(invalid);
  invalid = Plan();
  invalid["termination_owner_contract"]["status"] = "invented";
  MustReject(invalid);
  return 0;
}
