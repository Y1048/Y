#pragma once

// Strict offline conversion from a validated JSON value into the SDK-free
// sequence core. This header performs no I/O and has no robot or transport path.
#include "sysid_excitation_sequence.hpp"
#include "vendor/json.hpp"

#include <array>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

namespace sysid_excitation {

using Json = nlohmann::json;

struct LoadedPlan {
  std::string request_sha256;
  std::string contract_id;
  std::string termination_owner_status;
  std::array<double, kJointCount> start_q_rad{};
  std::array<double, kJointCount> kp_nm_rad{};
  std::array<double, kJointCount> kd_nm_s_rad{};
  double sample_period_s{};
  std::vector<Segment> training;
  std::vector<Segment> validation;
};

namespace detail {

constexpr std::array<const char*, 7> kRightArmNames = {
    "right_shoulder_pitch", "right_shoulder_roll", "right_shoulder_yaw",
    "right_elbow",          "right_wrist_roll",    "right_wrist_pitch",
    "right_wrist_yaw"};

inline void Require(bool condition, const char* reason) {
  if (!condition) {
    throw std::invalid_argument(reason);
  }
}

inline double Number(const Json& value, const char* key) {
  Require(value.contains(key) && value.at(key).is_number(), "missing number");
  const double result = value.at(key).get<double>();
  Require(std::isfinite(result), "nonfinite number");
  return result;
}

inline int Integer(const Json& value, const char* key) {
  Require(value.contains(key) && value.at(key).is_number_integer(),
          "missing integer");
  return value.at(key).get<int>();
}

inline std::string Text(const Json& value, const char* key) {
  Require(value.contains(key) && value.at(key).is_string(), "missing string");
  return value.at(key).get<std::string>();
}

inline std::array<double, kJointCount> Vector29(const Json& value,
                                                const char* key) {
  Require(value.contains(key) && value.at(key).is_array() &&
              value.at(key).size() == kJointCount,
          "invalid 29-axis vector");
  std::array<double, kJointCount> result{};
  for (std::size_t i = 0; i < result.size(); ++i) {
    Require(value.at(key).at(i).is_number(), "invalid vector number");
    result[i] = value.at(key).at(i).get<double>();
    Require(std::isfinite(result[i]), "nonfinite vector number");
  }
  return result;
}

inline void CheckJointIdentity(const Json& value, int joint) {
  Require(joint >= kRightArmFirst && joint <= kRightArmLast,
          "joint outside right arm");
  Require(Text(value, "joint_name") == kRightArmNames[joint - kRightArmFirst],
          "joint name/index mismatch");
}

inline std::vector<Segment> Episode(const Json& episode,
                                    const std::array<int, 7>& expected_order,
                                    const std::array<double, kJointCount>& start,
                                    const std::array<double, kJointCount>& lower,
                                    const std::array<double, kJointCount>& upper) {
  Require(episode.is_object(), "invalid episode");
  Require(episode.contains("joint_order") &&
              episode.at("joint_order").is_array() &&
              episode.at("joint_order").size() == expected_order.size(),
          "invalid episode joint order");
  for (std::size_t i = 0; i < expected_order.size(); ++i) {
    Require(episode.at("joint_order").at(i).is_number_integer() &&
                episode.at("joint_order").at(i).get<int>() == expected_order[i],
            "unexpected episode joint order");
  }
  Require(episode.contains("segments") && episode.at("segments").is_array() &&
              !episode.at("segments").empty(),
          "missing episode segments");

  std::vector<Segment> result;
  std::vector<int> observed_order;
  int previous_move_joint = -1;
  const auto& values = episode.at("segments");
  result.reserve(values.size());
  for (std::size_t index = 0; index < values.size(); ++index) {
    const auto& value = values.at(index);
    Require(value.is_object(), "invalid segment object");
    const auto kind = Text(value, "kind");
    const double duration = Number(value, "duration_s");
    if (kind == "hold") {
      const double offset = Number(value, "offset_rad");
      if (!value.contains("joint_index")) {
        Require(index == 0 && offset == 0.0, "invalid global hold");
        result.push_back(
            {SegmentKind::kHold, -1, 0.0, 0.0, 0.0, duration});
      } else {
        const int joint = Integer(value, "joint_index");
        CheckJointIdentity(value, joint);
        Require(start[joint] + offset >= lower[joint] &&
                    start[joint] + offset <= upper[joint],
                "hold outside soft limits");
        result.push_back(
            {SegmentKind::kHold, joint, 0.0, 0.0, offset, duration});
      }
    } else if (kind == "quintic_move") {
      const int joint = Integer(value, "joint_index");
      CheckJointIdentity(value, joint);
      const double begin = Number(value, "start_offset_rad");
      const double end = Number(value, "end_offset_rad");
      Require(start[joint] + begin >= lower[joint] &&
                  start[joint] + begin <= upper[joint] &&
                  start[joint] + end >= lower[joint] &&
                  start[joint] + end <= upper[joint],
              "move outside soft limits");
      const double expected_velocity = 1.875 * std::abs(end - begin) / duration;
      const double expected_acceleration =
          (10.0 / std::sqrt(3.0)) * std::abs(end - begin) /
          (duration * duration);
      Require(std::abs(Number(value, "analytic_peak_velocity_rad_s") -
                       expected_velocity) <= 1e-10,
              "analytic velocity mismatch");
      Require(std::abs(Number(value, "analytic_peak_acceleration_rad_s2") -
                       expected_acceleration) <= 1e-10,
              "analytic acceleration mismatch");
      if (joint != previous_move_joint) {
        observed_order.push_back(joint);
        previous_move_joint = joint;
      }
      result.push_back({SegmentKind::kQuinticMove, joint, begin, end, 0.0,
                        duration});
    } else {
      throw std::invalid_argument("unknown segment kind");
    }
  }
  Require(observed_order.size() == expected_order.size(),
          "incomplete observed joint order");
  for (std::size_t i = 0; i < expected_order.size(); ++i) {
    Require(observed_order[i] == expected_order[i],
            "segment order does not match episode order");
  }
  return result;
}

}  // namespace detail

inline LoadedPlan LoadPlan(const Json& value) {
  detail::Require(value.is_object(), "plan must be an object");
  detail::Require(detail::Text(value, "schema") ==
                      "g1.sysid.excitation-plan.v1",
                  "plan schema mismatch");
  detail::Require(value.contains("command_capable") &&
                      value.at("command_capable").is_boolean() &&
                      !value.at("command_capable").get<bool>(),
                  "command-capable plan rejected");
  detail::Require(value.contains("execution_authorized") &&
                      value.at("execution_authorized").is_boolean() &&
                      !value.at("execution_authorized").get<bool>(),
                  "execution-authorized plan rejected");
  detail::Require(value.contains("recommended_hardware_gains") &&
                      value.at("recommended_hardware_gains").is_null(),
                  "hardware gain recommendation rejected");
  const auto valid_hash = [](const std::string& text) {
    if (text.size() != 64) return false;
    for (const char value : text) {
      if (!((value >= '0' && value <= '9') ||
            (value >= 'a' && value <= 'f'))) return false;
    }
    return true;
  };
  const auto request_sha256 = detail::Text(value, "request_sha256");
  detail::Require(valid_hash(request_sha256), "invalid request hash");
  const auto contract_id = detail::Text(value, "contract_id");
  detail::Require(!contract_id.empty(), "empty contract id");
  detail::Require(value.contains("termination_owner_contract") &&
                      value.at("termination_owner_contract").is_object(),
                  "missing termination owner contract");
  const auto owner_status = detail::Text(
      value.at("termination_owner_contract"), "status");
  detail::Require(owner_status == "unresolved" || owner_status == "reviewed",
                  "invalid termination owner status");
  detail::Require(value.contains("joint_indices") &&
                      value.at("joint_indices").is_array() &&
                      value.at("joint_indices").size() == 7,
                  "invalid right-arm indices");
  detail::Require(value.contains("joint_names") &&
                      value.at("joint_names").is_array() &&
                      value.at("joint_names").size() == 7,
                  "invalid right-arm names");
  for (std::size_t local = 0; local < 7; ++local) {
    detail::Require(
        value.at("joint_indices").at(local).is_number_integer() &&
            value.at("joint_indices").at(local).get<int>() ==
                kRightArmFirst + static_cast<int>(local),
        "right-arm index order mismatch");
    detail::Require(value.at("joint_names").at(local).is_string() &&
                        value.at("joint_names").at(local).get<std::string>() ==
                            detail::kRightArmNames[local],
                    "right-arm name order mismatch");
  }

  LoadedPlan result;
  result.request_sha256 = request_sha256;
  result.contract_id = contract_id;
  result.termination_owner_status = owner_status;
  result.start_q_rad = detail::Vector29(value, "start_q_rad");
  result.kp_nm_rad = detail::Vector29(value, "kp_nm_rad");
  result.kd_nm_s_rad = detail::Vector29(value, "kd_nm_s_rad");
  const auto lower = detail::Vector29(value, "soft_lower_q_rad");
  const auto upper = detail::Vector29(value, "soft_upper_q_rad");
  for (std::size_t joint = 0; joint < kJointCount; ++joint) {
    detail::Require(lower[joint] < result.start_q_rad[joint] &&
                        result.start_q_rad[joint] < upper[joint],
                    "start outside soft limits");
    detail::Require(result.kp_nm_rad[joint] > 0.0 &&
                        result.kd_nm_s_rad[joint] > 0.0,
                    "nonpositive planned gain");
  }
  result.sample_period_s = detail::Number(value, "sample_period_s");
  detail::Require(result.sample_period_s > 0.0, "invalid sample period");
  detail::Require(value.contains("episodes") && value.at("episodes").is_object(),
                  "missing episodes");
  constexpr std::array<int, 7> kTraining = {22, 23, 24, 25, 26, 27, 28};
  constexpr std::array<int, 7> kValidation = {28, 27, 26, 25, 24, 23, 22};
  detail::Require(value.at("episodes").contains("training") &&
                      value.at("episodes").contains("validation"),
                  "missing training or validation episode");
  result.training = detail::Episode(value.at("episodes").at("training"),
                                    kTraining, result.start_q_rad, lower, upper);
  result.validation = detail::Episode(value.at("episodes").at("validation"),
                                      kValidation, result.start_q_rad, lower,
                                      upper);
  (void)Sequence(result.start_q_rad, result.training, result.sample_period_s);
  (void)Sequence(result.start_q_rad, result.validation, result.sample_period_s);
  return result;
}

}  // namespace sysid_excitation
