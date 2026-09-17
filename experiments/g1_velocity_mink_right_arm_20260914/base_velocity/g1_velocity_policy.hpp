#pragma once

#include "twist2_common.hpp"

#include <array>
#include <cstring>

namespace twist2 {

constexpr std::size_t kVelocityObservations = 47;
constexpr float kVelocityActionScale = 0.25F;
constexpr char kVelocityPolicySha256[] =
    "cf668f75b90d1abf73d2b87612a6e76bccc61ff7e083b63582d3f6aaa3c1759d";

const std::array<float, kDofs> kVelocityDefault = {
    -0.1F, 0, 0, 0.3F, -0.2F, 0,
    -0.1F, 0, 0, 0.3F, -0.2F, 0,
    0, 0, 0,
    0.35F, 0.18F, 0, 0.87F, 0, 0, 0,
    0.35F, -0.18F, 0, 0.87F, 0, 0, 0};

class VelocityCommand {
 public:
  static bool IsKey(char key) {
    switch (key) {
      case '8': case '2': case '4': case '6':
      case '7': case '9': case '5': case '0': case ' ':
        return true;
      default:
        return false;
    }
  }

  static bool HandleKey(char key) {
    std::array<float, 3> next{};
    bool motion = true;
    switch (key) {
      case '8': next = {0.40F, 0.0F, 0.0F}; break;
      case '2': next = {-0.20F, 0.0F, 0.0F}; break;
      case '4': next = {0.0F, 0.20F, 0.0F}; break;
      case '6': next = {0.0F, -0.20F, 0.0F}; break;
      case '7': next = {0.0F, 0.0F, 0.20F}; break;
      case '9': next = {0.0F, 0.0F, -0.20F}; break;
      case '5': case '0': case ' ': next = {0.0F, 0.0F, 0.0F}; break;
      default: motion = false; break;
    }
    if (!motion) {
      return false;
    }
    target_ = next;
    return true;
  }

  static std::array<float, 3> Command() {
    constexpr std::array<float, 3> kAccelerationStep{
        0.005F, 0.004F, 0.005F};
    constexpr std::array<float, 3> kStopStep{0.020F, 0.020F, 0.020F};
    const auto& maximum_step = MotionRequested() ? kAccelerationStep : kStopStep;
    for (std::size_t i = 0; i < command_.size(); ++i) {
      command_[i] += std::clamp(
          target_[i] - command_[i], -maximum_step[i], maximum_step[i]);
    }
    return command_;
  }

  static bool MotionRequested() {
    constexpr float kEpsilon = 1.0e-6F;
    return std::abs(target_[0]) > kEpsilon ||
           std::abs(target_[1]) > kEpsilon ||
           std::abs(target_[2]) > kEpsilon;
  }

  static void Stop() {
    target_.fill(0.0F);
  }

  static void Reset() {
    target_.fill(0.0F);
    command_.fill(0.0F);
  }

 private:
  inline static std::array<float, 3> target_{};
  inline static std::array<float, 3> command_{};
};

class GaitPhaseClock {
 public:
  static constexpr std::size_t kCycleSteps = 40;
  static constexpr std::size_t kStopSettleCycles = 2;

  void Reset() {
    step_ = 0;
#ifdef G1_VELOCITY_CONTINUOUS_GAIT
    running_ = true;
#else
    running_ = false;
#endif
    zero_command_cycles_ = 0;
  }

  float Next(bool motion_requested, bool command_is_zero) {
#ifdef G1_VELOCITY_CONTINUOUS_GAIT
    (void)motion_requested;
    (void)command_is_zero;
    running_ = true;
    const float phase = static_cast<float>(step_) /
                        static_cast<float>(kCycleSteps);
    step_ = (step_ + 1U) % kCycleSteps;
    return phase;
#else
    if (motion_requested) {
      running_ = true;
      zero_command_cycles_ = 0;
    }
    if (running_ && !motion_requested && command_is_zero && step_ == 0U &&
        zero_command_cycles_ >= kStopSettleCycles) {
      running_ = false;
    }
    const float phase = static_cast<float>(step_) /
                        static_cast<float>(kCycleSteps);
    if (running_) {
      step_ = (step_ + 1U) % kCycleSteps;
      if (!motion_requested && command_is_zero && step_ == 0U) {
        ++zero_command_cycles_;
      }
    }
    return phase;
#endif
  }

  bool running() const {
    return running_;
  }

  std::size_t zero_command_cycles() const {
    return zero_command_cycles_;
  }

 private:
  std::size_t step_{0};
  bool running_{false};
  std::size_t zero_command_cycles_{0};
};

class VelocityPolicy {
 public:
  explicit VelocityPolicy(const std::filesystem::path& path) {
    if (!path.is_absolute() || !std::filesystem::is_regular_file(path)) {
      throw std::runtime_error(
          "Policy must be an existing absolute path: " + path.string());
    }
    const std::string actual_sha = sha256sum(path);
    if (actual_sha != kVelocityPolicySha256) {
      throw std::runtime_error("Velocity policy SHA256 mismatch: " + actual_sha);
    }
    configure_torch_threads_once();
    module_ = torch::jit::load(path.string(), torch::kCPU);
    module_.eval();
    std::array<float, kVelocityObservations> zeros{};
    double ignored = 0.0;
    Infer(zeros, &ignored);
  }

  std::array<float, kLegDofs> Infer(
      const std::array<float, kVelocityObservations>& observation,
      double* inference_ms) {
    torch::InferenceMode guard;
    const auto input = torch::from_blob(
        const_cast<float*>(observation.data()),
        {1, static_cast<long>(kVelocityObservations)},
        torch::TensorOptions().dtype(torch::kFloat32)).clone();
    const auto started = Clock::now();
    const auto output = module_.forward({input}).toTensor();
    const auto stopped = Clock::now();
    *inference_ms = std::chrono::duration<double, std::milli>(
        stopped - started).count();
    if (output.dim() != 2 || output.size(0) != 1 ||
        output.size(1) != static_cast<long>(kLegDofs) ||
        !torch::isfinite(output).all().item<bool>()) {
      throw std::runtime_error("Velocity policy output must be finite [1, 12]");
    }
    const auto contiguous = output.to(torch::kCPU).contiguous();
    const float* data = contiguous.data_ptr<float>();
    std::array<float, kLegDofs> action{};
    for (std::size_t i = 0; i < kLegDofs; ++i) {
      action[i] = std::clamp(data[i], -2.0F, 2.0F);
    }
    return action;
  }

 private:
  torch::jit::script::Module module_;
};

struct VelocityPolicyResult {
  std::array<float, kDofs> action{};
  std::array<float, kSingleObservations> current{};
  std::array<float, 3> command{};
  float gait_phase{0.0F};
  bool gait_clock_running{false};
  double inference_ms{0.0};
};

class VelocityObservationHistory {
 public:
  void reset() {
    previous_action_.fill(0.0F);
    phase_clock_.Reset();
    VelocityCommand::Reset();
  }

  VelocityPolicyResult infer(
      VelocityPolicy& policy,
      const LowState& state,
      const std::array<float, kDofs>&) {
    VelocityPolicyResult result;
    std::array<float, kVelocityObservations> observation{};
    const auto& gyro = state.imu_state().gyroscope();
    for (std::size_t i = 0; i < 3; ++i) {
      observation[i] = gyro[i] * 0.25F;
    }

    const auto& quaternion = state.imu_state().quaternion();
    const float w = quaternion[0];
    const float x = quaternion[1];
    const float y = quaternion[2];
    const float z = quaternion[3];
    observation[3] = -2.0F * (x * z - w * y);
    observation[4] = -2.0F * (y * z + w * x);
    observation[5] = -(1.0F - 2.0F * (x * x + y * y));

    const auto command = VelocityCommand::Command();
    result.command = command;
    observation[6] = command[0] * 2.0F;
    observation[7] = command[1] * 2.0F;
    observation[8] = command[2] * 0.25F;
    for (std::size_t i = 0; i < kLegDofs; ++i) {
      observation[9 + i] = state.motor_state()[i].q() - kVelocityDefault[i];
      observation[21 + i] = state.motor_state()[i].dq() * 0.05F;
      observation[33 + i] = previous_action_[i];
    }
    constexpr float kCommandZeroEpsilon = 1.0e-5F;
    const bool command_is_zero =
        std::abs(command[0]) <= kCommandZeroEpsilon &&
        std::abs(command[1]) <= kCommandZeroEpsilon &&
        std::abs(command[2]) <= kCommandZeroEpsilon;
    const float phase = phase_clock_.Next(
        VelocityCommand::MotionRequested(), command_is_zero);
    result.gait_phase = phase;
    result.gait_clock_running = phase_clock_.running();
    observation[45] = std::sin(2.0F * static_cast<float>(M_PI) * phase);
    observation[46] = std::cos(2.0F * static_cast<float>(M_PI) * phase);
    for (float& value : observation) {
      if (!std::isfinite(value)) {
        throw std::runtime_error("Velocity observation is non-finite");
      }
      value = std::clamp(value, -100.0F, 100.0F);
    }
    const auto leg_action = policy.Infer(observation, &result.inference_ms);
    std::copy(leg_action.begin(), leg_action.end(), result.action.begin());
    return result;
  }

  void commit(
      const std::array<float, kSingleObservations>&,
      const std::array<float, kDofs>& applied_action) {
    std::copy_n(applied_action.begin(), kLegDofs, previous_action_.begin());
  }

 private:
  std::array<float, kLegDofs> previous_action_{};
  GaitPhaseClock phase_clock_{};
};

inline std::array<float, kDofs> velocity_hybrid_target(
    const std::array<float, kDofs>& action,
    const std::array<float, kDofs>& upper_target = kVelocityDefault) {
  std::array<float, kDofs> target = upper_target;
  for (std::size_t i = 0; i < kLegDofs; ++i) {
    target[i] = kVelocityDefault[i] + kVelocityActionScale * action[i];
  }
  for (std::size_t i = 0; i < kDofs; ++i) {
    target[i] = std::clamp(
        target[i], kLower[i] + kJointLimitMargin,
        kUpper[i] - kJointLimitMargin);
  }
  return target;
}

inline std::array<float, kDofs> velocity_target_as_action(
    const std::array<float, kDofs>& target) {
  std::array<float, kDofs> action{};
  for (std::size_t i = 0; i < kLegDofs; ++i) {
    action[i] = std::clamp(
        (target[i] - kVelocityDefault[i]) / kVelocityActionScale,
        -2.0F, 2.0F);
  }
  return action;
}

}  // namespace twist2
