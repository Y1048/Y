// Native VR draft: Linux SDK build and hardware validation NOT performed.
#include "twist2_common.hpp"
#include "native_vr_udp.hpp"
#include "native_vr_invocation.hpp"
#include "native_command_limits.hpp"
#include "native_state_tick.hpp"
#include "native_state_audit.hpp"
#include "native_stop_audit.hpp"
#include "native_snapshot_freshness.hpp"
#ifdef TWIST2_SPLIT_CANDIDATE
#include "split_vr_adapter_study.hpp"
#include "native_relative_reference.hpp"
#endif
#include <functional>

#include <unitree/common/thread/thread.hpp>
#include <unitree/robot/b2/motion_switcher/motion_switcher_client.hpp>
#include <unitree/robot/channel/channel_publisher.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>

#include <atomic>
#include <cerrno>
#include <cctype>
#include <csignal>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <poll.h>
#include <sstream>
#include <termios.h>
#include <thread>
#include <unistd.h>

namespace {

using namespace twist2;

constexpr auto kLowCmdPeriod = std::chrono::microseconds(2000);
constexpr auto kStateTimeout = std::chrono::milliseconds(20);
constexpr auto kCommandTimeout = std::chrono::milliseconds(60);
constexpr auto kHandoffCommandGrace = std::chrono::milliseconds(250);
constexpr float kSoftTorqueFraction = 0.5F;
constexpr float kLegTargetRate = 2.0F;
constexpr float kUpperTargetRate = 0.8F;
constexpr float kRollLimit = 0.35F;
constexpr float kPitchLimit = 0.35F;
constexpr float kArmingRollLimit = 0.15F;
constexpr float kArmingPitchLimit = 0.15F;
constexpr float kPreflightVelocityLimit = 0.10F;
constexpr float kVelocityLimit = 12.0F;
constexpr float kTemperatureLimit = 75.0F;
constexpr float kMaxLegHomeError = 0.40F;
constexpr double kCaptureSeconds = 1.0;
constexpr double kBlendSeconds = 4.0;
constexpr double kDefaultPolicySeconds = 2.0;
constexpr double kMinimumPolicySeconds = 2.0;
constexpr double kMaximumPolicySeconds = 20.0;
constexpr double kKeyboardPolicySeconds = 20.0;
constexpr double kDampingSeconds = 3.0;
constexpr double kArmHoldPolicySeconds = 10.0;
constexpr double kArmMotionSeconds = 10.0;
constexpr float kInitialRightShoulderForwardDegrees = 30.0F;
constexpr float kKeyboardIncrement = 0.02F;
constexpr float kKeyboardBaseTargetRate = 0.08F;
constexpr float kKeyboardTrackingErrorLimit = 0.25F;
constexpr float kKeyboardMeasuredVelocityLimit = 1.5F;
constexpr float kDegreesToRadians = 0.01745329251994329577F;
constexpr float kForwardShoulderPitchSign = -1.0F;
constexpr std::size_t kRightShoulderPitch = 22;
constexpr std::size_t kRightArmBegin = 22;
constexpr std::size_t kRightArmDofs = 7;
constexpr std::array<char, kRightArmDofs> kKeyboardPlusKeys = {
    'q', 'w', 'e', 'r', 't', 'y', 'u'};
constexpr std::array<char, kRightArmDofs> kKeyboardZeroKeys = {
    'a', 's', 'd', 'f', 'g', 'h', 'j'};
constexpr std::array<char, kRightArmDofs> kKeyboardMinusKeys = {
    'z', 'x', 'c', 'v', 'b', 'n', 'm'};
constexpr std::array<const char*, kRightArmDofs> kRightArmNames = {
    "shoulder_pitch", "shoulder_roll", "shoulder_yaw", "elbow",
    "wrist_roll", "wrist_pitch", "wrist_yaw"};
constexpr std::uint16_t kR1 = 0x0001U;
constexpr std::uint16_t kSelect = 0x0008U;
constexpr std::uint16_t kB = 0x0200U;

std::atomic<bool> gInterrupt{false};

void signal_handler(int) {
  gInterrupt.store(true);
}

struct Desired {
  Clock::time_point created{};
  std::array<float, kDofs> target{};
  std::array<float, kDofs> feedforward{};
};

// Latest completed SDK write attempt, not a motor acknowledgement or full 500-Hz trace.
struct WriterAudit {
  std::uint64_t sequence{0};
  bool sdk_accepted{false};
  bool damping{false};
  Clock::time_point completed{};
  std::uint32_t state_tick{0};
  std::array<float,kDofs> desired{},target{},position{},velocity{},kp{},kd{},feedforward{};
};

struct Sample {
  double elapsed_s{0.0};
  std::string phase;
  float alpha{0.0F};
  float arm_alpha{0.0F};
  double state_age_ms{0.0};
  double inference_ms{0.0};
  float roll{0.0F};
  float pitch{0.0F};
  std::array<float, kDofs> action{};
  std::array<float, kDofs> position{};
  std::array<float, kDofs> velocity{};
  std::array<float, kDofs> estimated_torque{};
  std::array<float, kDofs> target{};
  std::array<float, kDofs> mimic_target{};
  WriterAudit writer;
  double writer_age_ms{-1.0};
  NativeStateAudit state_audit;
};

class Controller {
 public:
  WriterAudit writer_audit() const {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    return writer_audit_;
  }
  explicit Controller(const std::string& interface) {
    // The keyboard run is 305 active seconds plus a 3-second damping tail.
    // Reserve before any handoff so the 500-Hz statistics path does not
    // allocate during the bounded run.
    intervals_ms_.reserve(200000);
    unitree::robot::ChannelFactory::Instance()->Init(0, interface);
    switcher_ =
        std::make_unique<unitree::robot::b2::MotionSwitcherClient>();
    publisher_.reset(
        new unitree::robot::ChannelPublisher<LowCmd>("rt/lowcmd"));
    subscriber_.reset(
        new unitree::robot::ChannelSubscriber<LowState>("rt/lowstate"));
    publisher_->InitChannel();
    subscriber_->InitChannel(
        std::bind(&Controller::on_state, this, std::placeholders::_1), 1);
    switcher_->SetTimeout(5.0F);
    switcher_->Init();
  }

  void wait_for_state() {
    const auto deadline = Clock::now() + std::chrono::seconds(10);
    while (!has_state_.load() && Clock::now() < deadline) {
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    if (!has_state_.load()) {
      throw std::runtime_error("LowState timeout");
    }
  }

  LowState snapshot(double* age_ms = nullptr, Clock::time_point* received = nullptr) const {
    std::lock_guard<std::mutex> lock(state_mutex_);
    if(received) *received=state_received_;
    if (age_ms != nullptr) {
      *age_ms = std::chrono::duration<double, std::milli>(
                    Clock::now() - state_received_)
                    .count();
    }
    return state_;
  }

  void validate_state(
      const LowState& state,
      bool require_deadman,
      float velocity_limit,
      bool arming, Clock::time_point received) const {
    if (!NativeSnapshotFresh(received,Clock::now(),kStateTimeout)) {
      throw std::runtime_error("LowState stale");
    }
    if (state.mode_pr() != kExpectedModePr ||
        state.mode_machine() != kExpectedModeMachine) {
      throw std::runtime_error("unexpected mode");
    }
    const auto& rpy = state.imu_state().rpy();
    const float roll_limit = arming ? kArmingRollLimit : kRollLimit;
    const float pitch_limit = arming ? kArmingPitchLimit : kPitchLimit;
    if (!std::isfinite(rpy[0]) || !std::isfinite(rpy[1]) ||
        std::abs(rpy[0]) > roll_limit ||
        std::abs(rpy[1]) > pitch_limit) {
      throw std::runtime_error("IMU roll/pitch limit");
    }
    if (require_deadman) {
      const std::uint16_t buttons = remote_buttons(state);
      if ((buttons & kR1) == 0U) {
        throw std::runtime_error("R1 deadman released");
      }
      if ((buttons & (kSelect | kB)) != 0U) {
        throw std::runtime_error("Select/B emergency stop");
      }
    }
    for (std::size_t i = 0; i < kDofs; ++i) {
      const auto& motor = state.motor_state()[i];
      if (!std::isfinite(motor.q()) || !std::isfinite(motor.dq()) ||
          !std::isfinite(motor.tau_est())) {
        throw std::runtime_error("non-finite motor state");
      }
      if (std::abs(motor.dq()) > velocity_limit) {
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

  void wait_for_preflight() {
    std::cout
        << "[preflight] AI standing must be active; hold R1 continuously; "
           "waiting for 1 s stable\n";
    const auto deadline = Clock::now() + std::chrono::seconds(60);
    auto stable_since = Clock::time_point{};
    std::string last_reason;
    while (Clock::now() < deadline && !gInterrupt.load()) {
      Clock::time_point received;
      const LowState state = snapshot(nullptr,&received);
      bool valid = true;
      try {
        validate_state(state, true, kPreflightVelocityLimit, true, received);
        float maximum_error = 0.0F;
        for (std::size_t i = 0; i < kLegDofs; ++i) {
          maximum_error = std::max(
              maximum_error,
              std::abs(state.motor_state()[i].q() - kDefault[i]));
        }
        if (maximum_error > kMaxLegHomeError) {
          throw std::runtime_error("leg pose too far from TWIST2 home");
        }
      } catch (const std::exception& error) {
        valid = false;
        last_reason = error.what();
      }
      if (!valid) {
        stable_since = Clock::time_point{};
      } else if (stable_since == Clock::time_point{}) {
        stable_since = Clock::now();
      } else if (Clock::now() - stable_since >= std::chrono::seconds(1)) {
        capture(state);
        std::cout << "[preflight] passed\n";
        return;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    throw std::runtime_error(
        "Preflight did not remain safe for 1 s; last=" + last_reason);
  }

  void capture(const LowState& state) {
    for (std::size_t i = 0; i < kDofs; ++i) {
      capture_q_[i] = state.motor_state()[i].q();
      const float limit = kTorqueLimit[i] * kSoftTorqueFraction;
      capture_tau_[i] =
          std::clamp(state.motor_state()[i].tau_est(), -limit, limit);
      last_target_[i] = capture_q_[i];
    }
    set_capture_desired();
  }

  const std::array<float, kDofs>& capture_q() const {
    return capture_q_;
  }

  const std::array<float, kDofs>& capture_tau() const {
    return capture_tau_;
  }

  void set_capture_desired() {
    Desired desired;
    desired.created = Clock::now();
    desired.target = capture_q_;
    desired.feedforward = capture_tau_;
    set_desired(desired);
  }

  void set_desired(const Desired& desired) {
    std::lock_guard<std::mutex> lock(desired_mutex_);
    desired_ = desired;
    has_desired_ = true;
  }

  void set_vr_watchdog(std::function<std::string()> check) { vr_watchdog_ = std::move(check); }

  void start_writer() {
    writer_ = unitree::common::CreateRecurrentThreadEx(
        "g1_twist2_500hz",
        UT_CPU_ID_NONE,
        2000,
        &Controller::write_cycle,
        this);
  }

  void handoff_and_activate() {
    std::string form;
    std::string name;
    const std::int32_t check = switcher_->CheckMode(form, name);
    if (check != 0 || name != "ai") {
      throw std::runtime_error(
          "Expected active motion service 'ai', got result=" +
          std::to_string(check) + " name='" + name + "'");
    }
    std::cout << "[handoff] releasing motion service: " << name << '\n';
    set_capture_desired();
    std::int32_t released;
    try { released = switcher_->ReleaseMode(); }
    catch (...) {
      std::cerr << "[handoff UNKNOWN] ReleaseMode threw; no activation or automatic mode retry. Robot state must be inspected.\n";
      throw;
    }
    if (released != 0) {
      std::cerr << "[handoff UNKNOWN] ReleaseMode did not confirm success; do not assume AI still owns control.\n";
      throw std::runtime_error(
          "MotionSwitcher ReleaseMode failed: " +
          std::to_string(released));
    }
    // desired_ already contains the freshly captured hold command.  Make the
    // 500-Hz writer active immediately after a successful release; do not put
    // another potentially throwing operation in this handoff gap.
    activated_at_ = Clock::now();
    active_.store(true);
  }

  void latch(const std::string& reason, bool planned = false,
             const LowState* context = nullptr, double snapshot_age_ms = -1) {
    std::lock_guard<std::recursive_mutex> command_lock(command_mutex_);
    bool expected = false;
    if (damping_.compare_exchange_strong(expected, true)) {
      std::lock_guard<std::mutex> lock(reason_mutex_);
      reason_ = reason;
      planned_.store(planned);
      // Damping is already latched. Only copy bounded diagnostics here; no file I/O.
      if (context) stop_audit_.CaptureFirst(*context, true, snapshot_age_ms);
      else {
        double age=0;
        const auto latest=snapshot(&age);
        stop_audit_.CaptureFirst(latest, false, age);
      }
    }
  }

  bool damping() const {
    return damping_.load();
  }

#ifdef TWIST2_SPLIT_CANDIDATE
  WriterAudit capture_relative_reference() {
    std::lock_guard<std::recursive_mutex> lock(command_mutex_);
    if(!active_.load()||damping_.load())throw std::runtime_error("relative owner inactive");
    Clock::time_point received;
    const auto state=snapshot(nullptr,&received);
    validate_state(state,true,kVelocityLimit,false,received);
    const auto audit=writer_audit();
    if(!audit.sequence||!audit.sdk_accepted||audit.damping||
       !NativeSnapshotFresh(audit.completed,Clock::now(),kStateTimeout))
      throw std::runtime_error("relative writer reference unavailable");
    return audit;
  }

  void commit_relative_desired(const Desired& desired,const std::optional<WriterAudit>& initial) {
    std::lock_guard<std::recursive_mutex> lock(command_mutex_);
    const auto latest=capture_relative_reference();
    if(initial&&!NativeRelativeReferenceMatches(latest,*initial,desired))
      throw std::runtime_error("relative first command reference changed or discontinuous");
    set_desired(desired);
  }
#endif

  void write_stop_audit(const std::filesystem::path& csv_path) const {
    std::lock_guard<std::mutex> lock(reason_mutex_);
    std::ofstream out(csv_path.string()+".stop.csv");
    if(!out)throw std::runtime_error("Could not create stop audit CSV");
    out << std::setprecision(9);
    stop_audit_.Csv(out, reason_, planned_.load());
    if(!out)throw std::runtime_error("Could not write stop audit CSV");
  }

  std::string reason() const {
    std::lock_guard<std::mutex> lock(reason_mutex_);
    return reason_;
  }

  void finish() {
    std::cout << "[damping] sending mandatory tail for 3 s\n";
    std::this_thread::sleep_for(
        std::chrono::duration<double>(kDampingSeconds));
    if (!planned_.load() && !gInterrupt.load()) {
      std::cout << "[damping] safety stop: " << reason()
                << "; press Ctrl+C to stop continuous damping\n";
      while (!gInterrupt.load()) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
      }
    }
    active_.store(false);
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }

  void print_stats() const {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    const double span =
        std::chrono::duration<double>(last_write_ - first_write_).count();
    const double rate =
        write_count_ > 1 && span > 0.0
            ? (write_count_ - 1) / span
            : 0.0;
    const double mean =
        intervals_ms_.empty()
            ? 0.0
            : std::accumulate(
                  intervals_ms_.begin(), intervals_ms_.end(), 0.0) /
                  static_cast<double>(intervals_ms_.size());
    std::cout << std::fixed << std::setprecision(6)
              << "  \"lowcmd_count\": " << write_count_ << ",\n"
              << "  \"lowcmd_rate_hz\": " << rate << ",\n"
              << "  \"interval_ms_mean\": " << mean << ",\n"
              << "  \"interval_ms_p95\": "
              << percentile(intervals_ms_, 0.95) << ",\n"
              << "  \"interval_ms_p99\": "
              << percentile(intervals_ms_, 0.99) << ",\n"
              << "  \"interval_ms_max\": "
              << (intervals_ms_.empty()
                      ? 0.0
                      : *std::max_element(
                            intervals_ms_.begin(), intervals_ms_.end()))
              << ",\n"
              << "  \"handler_ms_max\": " << max_handler_ms_ << ",\n"
              << "  \"predicted_torque_abs_max_nm\": "
              << predicted_torque_abs_max_ << ",\n"
              << "  \"torque_limiter_joint_ratio\": "
              << (active_joint_commands_ == 0
                      ? 0.0
                      : static_cast<double>(torque_limited_commands_) /
                            static_cast<double>(active_joint_commands_))
              << '\n';
  }

 private:
  void on_state(const void* message) {
    const auto* incoming = static_cast<const LowState*>(message);
    if (!valid_crc(*incoming)) {
      return;
    }
    {
      std::lock_guard<std::mutex> lock(state_mutex_);
      if (has_state_.load() && !NativeStateTickAdvances(state_.tick(),incoming->tick())) {
        return; // Duplicate/backward messages must not keep the state watchdog alive.
      }
      state_ = *incoming;
      state_received_ = Clock::now();
      has_state_.store(true);
    }
  }

  Desired desired() const {
    std::lock_guard<std::mutex> lock(desired_mutex_);
    if (!has_desired_) {
      throw std::runtime_error("No desired command");
    }
    return desired_;
  }

  void write_cycle() {
    std::lock_guard<std::recursive_mutex> command_lock(command_mutex_);
    if (!active_.load()) {
      return;
    }
    if (vr_watchdog_ && !damping_.load()) {
      const auto why = vr_watchdog_();
      if (!why.empty()) latch(why, why == "input_disengaged");
    }
    const auto cycle_started = Clock::now();
    double snapshot_age_ms=0;
    Clock::time_point received;
    const LowState state = snapshot(&snapshot_age_ms,&received);
    Desired command_desired;
    if (!damping_.load()) {
      try {
        validate_state(state, true, kVelocityLimit, false, received);
        command_desired = desired();
        if (command_watchdog_expired(
                Clock::now(),
                command_desired.created,
                activated_at_,
                kCommandTimeout,
                kHandoffCommandGrace)) {
          throw std::runtime_error("50-Hz policy command stale");
        }
      } catch (const std::exception& error) {
        latch(std::string("RuntimeError: ") + error.what(), false, &state, snapshot_age_ms);
      }
    }

    LowCmd command{};
    command.mode_pr() = kExpectedModePr;
    command.mode_machine() = state.mode_machine();
    std::uint64_t cycle_active_commands = 0;
    std::uint64_t cycle_limited_commands = 0;
    double cycle_predicted_torque_abs_max = 0.0;
    auto candidate_last = last_target_;
    for (std::size_t i = 0; i < command.motor_cmd().size(); ++i) {
      auto& motor = command.motor_cmd()[i];
      motor.mode() = 1;
      motor.dq() = 0.0F;
      motor.tau() = 0.0F;
      if (i >= kDofs || damping_.load()) {
        motor.q() = 0.0F;
        motor.kp() = 0.0F;
        motor.kd() = (i == 3 || i == 9) ? 2.0F : 1.0F;
        continue;
      }

      const float rate = i < kLegDofs ? kLegTargetRate : kUpperTargetRate;
      const float delta =
          rate * std::chrono::duration<float>(kLowCmdPeriod).count();
      const float soft_torque = kTorqueLimit[i] * kSoftTorqueFraction;
      const float feedforward = std::clamp(
          command_desired.feedforward[i], -soft_torque, soft_torque);
      const float torque_without_position =
          -kKd[i] * state.motor_state()[i].dq() + feedforward;
      const auto limited = NativeLimitedPosition(command_desired.target[i],last_target_[i],
          state.motor_state()[i].q(),delta,kLower[i]+kJointLimitMargin,
          kUpper[i]-kJointLimitMargin,kKp[i],torque_without_position,soft_torque);
      if (!limited) {
        latch("incompatible rate/joint/torque limits", false, &state, snapshot_age_ms);
        break;
      }
      const float target=*limited;
      if (std::abs(target - command_desired.target[i]) > 1.0e-7F) {
        ++cycle_limited_commands;
      }
      const double predicted_torque =
          kKp[i] * (target - state.motor_state()[i].q()) -
          kKd[i] * state.motor_state()[i].dq() + feedforward;
      cycle_predicted_torque_abs_max = std::max(
          cycle_predicted_torque_abs_max, std::abs(predicted_torque));
      ++cycle_active_commands;
      candidate_last[i] = target;
      motor.q() = target;
      motor.kp() = kKp[i];
      motor.kd() = kKd[i];
      motor.tau() = feedforward;
    }
    // One failed joint invalidates the entire active frame, including earlier joints.
    if (damping_.load()) {
      cycle_active_commands=0;
      for(std::size_t i=0;i<command.motor_cmd().size();++i){
        auto& motor=command.motor_cmd()[i];motor.mode()=1;motor.q()=0;motor.dq()=0;
        motor.kp()=0;motor.kd()=(i==3||i==9)?2.0F:1.0F;motor.tau()=0;
      }
    } else last_target_=candidate_last;
    command.crc() = crc32_core(
        reinterpret_cast<std::uint32_t*>(&command),
        (sizeof(LowCmd) >> 2U) - 1U);
    const bool sdk_accepted = publisher_->Write(command);

    const auto sent = Clock::now();
    {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    writer_audit_.sequence=write_count_+1;
    writer_audit_.sdk_accepted=sdk_accepted;
    writer_audit_.damping=damping_.load();
    writer_audit_.completed=sent;
    writer_audit_.state_tick=state.tick();
    for(std::size_t i=0;i<kDofs;++i){
      writer_audit_.desired[i]=command_desired.target[i];
      writer_audit_.target[i]=command.motor_cmd()[i].q();
      writer_audit_.position[i]=state.motor_state()[i].q();
      writer_audit_.velocity[i]=state.motor_state()[i].dq();
      writer_audit_.kp[i]=command.motor_cmd()[i].kp();
      writer_audit_.kd[i]=command.motor_cmd()[i].kd();
      writer_audit_.feedforward[i]=command.motor_cmd()[i].tau();
    }
    if (last_write_ != Clock::time_point{}) {
      intervals_ms_.push_back(
          std::chrono::duration<double, std::milli>(
              sent - last_write_)
              .count());
    } else {
      first_write_ = sent;
    }
    last_write_ = sent;
    ++write_count_;
    active_joint_commands_ += cycle_active_commands;
    torque_limited_commands_ += cycle_limited_commands;
    predicted_torque_abs_max_ = std::max(
        predicted_torque_abs_max_, cycle_predicted_torque_abs_max);
    max_handler_ms_ = std::max(
        max_handler_ms_,
        std::chrono::duration<double, std::milli>(
            sent - cycle_started)
            .count());
    }
#ifdef TWIST2_SPLIT_CANDIDATE
    // Preserve the attempted-frame audit, then latch before another active write.
    if(!sdk_accepted)latch("SDK command write rejected");
#endif
  }

  mutable std::mutex state_mutex_;
  LowState state_{};
  Clock::time_point state_received_{};
  std::atomic<bool> has_state_{false};
  std::array<float, kDofs> capture_q_{};
  std::array<float, kDofs> capture_tau_{};
  std::array<float, kDofs> last_target_{};

  mutable std::mutex desired_mutex_;
  Desired desired_{};
  bool has_desired_{false};

  // Serialize stop latching with the final frame decision and SDK Write.
  // Write may block: target-SDK timing still needs measurement.
  std::recursive_mutex command_mutex_;
  unitree::robot::ChannelPublisherPtr<LowCmd> publisher_;
  unitree::robot::ChannelSubscriberPtr<LowState> subscriber_;
  std::unique_ptr<unitree::robot::b2::MotionSwitcherClient> switcher_;
  std::function<std::string()> vr_watchdog_;
  unitree::common::ThreadPtr writer_;

  std::atomic<bool> active_{false};
  Clock::time_point activated_at_{};
  std::atomic<bool> damping_{false};
  std::atomic<bool> planned_{false};
  mutable std::mutex reason_mutex_;
  std::string reason_{"not started"};
  NativeStopAudit stop_audit_;

  mutable std::mutex stats_mutex_;
  std::uint64_t write_count_{0};
  Clock::time_point first_write_{};
  Clock::time_point last_write_{};
  std::vector<double> intervals_ms_;
  double max_handler_ms_{0.0};
  std::uint64_t active_joint_commands_{0};
  std::uint64_t torque_limited_commands_{0};
  double predicted_torque_abs_max_{0.0};
  WriterAudit writer_audit_{};
};

std::filesystem::path write_csv(const std::vector<Sample>& samples) {
  const auto timestamp = std::chrono::system_clock::to_time_t(
      std::chrono::system_clock::now());
  std::ostringstream name;
  name << "g1_twist2_right_arm_trial_" << timestamp << ".csv";
  const auto path = std::filesystem::current_path() / name.str();
  std::ofstream stream(path);
  if (!stream) {
    throw std::runtime_error("Could not create CSV");
  }
  stream
      << "elapsed_s,phase,alpha,arm_alpha,state_age_ms,inference_ms,"
         "roll_rad,pitch_rad,writer_attempt_sequence,writer_sdk_accepted,writer_damping,writer_state_tick,writer_age_ms";
  for (std::size_t i = 0; i < kDofs; ++i) {
    stream << ",action_" << i << ",q_" << i << ",dq_" << i
           << ",tau_est_" << i << ",desired_target_" << i
           << ",mimic_target_" << i
           << ",writer_desired_" << i << ",writer_target_" << i
           << ",writer_q_" << i << ",writer_dq_" << i
           << ",writer_kp_" << i << ",writer_kd_" << i << ",writer_ff_" << i;
  }
  NativeStateAudit::Header(stream);
  stream << '\n' << std::setprecision(9);
  for (const Sample& sample : samples) {
    stream << sample.elapsed_s << ',' << sample.phase << ',' << sample.alpha
           << ',' << sample.arm_alpha << ',' << sample.state_age_ms << ','
           << sample.inference_ms << ',' << sample.roll << ','
           << sample.pitch;
    stream << ',' << sample.writer.sequence << ',' << sample.writer.sdk_accepted
           << ',' << sample.writer.damping << ',' << sample.writer.state_tick
           << ',' << sample.writer_age_ms;
    for (std::size_t i = 0; i < kDofs; ++i) {
      stream << ',' << sample.action[i] << ',' << sample.position[i] << ','
             << sample.velocity[i] << ',' << sample.estimated_torque[i] << ','
             << sample.target[i] << ',' << sample.mimic_target[i]
             << ',' << sample.writer.desired[i] << ',' << sample.writer.target[i]
             << ',' << sample.writer.position[i] << ',' << sample.writer.velocity[i]
             << ',' << sample.writer.kp[i] << ',' << sample.writer.kd[i]
             << ',' << sample.writer.feedforward[i];
    }
    sample.state_audit.Row(stream);
    stream << '\n';
  }
  return path;
}

}  // namespace

int main(int argc, char** argv) {
  std::signal(SIGINT, signal_handler);
  std::signal(SIGTERM, signal_handler);
  try {
#ifdef TWIST2_SPLIT_CANDIDATE
    constexpr bool relative_candidate=true;
#else
    constexpr bool relative_candidate=false;
#endif
    if(!NativeVrInvocationValid(argc,argv,relative_candidate))
      throw std::runtime_error("native VR draft requires explicit VR invocation; not a keyboard executable");
    const bool default_duration =
        argc == 4 && std::string(argv[3]) == "--enable-actuation";
    const bool explicit_duration =
        argc == 6 && std::string(argv[3]) == "--enable-actuation" &&
        std::string(argv[4]) == "--policy-seconds";
    const bool right_arm_motion =
        argc == 8 && std::string(argv[3]) == "--enable-actuation" &&
        std::string(argv[4]) == "--policy-seconds" &&
        std::string(argv[6]) == "--right-shoulder-forward-deg";
    const bool vr_right_arm=NativeVrInvocationValid(argc,argv,relative_candidate);
    if (!default_duration && !explicit_duration && !right_arm_motion &&
        !vr_right_arm) {
      std::cerr
          << "Usage: " << argv[0]
          << " eth0 /absolute/twist2_1017_20k_torchscript.pt "
             "--enable-actuation [--policy-seconds 2..20 "
             "[--right-shoulder-forward-deg 30]]\n"
          << "       " << argv[0]
          << " eth0 /absolute/twist2_1017_20k_torchscript.pt "
             "--enable-actuation --policy-seconds 2..20 "
             "--vr-right-arm\n";
      return 2;
    }
    double policy_seconds = kDefaultPolicySeconds;
    if (explicit_duration || right_arm_motion || vr_right_arm) {
      std::size_t parsed = 0;
      const std::string duration_text(argv[5]);
      policy_seconds = std::stod(duration_text, &parsed);
      const double maximum_duration =
          vr_right_arm
              ? kKeyboardPolicySeconds
              : kMaximumPolicySeconds;
      if (parsed != duration_text.size() ||
          !std::isfinite(policy_seconds) ||
          policy_seconds < kMinimumPolicySeconds ||
          policy_seconds > maximum_duration) {
        throw std::runtime_error(
            vr_right_arm
                ? "VR draft requires --policy-seconds 2..20"
                : "--policy-seconds must be a finite value from 2 through 20");
      }
    }
    float right_shoulder_forward_degrees = 0.0F;
    if (right_arm_motion) {
      std::size_t parsed = 0;
      const std::string degrees_text(argv[7]);
      right_shoulder_forward_degrees =
          std::stof(degrees_text, &parsed);
      if (parsed != degrees_text.size() ||
          !std::isfinite(right_shoulder_forward_degrees) ||
          std::abs(
              right_shoulder_forward_degrees -
              kInitialRightShoulderForwardDegrees) >
              1.0e-6F ||
          std::abs(policy_seconds - kMaximumPolicySeconds) > 1.0e-9) {
        throw std::runtime_error(
            "Initial right-arm motion requires exactly "
            "--policy-seconds 20 --right-shoulder-forward-deg 30");
      }
    }
    const std::filesystem::path policy_path(argv[2]);
    Policy policy{policy_path};
    const std::string confirmation_phrase = "P";

    std::cout
        << "=== G1 TWIST2 RIGHT ARM TRIAL ===\n"
        << "policy: " << policy_path << '\n'
        << "sha256: " << kExpectedPolicySha256 << '\n'
        << "timeline: capture 1 s -> leg-only blend 4 s -> "
           "TWIST2 legs " << policy_seconds << " s -> damping\n";
    if (vr_right_arm) {
      std::cout
          << "control: policy legs 0:12; captured waist/left arm held; "
             "right arm 7-DOF VR-commanded\n";
    } else {
      std::cout
          << "control: policy legs 0:12; captured waist and arms held\n";
    }
    if (right_arm_motion) {
      std::cout
          << "arm timeline: policy 0-10 s hold; policy 10-20 s "
             "right shoulder forward 30 deg S-curve\n";
    }
    if (vr_right_arm) {
      std::cout
          << "VR timeline: after blend and measured ready, right arm is "
             "controlled until pinch or the explicit duration limit\n"
          << "warning: shoulder roll/yaw, elbow, wrist, and 2x-9x speeds "
             "are new physical test conditions; use one key step first\n";
      std::cout << "[VR] validated UDP right-arm targets, 0.08 rad/s; pinch/timeout latches damping\n";
    }
    std::cout
        << "Hold R1 continuously; release R1 or press Select/B for damping.\n"
        << "The robot finishes in damping; AI standing is not restored.\n"
        << "Type exactly '" << confirmation_phrase << "' to continue: ";
    std::string confirmation;
    std::getline(std::cin, confirmation);
    if (confirmation != confirmation_phrase) {
      std::cout << "[safety] cancelled before DDS initialization\n";
      return 2;
    }

    Controller controller(argv[1]);
    controller.wait_for_state();
    controller.wait_for_preflight();

    ObservationHistory readiness_history;
    std::vector<double> warmup_ms;
    warmup_ms.reserve(20);
    auto next_warmup = Clock::now();
    for (int step = 0; step < 20; ++step) {
      double state_age_ms = 0.0;
      Clock::time_point received;
      const LowState state = controller.snapshot(&state_age_ms,&received);
      controller.validate_state(
          state, true, kPreflightVelocityLimit, true, received);
      const PolicyResult result = readiness_history.infer(
          policy, state, controller.capture_q());
      const auto target = hybrid_target(
          result.action, controller.capture_q());
      readiness_history.commit(
          result.current, target_as_action(target));
      warmup_ms.push_back(result.inference_ms);
      next_warmup += kPolicyPeriod;
      std::this_thread::sleep_until(next_warmup);
    }

    readiness_history.reset();
    double readiness_state_age_ms = 0.0;
    Clock::time_point readiness_received;
    const LowState readiness_state =
        controller.snapshot(&readiness_state_age_ms,&readiness_received);
    controller.validate_state(
        readiness_state, true, kPreflightVelocityLimit, true, readiness_received);
    const PolicyResult readiness = readiness_history.infer(
        policy, readiness_state, controller.capture_q());
    if (readiness.inference_ms > 45.0) {
      throw std::runtime_error(
          "readiness inference exceeded 45 ms before handoff");
    }
    std::cout << "[policy] real-state warm-up passed: final="
              << std::fixed << std::setprecision(3)
              << readiness.inference_ms << " ms, warmup_max="
              << *std::max_element(warmup_ms.begin(), warmup_ms.end())
              << " ms\n";

    // Allocate all policy-loop storage before releasing the built-in service.
    // After handoff, every potentially throwing operation is inside the latch
    // block below so a failure cannot bypass damping.
    ObservationHistory history;
    std::vector<double> inference_ms;
    std::vector<Sample> samples;
    const auto planned_policy_steps = static_cast<std::size_t>(
        std::ceil(
            (kCaptureSeconds + kBlendSeconds + policy_seconds) * 50.0)) +
        10U;
    inference_ms.reserve(planned_policy_steps);
    samples.reserve(planned_policy_steps);
    double action_abs_max = 0.0;
    double action_delta_abs_max = 0.0;
    double roll_abs_max = 0.0;
    double pitch_abs_max = 0.0;
    double right_shoulder_tracking_error_abs_max = 0.0;
    double right_shoulder_command_forward_abs_max = 0.0;
    double right_arm_tracking_error_abs_max = 0.0;
    std::array<float, kDofs> previous_action{};

    controller.capture(controller.snapshot());
    const float right_shoulder_start =
        controller.capture_q()[kRightShoulderPitch];
    const float right_shoulder_final =
        right_shoulder_start +
        kForwardShoulderPitchSign *
            right_shoulder_forward_degrees * kDegreesToRadians;
    if (right_arm_motion &&
        (right_shoulder_final <
             kLower[kRightShoulderPitch] + kJointLimitMargin ||
         right_shoulder_final >
             kUpper[kRightShoulderPitch] - kJointLimitMargin)) {
      throw std::runtime_error(
          "Captured right shoulder cannot safely move forward 30 degrees");
    }
    if (right_arm_motion) {
      std::cout << "[arm] right shoulder pitch start="
                << right_shoulder_start
                << " rad, final=" << right_shoulder_final
                << " rad, peak trajectory speed="
                << (1.5 * right_shoulder_forward_degrees *
                    kDegreesToRadians / kArmMotionSeconds)
                << " rad/s\n";
    }
    if (vr_right_arm) {
      std::cout << "[arm] captured right-arm targets and safe ranges:\n";
      for (std::size_t arm = 0; arm < kRightArmDofs; ++arm) {
        const std::size_t joint = kRightArmBegin + arm;
        std::cout
            << "  " << kRightArmNames[arm]
            << " start=" << controller.capture_q()[joint]
            << " range=[" << kLower[joint] + kJointLimitMargin
            << ", " << kUpper[joint] - kJointLimitMargin << "] rad\n";
      }
    }
    const auto vr_clock = [](){ return std::chrono::duration<double>(Clock::now().time_since_epoch()).count(); };
    std::array<double,29> vr_capture{}, vr_previous{};
    for (std::size_t i=0;i<29;++i) vr_capture[i]=controller.capture_q()[i];
    vr_previous=vr_capture;
    #ifdef TWIST2_SPLIT_CANDIDATE
    std::cout << "[candidate] experimental split settle + relative VR; not physically validated\n";
    auto vr_target=std::make_shared<SplitVrAdapterStudy>(vr_capture,vr_clock(),SplitSettleLimits{1,.005,.01,.1,.1,.15},true);
#else
    auto vr_target=std::make_shared<NativeVrPolicyAdapter>(vr_capture,vr_clock());
#endif
    NativeVrUdp vr_udp;
    controller.set_vr_watchdog([vr_target,vr_clock](){return vr_target->Poll(vr_clock());});
    const int keyboard_speed_multiplier=1;
    controller.set_capture_desired();
    controller.start_writer();
    try { controller.handoff_and_activate(); }
    catch (...) {
      // active_ stays false. Do not start a competing damping publisher or claim restoration.
      std::cerr << "[handoff ABORT] VR loop was not entered; robot mode/ownership is not confirmed.\n";
      throw;
    }

    const auto started = Clock::now();
    auto next_policy = started + kPolicyPeriod;
    const double active_seconds =
        kCaptureSeconds + kBlendSeconds + policy_seconds;

    std::optional<LowState> policy_context;
    double policy_snapshot_age_ms=-1;
    try {
      // ReleaseMode can take longer than the normal 60-ms policy watchdog.
      // Refresh the already safe capture command immediately after handoff;
      // the writer permits only the bounded handoff grace before this update.
      controller.set_capture_desired();
      while (!controller.damping() && !gInterrupt.load()) {
        policy_context.reset();
        const auto now = Clock::now();
        const double elapsed =
            std::chrono::duration<double>(now - started).count();
        if (elapsed >= active_seconds) {
          controller.latch("planned policy duration completed", true);
          break;
        }
        if (now < next_policy) {
          std::this_thread::sleep_until(next_policy);
          continue;
        }

        double state_age_ms = 0.0;
        Clock::time_point received;
        const LowState state = controller.snapshot(&state_age_ms,&received);
        policy_context=state;
        policy_snapshot_age_ms=state_age_ms;
        const double vr_state_receipt=std::chrono::duration<double>(received.time_since_epoch()).count();
        controller.validate_state(state, true, kVelocityLimit, false, received);

        float alpha = 0.0F;
        float arm_alpha = 0.0F;
        std::string phase = "capture";
        if (elapsed >= kCaptureSeconds + kBlendSeconds) {
          alpha = 1.0F;
          phase = "policy";
        } else if (elapsed >= kCaptureSeconds) {
          alpha = smoothstep(static_cast<float>(
              (elapsed - kCaptureSeconds) / kBlendSeconds));
          phase = "blend";
        }

        std::array<float, kDofs> upper_target =
            controller.capture_q();
        if (right_arm_motion) {
          const double policy_elapsed =
              elapsed - kCaptureSeconds - kBlendSeconds;
          arm_alpha = smoothstep(static_cast<float>(
              (policy_elapsed - kArmHoldPolicySeconds) /
              kArmMotionSeconds));
          upper_target[kRightShoulderPitch] =
              right_shoulder_start +
              arm_alpha *
                  (right_shoulder_final - right_shoulder_start);
          if (policy_elapsed >= kArmHoldPolicySeconds) {
            phase = "arm";
          }
        }
        #ifdef TWIST2_SPLIT_CANDIDATE
        std::optional<WriterAudit> initial_reference;
        #endif
        if (vr_right_arm) {
          vr_udp.Drain(*vr_target,vr_clock);
#ifdef TWIST2_SPLIT_CANDIDATE
          if(vr_target->NeedsCommandReference()) {
            initial_reference=controller.capture_relative_reference();
            std::array<double,29> command{};
            std::copy(initial_reference->target.begin(),initial_reference->target.end(),command.begin());
            if(!vr_target->BindCommandReference(command))throw std::runtime_error("relative reference binding failed");
          }
#endif
          std::array<double,29> measured{}, velocity{};
          for(std::size_t i=0;i<29;++i){measured[i]=state.motor_state()[i].q();velocity[i]=state.motor_state()[i].dq();}
          const auto updated=vr_target->Update(measured,velocity,vr_previous,
              vr_state_receipt,vr_clock(),alpha>=1.0F
#ifdef TWIST2_SPLIT_CANDIDATE
              ,{state.imu_state().rpy()[0],state.imu_state().rpy()[1],state.imu_state().rpy()[2]},
              {state.imu_state().gyroscope()[0],state.imu_state().gyroscope()[1],state.imu_state().gyroscope()[2]},
              NativeSnapshotFresh(received,Clock::now(),kStateTimeout)&&!controller.damping()
#endif
              );
          for(std::size_t i=12;i<29;++i)upper_target[i]=static_cast<float>(updated[i]);
          phase=alpha>=1.0F?vr_target->Phase():phase;
        }
        std::array<float, kDofs> mimic_target{};
        for (std::size_t i = 0; i < kDofs; ++i) {
          mimic_target[i] = i < kLegDofs
                                ? (1.0F - alpha) *
                                          controller.capture_q()[i] +
                                      alpha * kDefault[i]
                                : upper_target[i];
        }
        const PolicyResult result =
            history.infer(policy, state, mimic_target);
        inference_ms.push_back(result.inference_ms);
        if (result.inference_ms > 45.0) {
          throw std::runtime_error("policy inference exceeded 45 ms");
        }
        const auto full_policy_target =
            hybrid_target(result.action, upper_target);

        Desired desired;
        desired.created = Clock::now();
        for (std::size_t i = 0; i < kDofs; ++i) {
          desired.target[i] =
              (1.0F - alpha) * controller.capture_q()[i] +
              alpha * full_policy_target[i];
          desired.feedforward[i] =
              (1.0F - alpha) * controller.capture_tau()[i];
        }
#ifdef TWIST2_SPLIT_CANDIDATE
        controller.commit_relative_desired(desired,initial_reference);
#else
        controller.set_desired(desired);
#endif
        for(std::size_t i=0;i<29;++i)vr_previous[i]=desired.target[i];
        const auto applied = target_as_action(desired.target);
        history.commit(result.current, applied);

        Sample sample;
        sample.elapsed_s = elapsed;
        sample.phase = phase;
        sample.alpha = alpha;
        sample.arm_alpha = arm_alpha;
        sample.state_age_ms = state_age_ms;
        sample.inference_ms = result.inference_ms;
        sample.roll = state.imu_state().rpy()[0];
        sample.pitch = state.imu_state().rpy()[1];
        sample.state_audit = NativeStateAudit::Capture(state);
        sample.action = result.action;
        sample.target = desired.target;
        sample.mimic_target = mimic_target;
        sample.writer=controller.writer_audit();
        if(sample.writer.sequence!=0)sample.writer_age_ms=
            std::chrono::duration<double,std::milli>(Clock::now()-sample.writer.completed).count();
        for (std::size_t i = 0; i < kDofs; ++i) {
          sample.position[i] = state.motor_state()[i].q();
          sample.velocity[i] = state.motor_state()[i].dq();
          sample.estimated_torque[i] =
              state.motor_state()[i].tau_est();
          if (i < kLegDofs) {
            action_abs_max = std::max(
                action_abs_max,
                std::abs(static_cast<double>(result.action[i])));
            action_delta_abs_max = std::max(
                action_delta_abs_max,
                std::abs(static_cast<double>(
                    result.action[i] - previous_action[i])));
          }
        }
        previous_action = result.action;
        if (right_arm_motion || vr_right_arm) {
          right_shoulder_tracking_error_abs_max = std::max(
              right_shoulder_tracking_error_abs_max,
              std::abs(static_cast<double>(
                  sample.position[kRightShoulderPitch] -
                  sample.target[kRightShoulderPitch])));
          right_shoulder_command_forward_abs_max = std::max(
              right_shoulder_command_forward_abs_max,
              std::abs(static_cast<double>(
                  right_shoulder_start -
                  sample.target[kRightShoulderPitch])));
        }
        if (vr_right_arm) {
          for (std::size_t arm = 0; arm < kRightArmDofs; ++arm) {
            const std::size_t joint = kRightArmBegin + arm;
            right_arm_tracking_error_abs_max = std::max(
                right_arm_tracking_error_abs_max,
                std::abs(static_cast<double>(
                    sample.position[joint] - sample.target[joint])));
          }
        }
        samples.push_back(sample);
        roll_abs_max = std::max(
            roll_abs_max, std::abs(static_cast<double>(sample.roll)));
        pitch_abs_max = std::max(
            pitch_abs_max, std::abs(static_cast<double>(sample.pitch)));
        const std::size_t console_period =
            vr_right_arm ? 50U : 10U;
        if (samples.size() % console_period == 0) {
          std::cout << "\r[actuate] " << std::fixed << std::setprecision(2)
                    << elapsed << "s phase=" << std::setw(7) << phase
                    << " alpha=" << alpha
                    << " arm=" << arm_alpha
                    << " roll=" << sample.roll
                    << " pitch=" << sample.pitch << std::flush;
        }
        next_policy += kPolicyPeriod;
        if (next_policy < Clock::now() - kPolicyPeriod) {
          throw std::runtime_error("50-Hz policy loop missed a full period");
        }
      }
      if (gInterrupt.load() && !controller.damping()) {
        controller.latch("operator signal");
      }
    } catch (const std::exception& error) {
      const auto* context=policy_context ? &*policy_context : nullptr;
      if (std::string(error.what()) == "input_disengaged") controller.latch("input_disengaged", true, context, policy_snapshot_age_ms);
      else controller.latch(std::string("RuntimeError: ") + error.what(), false, context, policy_snapshot_age_ms);
    }

    std::cout << '\n';
    controller.finish();
    const auto csv_path = write_csv(samples);
    controller.write_stop_audit(csv_path);
    const bool completed_duration =
        controller.reason() == "planned policy duration completed";
    const bool operator_stop =
        controller.reason() == "input_disengaged";
    const bool completed = completed_duration || operator_stop;
    const double inference_mean =
        inference_ms.empty()
            ? 0.0
            : std::accumulate(
                  inference_ms.begin(), inference_ms.end(), 0.0) /
                  static_cast<double>(inference_ms.size());
    std::cout << std::fixed << std::setprecision(6)
              << "{\n"
              << "  \"status\": \""
              << (completed_duration
                      ? "completed"
                      : (operator_stop ? "operator_stop" : "safety_stop"))
              << "\",\n"
              << "  \"reason\": \"" << controller.reason() << "\",\n"
              << "  \"policy_sha256\": \"" << kExpectedPolicySha256
              << "\",\n"
              << "  \"capture_s\": " << kCaptureSeconds << ",\n"
              << "  \"blend_s\": " << kBlendSeconds << ",\n"
              << "  \"policy_s\": " << policy_seconds << ",\n"
              << "  \"right_shoulder_forward_deg\": "
              << right_shoulder_forward_degrees << ",\n"
              << "  \"right_shoulder_start_rad\": "
              << right_shoulder_start << ",\n"
              << "  \"right_shoulder_final_rad\": "
              << right_shoulder_final << ",\n"
              << "  \"right_shoulder_tracking_error_abs_max_rad\": "
              << right_shoulder_tracking_error_abs_max << ",\n"
              << "  \"right_shoulder_command_forward_abs_max_rad\": "
              << right_shoulder_command_forward_abs_max << ",\n"
              << "  \"right_arm_tracking_error_abs_max_rad\": "
              << right_arm_tracking_error_abs_max << ",\n"
              << "  \"keyboard_final_speed_multiplier\": "
              << keyboard_speed_multiplier << ",\n"
              << "  \"policy_steps\": " << samples.size() << ",\n"
              << "  \"takeover_inference_ms\": "
              << readiness.inference_ms << ",\n"
              << "  \"inference_ms_mean\": " << inference_mean << ",\n"
              << "  \"inference_ms_p99\": "
              << percentile(inference_ms, 0.99) << ",\n"
              << "  \"inference_ms_max\": "
              << (inference_ms.empty()
                      ? 0.0
                      : *std::max_element(
                            inference_ms.begin(), inference_ms.end()))
              << ",\n"
              << "  \"leg_action_abs_max\": " << action_abs_max << ",\n"
              << "  \"leg_action_delta_abs_max\": "
              << action_delta_abs_max << ",\n"
              << "  \"roll_abs_max_rad\": " << roll_abs_max << ",\n"
              << "  \"pitch_abs_max_rad\": " << pitch_abs_max << ",\n"
              << "  \"csv_path\": \"" << csv_path.string() << "\",\n";
    controller.print_stats();
    std::cout
        << "}\n"
        << "[safety] controller ended in damping; AI standing was not restored\n";
    return completed ? 0 : 1;
  } catch (const c10::Error& error) {
    std::cerr << "[fatal] Torch error: "
              << error.what_without_backtrace() << '\n';
  } catch (const std::exception& error) {
    std::cerr << "[fatal] " << error.what() << '\n';
  }
  return 1;
}
