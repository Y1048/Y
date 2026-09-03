#include "twist2_common.hpp"

#include <iomanip>
#include <iostream>
#include <random>

namespace {

using namespace twist2;

const std::array<float, kDofs> kExpectedZeroOutput = {
    -0.265443921F, -0.0174197145F, -0.560025215F, 0.0567002371F,
    -0.32110545F, -0.0319861509F, -0.0811575279F, 0.0534459911F,
    0.637038887F, 0.166075647F, -0.0821521431F, -0.235395581F,
    -0.00885243434F, -0.151009321F, -0.0534484014F, -1.03016686F,
    -2.0F, -0.33219552F, -1.48948765F, -1.44641483F,
    0.250639051F, -0.682333171F, 0.2251468F, 1.49843061F,
    0.996458828F, -2.0F, 1.31394124F, -0.932840943F,
    0.474021733F};

const std::array<float, kDofs> kExpectedStateOne = {
    0.137962237F, -0.259444922F, -0.320698589F, -0.380329698F,
    0.195241615F, 0.136907354F, 0.0464386158F, 0.268913299F,
    0.260327846F, -0.253137648F, -0.0247358568F, -0.214160576F,
    -0.0669325739F, -0.0428565145F, -0.17442593F, -0.47357285F,
    -0.82274586F, 0.652642071F, 1.32004082F, -1.34474587F,
    0.230392233F, -0.545881093F, -0.731125772F, 0.110416941F,
    -0.266222388F, 0.968228579F, 0.85414964F, -0.874734819F,
    0.0962264463F};

const std::array<float, kDofs> kExpectedStateTwo = {
    0.191786826F, -0.210392684F, -0.16980207F, -0.23828803F,
    0.189905241F, 0.095167838F, -0.0973551944F, 0.366294384F,
    0.248432532F, -0.428735584F, -0.0569036379F, -0.136832044F,
    -0.0388497151F, 0.101000734F, 0.0702514276F, -0.659538269F,
    -0.503227413F, 0.607473254F, 1.57698655F, -1.07305098F,
    0.477123052F, -0.629343331F, -0.388359874F, 0.507778645F,
    -0.0930917636F, 1.73715889F, 1.0367192F, -0.607167184F,
    0.46661523F};

double maximum_difference(
    const std::array<float, kDofs>& actual,
    const std::array<float, kDofs>& expected) {
  double difference = 0.0;
  for (std::size_t i = 0; i < kDofs; ++i) {
    difference = std::max(
        difference,
        std::abs(static_cast<double>(actual[i] - expected[i])));
  }
  return difference;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc != 2) {
      std::cerr << "Usage: " << argv[0]
                << " /absolute/twist2_1017_20k_torchscript.pt\n";
      return 2;
    }
    Policy policy{std::filesystem::path(argv[1])};
    std::array<float, kObservations> input{};
    double inference_ms = 0.0;
    const auto zero_output = policy.infer(input, &inference_ms);
    const double zero_max_difference =
        maximum_difference(zero_output, kExpectedZeroOutput);
    if (zero_max_difference > 2.0e-5) {
      throw std::runtime_error("zero-input output mismatch");
    }

    ObservationHistory history;
    LowState state_one{};
    const std::array<float, 3> gyro_one = {0.1F, -0.2F, 0.3F};
    const std::array<float, 3> rpy_one = {0.05F, -0.06F, 0.1F};
    state_one.imu_state().gyroscope() = gyro_one;
    state_one.imu_state().rpy() = rpy_one;
    for (std::size_t i = 0; i < kDofs; ++i) {
      const float offset = static_cast<float>(
          static_cast<int>(i) - 14);
      state_one.motor_state()[i].q() =
          kDefault[i] + 0.01F * offset;
      state_one.motor_state()[i].dq() = 0.02F * offset;
    }
    const PolicyResult state_one_result =
        history.infer(policy, state_one, kDefault);
    const double state_one_difference = maximum_difference(
        state_one_result.action, kExpectedStateOne);
    if (state_one_difference > 2.0e-5) {
      throw std::runtime_error("first observation-contract mismatch");
    }
    const auto state_one_target =
        hybrid_target(state_one_result.action);
    history.commit(
        state_one_result.current,
        target_as_action(state_one_target));

    std::array<float, kDofs> captured_upper = kDefault;
    for (std::size_t i = kLegDofs; i < kDofs; ++i) {
      captured_upper[i] +=
          0.01F * static_cast<float>(static_cast<int>(i) - 20);
    }
    const auto captured_upper_target =
        hybrid_target(state_one_result.action, captured_upper);
    double captured_upper_difference = 0.0;
    for (std::size_t i = kLegDofs; i < kDofs; ++i) {
      captured_upper_difference = std::max(
          captured_upper_difference,
          std::abs(static_cast<double>(
              captured_upper_target[i] - captured_upper[i])));
    }
    if (captured_upper_difference > 1.0e-7) {
      throw std::runtime_error("captured upper-body hold mismatch");
    }

    const auto watchdog_now = Clock::time_point{} +
                              std::chrono::seconds(10);
    const auto stale_command =
        watchdog_now - std::chrono::milliseconds(100);
    const auto just_activated =
        watchdog_now - std::chrono::milliseconds(20);
    const auto established_activation =
        watchdog_now - std::chrono::milliseconds(300);
    if (command_watchdog_expired(
            watchdog_now,
            stale_command,
            just_activated,
            std::chrono::milliseconds(60),
            std::chrono::milliseconds(250))) {
      throw std::runtime_error(
          "command watchdog rejected the bounded handoff grace");
    }
    if (!command_watchdog_expired(
            watchdog_now,
            stale_command,
            established_activation,
            std::chrono::milliseconds(60),
            std::chrono::milliseconds(250))) {
      throw std::runtime_error(
          "command watchdog failed after the handoff grace");
    }

    constexpr float keyboard_lower = -0.5F;
    constexpr float keyboard_upper = 0.5F;
    float keyboard_command = 0.0F;
    keyboard_command = update_keyboard_joint_command(
        'q', 'q', 'a', 'z', keyboard_command,
        keyboard_lower, keyboard_upper, 0.02F);
    if (std::abs(keyboard_command - 0.02F) > 1.0e-7F) {
      throw std::runtime_error("keyboard plus command mismatch");
    }
    keyboard_command = update_keyboard_joint_command(
        'z', 'q', 'a', 'z', keyboard_command,
        keyboard_lower, keyboard_upper, 0.02F);
    if (std::abs(keyboard_command) > 1.0e-7F) {
      throw std::runtime_error("keyboard minus command mismatch");
    }
    keyboard_command = 0.3F;
    keyboard_command = update_keyboard_joint_command(
        'a', 'q', 'a', 'z', keyboard_command,
        keyboard_lower, keyboard_upper, 0.02F);
    if (std::abs(keyboard_command) > 1.0e-7F) {
      throw std::runtime_error("keyboard zero command mismatch");
    }
    for (int i = 0; i < 1000; ++i) {
      keyboard_command = update_keyboard_joint_command(
          'q', 'q', 'a', 'z', keyboard_command,
          keyboard_lower, keyboard_upper, 0.02F);
    }
    if (std::abs(keyboard_command - keyboard_upper) > 1.0e-7F) {
      throw std::runtime_error("keyboard upper limit mismatch");
    }
    const float keyboard_applied = rate_limited_target(
        0.0F, 1.0F, 9.0F * 0.08F, 0.02F);
    if (std::abs(keyboard_applied - 0.0144F) > 1.0e-7F) {
      throw std::runtime_error(
          "keyboard 9x target rate-limit mismatch");
    }

    LowState state_two{};
    const std::array<float, 3> gyro_two = {-0.05F, 0.07F, -0.09F};
    const std::array<float, 3> rpy_two = {-0.03F, 0.04F, -0.2F};
    state_two.imu_state().gyroscope() = gyro_two;
    state_two.imu_state().rpy() = rpy_two;
    for (std::size_t i = 0; i < kDofs; ++i) {
      const float offset = static_cast<float>(
          static_cast<int>(i) - 14);
      state_two.motor_state()[i].q() =
          kDefault[i] - 0.005F * offset;
      state_two.motor_state()[i].dq() = -0.01F * offset;
    }
    const PolicyResult state_two_result =
        history.infer(policy, state_two, kDefault);
    const double state_two_difference = maximum_difference(
        state_two_result.action, kExpectedStateTwo);
    if (state_two_difference > 2.0e-5) {
      throw std::runtime_error("history observation-contract mismatch");
    }

    std::mt19937 generator(20260730U);
    std::normal_distribution<float> distribution(0.0F, 1.0F);
    std::vector<double> timings;
    timings.reserve(100);
    double output_abs_max = 0.0;
    for (int iteration = 0; iteration < 100; ++iteration) {
      for (float& value : input) {
        value = distribution(generator);
      }
      const auto output = policy.infer(input, &inference_ms);
      timings.push_back(inference_ms);
      for (float value : output) {
        if (!std::isfinite(value)) {
          throw std::runtime_error("non-finite policy output");
        }
        output_abs_max = std::max(
            output_abs_max, std::abs(static_cast<double>(value)));
      }
    }
    const double mean =
        std::accumulate(timings.begin(), timings.end(), 0.0) /
        static_cast<double>(timings.size());
    std::cout << std::fixed << std::setprecision(9)
              << "{\n"
              << "  \"status\": \"completed\",\n"
              << "  \"policy_sha256\": \"" << kExpectedPolicySha256
              << "\",\n"
              << "  \"zero_output_max_abs_difference\": "
              << zero_max_difference << ",\n"
              << "  \"state_one_max_abs_difference\": "
              << state_one_difference << ",\n"
              << "  \"state_two_history_max_abs_difference\": "
              << state_two_difference << ",\n"
              << "  \"captured_upper_hold_max_abs_difference\": "
              << captured_upper_difference << ",\n"
              << "  \"handoff_watchdog_grace_test\": \"passed\",\n"
              << "  \"keyboard_left_arm_limits_test\": \"passed\",\n"
              << "  \"random_cases\": " << timings.size() << ",\n"
              << "  \"inference_ms_mean\": " << mean << ",\n"
              << "  \"inference_ms_p99\": "
              << percentile(timings, 0.99) << ",\n"
              << "  \"inference_ms_max\": "
              << *std::max_element(timings.begin(), timings.end()) << ",\n"
              << "  \"output_abs_max_after_clamp\": " << output_abs_max
              << "\n"
              << "}\n";
    return 0;
  } catch (const c10::Error& error) {
    std::cerr << "[fatal] Torch error: "
              << error.what_without_backtrace() << '\n';
  } catch (const std::exception& error) {
    std::cerr << "[fatal] " << error.what() << '\n';
  }
  return 1;
}
