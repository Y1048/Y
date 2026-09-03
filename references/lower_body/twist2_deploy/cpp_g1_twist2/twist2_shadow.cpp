#include "twist2_common.hpp"

#include <unitree/robot/channel/channel_subscriber.hpp>

#include <atomic>
#include <csignal>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <sstream>
#include <thread>

namespace {

using namespace twist2;

constexpr double kShadowSeconds = 10.0;
constexpr auto kStateTimeout = std::chrono::milliseconds(20);
constexpr float kRollPitchLimit = 0.35F;
constexpr float kVelocityLimit = 12.0F;
constexpr float kTemperatureLimit = 75.0F;
constexpr float kSoftTorqueFraction = 0.5F;

std::atomic<bool> gInterrupt{false};

void signal_handler(int) {
  gInterrupt.store(true);
}

struct Sample {
  double elapsed_s{0.0};
  double state_age_ms{0.0};
  double inference_ms{0.0};
  float roll{0.0F};
  float pitch{0.0F};
  std::array<float, kDofs> action{};
  std::array<float, kDofs> position{};
  std::array<float, kDofs> velocity{};
  std::array<float, kDofs> target{};
  std::array<float, kDofs> predicted_torque{};
};

class StateReader {
 public:
  explicit StateReader(const std::string& interface) {
    unitree::robot::ChannelFactory::Instance()->Init(0, interface);
    subscriber_.reset(
        new unitree::robot::ChannelSubscriber<LowState>("rt/lowstate"));
    subscriber_->InitChannel(
        std::bind(&StateReader::on_state, this, std::placeholders::_1), 1);
  }

  void wait() const {
    const auto deadline = Clock::now() + std::chrono::seconds(10);
    while (!has_state_.load() && Clock::now() < deadline) {
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    if (!has_state_.load()) {
      throw std::runtime_error("LowState timeout");
    }
  }

  LowState snapshot(double* age_ms) const {
    std::lock_guard<std::mutex> lock(mutex_);
    *age_ms = std::chrono::duration<double, std::milli>(
                  Clock::now() - received_)
                  .count();
    return state_;
  }

  void validate(const LowState& state, double age_ms) const {
    if (age_ms >
        std::chrono::duration<double, std::milli>(kStateTimeout).count()) {
      throw std::runtime_error("LowState stale");
    }
    if (state.mode_pr() != kExpectedModePr ||
        state.mode_machine() != kExpectedModeMachine) {
      throw std::runtime_error("unexpected G1 mode");
    }
    const auto& rpy = state.imu_state().rpy();
    if (!std::isfinite(rpy[0]) || !std::isfinite(rpy[1]) ||
        std::abs(rpy[0]) > kRollPitchLimit ||
        std::abs(rpy[1]) > kRollPitchLimit) {
      throw std::runtime_error("IMU roll/pitch limit");
    }
    for (std::size_t i = 0; i < kDofs; ++i) {
      const auto& motor = state.motor_state()[i];
      if (!std::isfinite(motor.q()) || !std::isfinite(motor.dq()) ||
          !std::isfinite(motor.tau_est())) {
        throw std::runtime_error("non-finite motor state");
      }
      if (std::abs(motor.dq()) > kVelocityLimit) {
        throw std::runtime_error("joint velocity limit");
      }
      if (motor.q() < kLower[i] + kJointLimitMargin ||
          motor.q() > kUpper[i] - kJointLimitMargin) {
        throw std::runtime_error("joint position soft limit");
      }
      if (static_cast<float>(motor.temperature()[0]) > kTemperatureLimit ||
          motor.motorstate() != 0U) {
        throw std::runtime_error("motor temperature/fault");
      }
    }
  }

 private:
  void on_state(const void* message) {
    const auto* incoming = static_cast<const LowState*>(message);
    if (!valid_crc(*incoming)) {
      ++crc_failures_;
      return;
    }
    {
      std::lock_guard<std::mutex> lock(mutex_);
      state_ = *incoming;
      received_ = Clock::now();
    }
    has_state_.store(true);
  }

  mutable std::mutex mutex_;
  LowState state_{};
  Clock::time_point received_{};
  std::atomic<bool> has_state_{false};
  std::atomic<std::uint64_t> crc_failures_{0};
  unitree::robot::ChannelSubscriberPtr<LowState> subscriber_;
};

std::filesystem::path write_csv(const std::vector<Sample>& samples) {
  const auto timestamp = std::chrono::system_clock::to_time_t(
      std::chrono::system_clock::now());
  std::ostringstream name;
  name << "g1_twist2_shadow_" << timestamp << ".csv";
  const auto path = std::filesystem::current_path() / name.str();
  std::ofstream stream(path);
  if (!stream) {
    throw std::runtime_error("Could not create CSV");
  }
  stream << "elapsed_s,state_age_ms,inference_ms,roll_rad,pitch_rad";
  for (std::size_t i = 0; i < kDofs; ++i) {
    stream << ",action_" << i << ",q_" << i << ",dq_" << i
           << ",target_" << i << ",predicted_tau_" << i;
  }
  stream << '\n' << std::setprecision(9);
  for (const Sample& sample : samples) {
    stream << sample.elapsed_s << ',' << sample.state_age_ms << ','
           << sample.inference_ms << ',' << sample.roll << ','
           << sample.pitch;
    for (std::size_t i = 0; i < kDofs; ++i) {
      stream << ',' << sample.action[i] << ',' << sample.position[i] << ','
             << sample.velocity[i] << ',' << sample.target[i] << ','
             << sample.predicted_torque[i];
    }
    stream << '\n';
  }
  return path;
}

}  // namespace

int main(int argc, char** argv) {
  std::signal(SIGINT, signal_handler);
  std::signal(SIGTERM, signal_handler);
  try {
    if (argc != 3) {
      std::cerr << "Usage: " << argv[0]
                << " eth0 /absolute/twist2_1017_20k_torchscript.pt\n";
      return 2;
    }
    const std::filesystem::path policy_path(argv[2]);
    Policy policy{policy_path};
    StateReader reader(argv[1]);
    reader.wait();
    double capture_state_age_ms = 0.0;
    const LowState capture_state = reader.snapshot(&capture_state_age_ms);
    reader.validate(capture_state, capture_state_age_ms);
    std::array<float, kDofs> capture_target{};
    std::array<float, kDofs> mimic_target = kDefault;
    for (std::size_t i = 0; i < kDofs; ++i) {
      capture_target[i] = capture_state.motor_state()[i].q();
      if (i >= kLegDofs) {
        mimic_target[i] = capture_target[i];
      }
    }

    std::cout
        << "=== G1 TWIST2 READ-ONLY SHADOW ===\n"
        << "policy_sha256: " << kExpectedPolicySha256 << '\n'
        << "duration: " << kShadowSeconds << " s at 50 Hz\n"
        << "control preview: TWIST2 legs; captured waist and arms\n"
        << "This executable contains no LowCmd publisher or MotionSwitcher.\n";

    ObservationHistory history;
    const auto started = Clock::now();
    auto next = started;
    std::vector<Sample> samples;
    std::vector<double> inference_ms;
    double action_abs_max = 0.0;
    double action_delta_abs_max = 0.0;
    double target_error_abs_max = 0.0;
    double predicted_torque_ratio_max = 0.0;
    std::array<float, kDofs> previous_action{};

    while (!gInterrupt.load()) {
      const auto now = Clock::now();
      const double elapsed =
          std::chrono::duration<double>(now - started).count();
      if (elapsed >= kShadowSeconds) {
        break;
      }
      if (now < next) {
        std::this_thread::sleep_until(next);
      }
      double state_age_ms = 0.0;
      const LowState state = reader.snapshot(&state_age_ms);
      reader.validate(state, state_age_ms);
      const PolicyResult result =
          history.infer(policy, state, mimic_target);
      const auto target =
          hybrid_target(result.action, capture_target);
      const auto applied = target_as_action(target);
      history.commit(result.current, applied);

      Sample sample;
      sample.elapsed_s = elapsed;
      sample.state_age_ms = state_age_ms;
      sample.inference_ms = result.inference_ms;
      sample.roll = state.imu_state().rpy()[0];
      sample.pitch = state.imu_state().rpy()[1];
      sample.action = result.action;
      sample.target = target;
      for (std::size_t i = 0; i < kDofs; ++i) {
        const auto& motor = state.motor_state()[i];
        sample.position[i] = motor.q();
        sample.velocity[i] = motor.dq();
        sample.predicted_torque[i] =
            kKp[i] * (target[i] - motor.q()) - kKd[i] * motor.dq();
        if (i < kLegDofs) {
          action_abs_max = std::max(
              action_abs_max,
              std::abs(static_cast<double>(result.action[i])));
          action_delta_abs_max = std::max(
              action_delta_abs_max,
              std::abs(static_cast<double>(
                  result.action[i] - previous_action[i])));
        }
        target_error_abs_max = std::max(
            target_error_abs_max,
            std::abs(static_cast<double>(target[i] - motor.q())));
        predicted_torque_ratio_max = std::max(
            predicted_torque_ratio_max,
            std::abs(static_cast<double>(sample.predicted_torque[i])) /
                static_cast<double>(kTorqueLimit[i]));
      }
      previous_action = result.action;
      inference_ms.push_back(result.inference_ms);
      samples.push_back(sample);
      if (samples.size() % 25 == 0) {
        std::cout << "\r[shadow] " << std::fixed << std::setprecision(2)
                  << elapsed << " s inference=" << result.inference_ms
                  << " ms action_max=" << action_abs_max << std::flush;
      }
      next += kPolicyPeriod;
      if (next < Clock::now() - kPolicyPeriod) {
        throw std::runtime_error("50-Hz shadow loop missed a full period");
      }
    }

    std::cout << '\n';
    if (samples.empty()) {
      throw std::runtime_error("No shadow samples");
    }
    const auto csv = write_csv(samples);
    const double inference_mean =
        std::accumulate(inference_ms.begin(), inference_ms.end(), 0.0) /
        static_cast<double>(inference_ms.size());
    std::cout << std::fixed << std::setprecision(6)
              << "{\n"
              << "  \"status\": \"completed\",\n"
              << "  \"policy_sha256\": \"" << kExpectedPolicySha256
              << "\",\n"
              << "  \"samples\": " << samples.size() << ",\n"
              << "  \"inference_ms_mean\": " << inference_mean << ",\n"
              << "  \"inference_ms_p99\": "
              << percentile(inference_ms, 0.99) << ",\n"
              << "  \"inference_ms_max\": "
              << *std::max_element(
                     inference_ms.begin(), inference_ms.end())
              << ",\n"
              << "  \"leg_action_abs_max\": " << action_abs_max << ",\n"
              << "  \"leg_action_delta_abs_max\": "
              << action_delta_abs_max << ",\n"
              << "  \"target_error_abs_max_rad\": "
              << target_error_abs_max << ",\n"
              << "  \"predicted_torque_ratio_max\": "
              << predicted_torque_ratio_max << ",\n"
              << "  \"csv_path\": \"" << csv.string() << "\"\n"
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
