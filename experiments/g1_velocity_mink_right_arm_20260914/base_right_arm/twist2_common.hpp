#pragma once

#include <torch/script.h>
#include <torch/torch.h>

#include <unitree/idl/hg/LowCmd_.hpp>
#include <unitree/idl/hg/LowState_.hpp>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <limits>
#include <memory>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace twist2 {

using Clock = std::chrono::steady_clock;
using LowCmd = unitree_hg::msg::dds_::LowCmd_;
using LowState = unitree_hg::msg::dds_::LowState_;

constexpr std::size_t kDofs = 29;
constexpr std::size_t kLegDofs = 12;
constexpr std::size_t kMimicObservations = 35;
constexpr std::size_t kProprioObservations = 92;
constexpr std::size_t kSingleObservations = 127;
constexpr std::size_t kHistory = 10;
constexpr std::size_t kObservations = 1432;
constexpr int kExpectedModePr = 0;
constexpr int kExpectedModeMachine = 5;
constexpr auto kPolicyPeriod = std::chrono::milliseconds(20);
constexpr float kActionScale = 0.5F;
constexpr float kActionLimit = 2.0F;
constexpr float kJointLimitMargin = 0.05F;
constexpr float kObservationLimit = 100.0F;
constexpr char kExpectedPolicySha256[] =
    "463be0376c2c1f551b996d0bf9ab97833854f2cc098b9d4fea735f17ec2e9015";

const std::array<float, kDofs> kDefault = {
    -0.2F, 0, 0, 0.4F, -0.2F, 0,
    -0.2F, 0, 0, 0.4F, -0.2F, 0,
    0, 0, 0,
    0, 0.4F, 0, 1.2F, 0, 0, 0,
    0, -0.4F, 0, 1.2F, 0, 0, 0};

const std::array<float, kDofs> kKp = {
    100, 100, 100, 150, 40, 40, 100, 100, 100, 150, 40, 40,
    150, 150, 150,
    40, 40, 40, 40, 20, 20, 20,
    40, 40, 40, 40, 20, 20, 20};

const std::array<float, kDofs> kKd = {
    2, 2, 2, 4, 2, 2, 2, 2, 2, 4, 2, 2,
    4, 4, 4,
    5, 5, 5, 5, 1, 1, 1,
    5, 5, 5, 5, 1, 1, 1};

const std::array<float, kDofs> kTorqueLimit = {
    88, 139, 88, 139, 50, 50, 88, 139, 88, 139, 50, 50,
    88, 50, 50,
    25, 25, 25, 25, 25, 5, 5,
    25, 25, 25, 25, 25, 5, 5};

const std::array<float, kDofs> kLower = {
    -2.5307F, -0.5236F, -2.7576F, -0.087267F, -0.87267F, -0.2618F,
    -2.5307F, -2.9671F, -2.7576F, -0.087267F, -0.87267F, -0.2618F,
    -2.618F, -0.52F, -0.52F,
    -3.0892F, -1.5882F, -2.618F, -1.0472F, -1.972222054F,
    -1.614429558F, -1.614429558F,
    -3.0892F, -2.2515F, -2.618F, -1.0472F, -1.972222054F,
    -1.614429558F, -1.614429558F};

const std::array<float, kDofs> kUpper = {
    2.8798F, 2.9671F, 2.7576F, 2.8798F, 0.5236F, 0.2618F,
    2.8798F, 0.5236F, 2.7576F, 2.8798F, 0.5236F, 0.2618F,
    2.618F, 0.52F, 0.52F,
    2.6704F, 2.2515F, 2.618F, 2.0944F, 1.972222054F,
    1.614429558F, 1.614429558F,
    2.6704F, 1.5882F, 2.618F, 2.0944F, 1.972222054F,
    1.614429558F, 1.614429558F};

inline float smoothstep(float value) {
  value = std::clamp(value, 0.0F, 1.0F);
  return value * value * (3.0F - 2.0F * value);
}

inline double percentile(std::vector<double> values, double fraction) {
  if (values.empty()) {
    return std::numeric_limits<double>::quiet_NaN();
  }
  std::sort(values.begin(), values.end());
  const double position = fraction * static_cast<double>(values.size() - 1);
  const auto lower = static_cast<std::size_t>(std::floor(position));
  const auto upper = static_cast<std::size_t>(std::ceil(position));
  const double alpha = position - static_cast<double>(lower);
  return values[lower] * (1.0 - alpha) + values[upper] * alpha;
}

inline bool command_watchdog_expired(
    Clock::time_point now,
    Clock::time_point command_created,
    Clock::time_point activated,
    Clock::duration command_timeout,
    Clock::duration handoff_grace) {
  return now - command_created > command_timeout &&
         now - activated > handoff_grace;
}

inline float update_keyboard_joint_command(
    char key,
    char plus_key,
    char zero_key,
    char minus_key,
    float command,
    float lower_limit,
    float upper_limit,
    float increment) {
  if (key == plus_key) {
    command += increment;
  } else if (key == zero_key) {
    command = 0.0F;
  } else if (key == minus_key) {
    command -= increment;
  }
  return std::clamp(command, lower_limit, upper_limit);
}

inline float rate_limited_target(
    float target,
    float command,
    float maximum_rate,
    float dt) {
  const float maximum_step = maximum_rate * dt;
  return target +
         std::clamp(command - target, -maximum_step, maximum_step);
}

inline std::uint16_t remote_buttons(const LowState& state) {
  const auto& remote = state.wireless_remote();
  return static_cast<std::uint16_t>(remote[2]) |
         (static_cast<std::uint16_t>(remote[3]) << 8U);
}

inline std::uint32_t crc32_core(std::uint32_t* ptr, std::uint32_t len) {
  std::uint32_t crc = 0xFFFFFFFFU;
  constexpr std::uint32_t polynomial = 0x04c11db7U;
  for (std::uint32_t i = 0; i < len; ++i) {
    std::uint32_t xbit = 1U << 31U;
    const std::uint32_t data = ptr[i];
    for (int bits = 0; bits < 32; ++bits) {
      crc = (crc & 0x80000000U) ? (crc << 1U) ^ polynomial : crc << 1U;
      if (data & xbit) {
        crc ^= polynomial;
      }
      xbit >>= 1U;
    }
  }
  return crc;
}

inline bool valid_crc(const LowState& state) {
  LowState copy = state;
  return copy.crc() ==
         crc32_core(
             reinterpret_cast<std::uint32_t*>(&copy),
             (sizeof(LowState) >> 2U) - 1U);
}

inline std::string sha256sum(const std::filesystem::path& path) {
  if (path.string().find('\'') != std::string::npos) {
    throw std::runtime_error("Policy path may not contain a single quote");
  }
  const std::string command = "sha256sum '" + path.string() + "'";
  std::unique_ptr<FILE, decltype(&pclose)> pipe(
      popen(command.c_str(), "r"), pclose);
  if (!pipe) {
    throw std::runtime_error("Could not launch sha256sum");
  }
  std::array<char, 256> buffer{};
  if (fgets(buffer.data(), static_cast<int>(buffer.size()), pipe.get()) ==
      nullptr) {
    throw std::runtime_error("sha256sum produced no output");
  }
  const std::string output(buffer.data());
  if (output.size() < 64) {
    throw std::runtime_error("sha256sum output is too short");
  }
  return output.substr(0, 64);
}

class Policy {
 public:
  explicit Policy(const std::filesystem::path& path) {
    if (!path.is_absolute() || !std::filesystem::is_regular_file(path)) {
      throw std::runtime_error(
          "Policy must be an existing absolute path: " + path.string());
    }
    const std::string actual_sha = sha256sum(path);
    if (actual_sha != kExpectedPolicySha256) {
      throw std::runtime_error("Policy SHA256 mismatch: " + actual_sha);
    }
    at::set_num_threads(1);
    at::set_num_interop_threads(1);
    module_ = torch::jit::load(path.string(), torch::kCPU);
    module_.eval();
    std::array<float, kObservations> zeros{};
    double ignored = 0.0;
    infer(zeros, &ignored);
  }

  std::array<float, kDofs> infer(
      const std::array<float, kObservations>& observation,
      double* inference_ms) {
    torch::InferenceMode guard;
    const auto input =
        torch::from_blob(
            const_cast<float*>(observation.data()),
            {1, static_cast<long>(kObservations)},
            torch::TensorOptions().dtype(torch::kFloat32)).clone();
    const auto started = Clock::now();
    const auto output = module_.forward({input}).toTensor();
    const auto stopped = Clock::now();
    *inference_ms =
        std::chrono::duration<double, std::milli>(stopped - started).count();
    if (output.dim() != 2 || output.size(0) != 1 ||
        output.size(1) != static_cast<long>(kDofs)) {
      throw std::runtime_error("Policy output is not [1, 29]");
    }
    if (!torch::isfinite(output).all().item<bool>()) {
      throw std::runtime_error("Policy output is non-finite");
    }
    const auto contiguous = output.to(torch::kCPU).contiguous();
    const float* data = contiguous.data_ptr<float>();
    std::array<float, kDofs> action{};
    for (std::size_t i = 0; i < kDofs; ++i) {
      action[i] = std::clamp(data[i], -kActionLimit, kActionLimit);
    }
    return action;
  }

 private:
  torch::jit::script::Module module_;
};

struct PolicyResult {
  std::array<float, kDofs> action{};
  std::array<float, kSingleObservations> current{};
  double inference_ms{0.0};
};

class ObservationHistory {
 public:
  ObservationHistory() {
    reset();
  }

  void reset() {
    history_.fill(0.0F);
    previous_action_.fill(0.0F);
  }

  PolicyResult infer(
      Policy& policy,
      const LowState& state,
      const std::array<float, kDofs>& mimic_joint_target) const {
    PolicyResult result;
    std::array<float, kMimicObservations> mimic{};
    mimic[2] = 0.8F;
    for (std::size_t i = 0; i < kDofs; ++i) {
      mimic[6 + i] = mimic_joint_target[i];
    }

    std::size_t current_index = 0;
    for (float value : mimic) {
      result.current[current_index++] = value;
    }
    const auto& gyro = state.imu_state().gyroscope();
    for (std::size_t i = 0; i < 3; ++i) {
      result.current[current_index++] = gyro[i] * 0.25F;
    }
    const auto& rpy = state.imu_state().rpy();
    result.current[current_index++] = rpy[0];
    result.current[current_index++] = rpy[1];
    for (std::size_t i = 0; i < kDofs; ++i) {
      result.current[current_index++] =
          state.motor_state()[i].q() - kDefault[i];
    }
    for (std::size_t i = 0; i < kDofs; ++i) {
      const bool ankle = i == 4 || i == 5 || i == 10 || i == 11;
      result.current[current_index++] =
          ankle ? 0.0F : state.motor_state()[i].dq() * 0.05F;
    }
    for (float value : previous_action_) {
      result.current[current_index++] = value;
    }
    if (current_index != kSingleObservations) {
      throw std::runtime_error("Current observation size mismatch");
    }

    std::array<float, kObservations> observation{};
    std::size_t observation_index = 0;
    for (float value : result.current) {
      observation[observation_index++] = value;
    }
    for (float value : history_) {
      observation[observation_index++] = value;
    }
    for (float value : mimic) {
      observation[observation_index++] = value;
    }
    if (observation_index != kObservations) {
      throw std::runtime_error("Full observation size mismatch");
    }
    for (float& value : observation) {
      if (!std::isfinite(value)) {
        throw std::runtime_error("Policy observation is non-finite");
      }
      value = std::clamp(value, -kObservationLimit, kObservationLimit);
    }
    result.action = policy.infer(observation, &result.inference_ms);
    return result;
  }

  void commit(
      const std::array<float, kSingleObservations>& current,
      const std::array<float, kDofs>& applied_action) {
    std::move(
        history_.begin() + kSingleObservations,
        history_.end(),
        history_.begin());
    std::copy(
        current.begin(), current.end(),
        history_.end() - kSingleObservations);
    previous_action_ = applied_action;
  }

 private:
  std::array<float, kSingleObservations * kHistory> history_{};
  std::array<float, kDofs> previous_action_{};
};

inline std::array<float, kDofs> hybrid_target(
    const std::array<float, kDofs>& action,
    const std::array<float, kDofs>& upper_target = kDefault) {
  std::array<float, kDofs> target = upper_target;
  for (std::size_t i = 0; i < kLegDofs; ++i) {
    target[i] = kDefault[i] + kActionScale * action[i];
  }
  for (std::size_t i = 0; i < kDofs; ++i) {
    target[i] = std::clamp(
        target[i],
        kLower[i] + kJointLimitMargin,
        kUpper[i] - kJointLimitMargin);
  }
  return target;
}

inline std::array<float, kDofs> target_as_action(
    const std::array<float, kDofs>& target) {
  std::array<float, kDofs> action{};
  for (std::size_t i = 0; i < kDofs; ++i) {
    action[i] = std::clamp(
        (target[i] - kDefault[i]) / kActionScale,
        -kActionLimit, kActionLimit);
  }
  return action;
}

}  // namespace twist2
