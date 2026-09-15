#include "twist2_common.hpp"
#include "native_vr_cycle_udp.hpp"
#include "mink_live_cycle_target.hpp"
#include "periodic_csv.hpp"
#include "real_response_frame.hpp"
#include "sysid_native_observer.hpp"
#include "sysid_excitation_observer_bridge.hpp"
#include <cstdlib>
#include "writer_frame.hpp"
#include "pd_reach_trial.hpp"
#include "pd_small_signal_trial.hpp"
#include "pd_ready_settle.hpp"
#include "pd_gain_options.hpp"
#include "native_snapshot_freshness.hpp"
#include "native_state_tick.hpp"
#include "verified_regular_handoff.hpp"
#include "regular_handoff_safety.hpp"
#include <functional>

#include <unitree/common/thread/thread.hpp>
#include <unitree/common/thread/recurrent_thread.hpp>
#include <unitree/robot/b2/motion_switcher/motion_switcher_client.hpp>
#include <unitree/robot/g1/loco/g1_loco_client.hpp>
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
#include <optional>
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
constexpr double kKeyboardPolicySeconds = 300.0;
constexpr double kArmHoldPolicySeconds = 10.0;
constexpr double kArmMotionSeconds = 10.0;
constexpr float kInitialRightShoulderForwardDegrees = 30.0F;
constexpr float kKeyboardIncrement = 0.02F;
constexpr float kKeyboardBaseTargetRate = 0.08F;
constexpr float kKeyboardTrackingErrorLimit = 0.25F;
constexpr float kKeyboardMeasuredVelocityLimit = 1.5F;
constexpr float kRightArmReturnApproachMargin = 0.08F;
float cycle_speed(size_t joint){
 const bool today=std::string(std::getenv("G1_MINK_SPEED_PROFILE")?std::getenv("G1_MINK_SPEED_PROFILE"):"")=="today";
 if(joint<22)return kUpperTargetRate;
 return today?(joint<26?1.57079632679F:3.14159265359F):.7F;
}
float cycle_measured_speed_limit(size_t joint){return joint<22?kKeyboardMeasuredVelocityLimit:cycle_speed(joint)+.8F;}

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
constexpr std::uint16_t kSelect = 0x0008U;
constexpr std::uint16_t kB = 0x0200U;

std::atomic<unsigned> gOperatorSignalCount{0};

void signal_handler(int) {
  gOperatorSignalCount.fetch_add(1);
}

class TerminalKeyboard {
 public:
  TerminalKeyboard() {
    if (::isatty(STDIN_FILENO) != 1) {
      throw std::runtime_error(
          "keyboard mode requires an interactive terminal on stdin");
    }
    if (::tcgetattr(STDIN_FILENO, &original_) != 0) {
      throw std::runtime_error("tcgetattr failed for keyboard mode");
    }
    termios configured = original_;
    configured.c_lflag &= static_cast<tcflag_t>(~(ICANON | ECHO));
    configured.c_cc[VMIN] = 0;
    configured.c_cc[VTIME] = 0;
    if (::tcsetattr(STDIN_FILENO, TCSANOW, &configured) != 0) {
      throw std::runtime_error("tcsetattr failed for keyboard mode");
    }
    enabled_ = true;
    ::tcflush(STDIN_FILENO, TCIFLUSH);
  }

  TerminalKeyboard(const TerminalKeyboard&) = delete;
  TerminalKeyboard& operator=(const TerminalKeyboard&) = delete;

  ~TerminalKeyboard() {
    if (enabled_) {
      ::tcsetattr(STDIN_FILENO, TCSANOW, &original_);
    }
  }

  std::string read_available() const {
    pollfd descriptor{};
    descriptor.fd = STDIN_FILENO;
    descriptor.events = POLLIN;
    const int ready = ::poll(&descriptor, 1, 0);
    if (ready < 0) {
      if (errno == EINTR) {
        return {};
      }
      throw std::runtime_error("keyboard poll failed");
    }
    if (ready == 0) {
      return {};
    }
    if ((descriptor.revents & (POLLERR | POLLNVAL)) != 0) {
      throw std::runtime_error("keyboard terminal error");
    }
    if ((descriptor.revents & POLLHUP) != 0) {
      throw std::runtime_error("keyboard terminal disconnected");
    }
    char buffer[64]{};
    const ssize_t count = ::read(STDIN_FILENO, buffer, sizeof(buffer));
    if (count < 0) {
      if (errno == EINTR || errno == EAGAIN) {
        return {};
      }
      throw std::runtime_error("keyboard read failed");
    }
    return std::string(buffer, static_cast<std::size_t>(count));
  }

 private:
  termios original_{};
  bool enabled_{false};
};

void print_keyboard_help() {
  std::cout
      << "\n[keyboard] right arm: plus / zero rad / minus\n"
      << "  shoulder pitch q/a/z    shoulder roll  w/s/x\n"
      << "  shoulder yaw   e/d/c    elbow          r/f/v\n"
      << "  wrist roll     t/g/b    wrist pitch    y/h/n\n"
      << "  wrist yaw      u/j/m\n"
      << "[keyboard] speed: 1..9 = 0.08..0.72 rad/s; "
         "?=help; P/Q=safe arm return and continued TWIST2 hold\n"
      << "[keyboard] every command is clamped to its configured soft "
         "joint limits\n";
}

struct Desired {
  int trial_phase=0,trial_cycle=0;
  Clock::time_point created{};
  std::array<float, kDofs> target{};
  std::array<float, kDofs> feedforward{};
};

struct Sample {
  WriterFrame writer_frame;
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
};

class Controller {
 public:
  WriterFrame writer_frame() const {return writer_frames_.Read();}
  explicit Controller(const std::string& interface,const PdGainOptions& gains)
      : kp_(gains.kp),kd_(gains.kd) {
    // Reserve before handoff so the 500-Hz statistics path does not allocate.
    // Reserve before any handoff so the 500-Hz statistics path does not
    // allocate during the bounded run.
    intervals_ms_.reserve(200000);
    unitree::robot::ChannelFactory::Instance()->Init(0, interface);
    switcher_ =
        std::make_unique<unitree::robot::b2::MotionSwitcherClient>();
    loco_ = std::make_unique<unitree::robot::g1::LocoClient>();
    publisher_.reset(
        new unitree::robot::ChannelPublisher<LowCmd>("rt/lowcmd"));
    subscriber_.reset(
        new unitree::robot::ChannelSubscriber<LowState>("rt/lowstate"));
    publisher_->InitChannel();
    subscriber_->InitChannel(
        std::bind(&Controller::on_state, this, std::placeholders::_1), 1);
    switcher_->SetTimeout(5.0F);
    switcher_->Init();
    loco_->SetTimeout(5.0F);
    loco_->Init();
  }

  ~Controller() {
    // Stop callbacks while their state/mutex members are still alive.
    active_.store(false);
    writer_.reset();
    subscriber_.reset();
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
    if (age_ms != nullptr) {
      *age_ms = std::chrono::duration<double, std::milli>(
                    Clock::now() - state_received_)
                    .count();
    }
    if(received)*received=state_received_;
    return state_;
  }

  void validate_state(
      const LowState& state,
      float velocity_limit,
      bool arming, Clock::time_point received,
      bool permit_right_arm_soft_margin = false) const {
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
        const bool recoverable_right_arm_margin =
            permit_right_arm_soft_margin && i >= kRightArmBegin &&
            motor.q() >= kLower[i] && motor.q() <= kUpper[i];
        if (!recoverable_right_arm_margin)
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
        << "[preflight] AI standing must be active; Select/B must be released; "
           "waiting for 1 s stable\n";
    const auto deadline = Clock::now() + std::chrono::seconds(60);
    auto stable_since = Clock::time_point{};
    std::string last_reason;
    while (Clock::now() < deadline && gOperatorSignalCount.load() == 0U) {
      Clock::time_point received;
    const LowState state = snapshot(nullptr,&received);
      bool valid = true;
      try {
        validate_state(state, kPreflightVelocityLimit, true, received);
        if ((remote_buttons(state) & (kSelect | kB)) != 0U)
          throw std::runtime_error("Select/B pressed");
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
    capture_ready_ = true;
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

  void set_input_watchdog(std::function<std::string()> check){input_watchdog_=std::move(check);}

  void set_proximal_pd(float kp,float kd) {
    if(!std::isfinite(kp)||!std::isfinite(kd)||kp<1.F||kp>100.F||kd<.1F||kd>20.F)
      throw std::runtime_error("invalid proximal PD sweep gain");
    std::lock_guard<std::mutex> lock(gains_mutex_);
    for(std::size_t i=22;i<26;++i){kp_[i]=kp;kd_[i]=kd;}
  }

  void start_writer() {
    writer_ = unitree::common::CreateRecurrentThreadEx(
        "g1_twist2_500hz",
        UT_CPU_ID_NONE,
        2000,
        &Controller::write_cycle,
        this);
  }

  // Compile-integrated seam only. No current CLI or launcher calls this method.
  // A later reviewed caller must install it before the writer and handoff start.
  void install_sysid_excitation_for_review(
      std::unique_ptr<sysid_excitation::Runtime> runtime) {
    std::lock_guard<std::mutex> write_lock(write_cycle_mutex_);
    if (!runtime) throw std::invalid_argument("null excitation runtime");
    if (writer_ || active_.load() || excitation_runtime_)
      throw std::logic_error("excitation must be installed before writer start");
    if (!capture_ready_) throw std::logic_error("excitation requires captured state");
    const auto context =
        sysid_excitation::MakeObserverContext(runtime->Describe());
    if (context.termination_owner_status != "reviewed")
      throw std::invalid_argument("excitation termination owner is not reviewed");
    const auto capture_enabled = std::getenv("G1_SYSID_CAPTURE_V2");
    if (!capture_enabled || std::string(capture_enabled) != "1")
      throw std::invalid_argument("excitation requires G1_SYSID_CAPTURE_V2=1");
    std::array<double, kDofs> measured_q{}, active_kp{}, active_kd{};
    std::array<float, kDofs> kp{}, kd{};
    {
      std::lock_guard<std::mutex> gain_lock(gains_mutex_);
      kp = kp_;
      kd = kd_;
    }
    for (std::size_t i = 0; i < kDofs; ++i) {
      measured_q[i] = capture_q_[i];
      active_kp[i] = kp[i];
      active_kd[i] = kd[i];
    }
    runtime->Arm(measured_q, active_kp, active_kd);
    excitation_context_ = context;
    excitation_runtime_ = std::move(runtime);
  }

  void start_response_log(const std::string& path,const std::string& session,const std::string& binary_sha){
    response_log_=std::make_unique<RealResponseLog>(path,session,binary_sha);
    // Explicit opt-in only. A normal run tolerates logger setup failure; an
    // excitation run refuses to start without its required provenance log.
    const auto opt=std::getenv("G1_SYSID_CAPTURE_V2");
    if(opt&&std::string(opt)=="1"){
      try{
        sysid_path_=path+".v2.jsonl";
        sysid_log_=std::make_unique<sysid::Observer>(sysid_path_,session,binary_sha,"measured",
            excitation_context_.value_or(sysid::ExcitationContext{}));
      }catch(...){
        if(excitation_runtime_)throw;
        std::fputs("[SYSID] recording unavailable; control unchanged\n",stderr);
      }
    }
  }
  void finish_response_log(){
    finish_sysid_log();
    if(response_log_)response_log_->Finish();
  }
  void finish_sysid_log() noexcept {
    try{
      std::unique_ptr<sysid::Observer> detached;
      {std::lock_guard<std::mutex> lock(write_cycle_mutex_);detached=std::move(sysid_log_);}
      if(!detached)return;
      auto receipt=detached->Finish(); // disk/join outside writer mutex
      receipt["sha256"]=sha256sum(sysid_path_);
      auto path=std::filesystem::path(sysid_path_);path.replace_extension(".receipt.json");
      const auto text=receipt.dump();
      const int fd=::open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL,0600);
      if(fd<0)throw std::runtime_error("sysid receipt open failed");
      const auto count=::write(fd,text.data(),text.size());const int closed=::close(fd);
      if(count!=static_cast<ssize_t>(text.size())||closed!=0)throw std::runtime_error("sysid receipt write failed");
    }catch(...){std::fputs("[SYSID] incomplete recording; control unchanged\n",stderr);}
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
    const std::int32_t fsm_result = loco_->GetFsmId(start_fsm_id_);
    const std::int32_t balance_result =
        loco_->GetBalanceMode(start_balance_mode_);
    if (fsm_result != 0 ||
        (start_fsm_id_ != 500 && start_fsm_id_ != 501)) {
      throw std::runtime_error(
          "Expected verified Regular FSM 500/501 before handoff; fsm_result=" +
          std::to_string(fsm_result) + " fsm_id=" +
          std::to_string(start_fsm_id_) + " balance_result=" +
          std::to_string(balance_result));
    }
    std::cout << "[handoff] captured Regular state: fsm_id=" << start_fsm_id_
              << " balance_result=" << balance_result;
    if (balance_result == 0)
      std::cout << " balance_mode=" << start_balance_mode_;
    else
      std::cout << " balance_mode=unavailable";
    std::cout << '\n';
    std::cout << "[handoff] releasing motion service: " << name << '\n';
    set_capture_desired();
    // A thrown/failed release has an uncertain outcome. Do not let the main
    // scope unwind until the observed owner is resolved, even at acquisition.
    owner_phase_ = regular_handoff::OwnerPhase::WriterStopped;
    const std::int32_t released = switcher_->ReleaseMode();
    if (released != 0) {
      throw std::runtime_error(
          "MotionSwitcher ReleaseMode failed: " +
          std::to_string(released));
    }
    // desired_ already contains the freshly captured hold command.  Make the
    // 500-Hz writer active immediately after a successful release; do not put
    // another potentially throwing operation in this handoff gap.
    activated_at_ = Clock::now();
    owner_phase_ = regular_handoff::OwnerPhase::Holding;
    active_.store(true);
  }

  void latch(const std::string& reason, bool planned = false) {
    bool expected = false;
    if (handoff_requested_.compare_exchange_strong(expected, true)) {
      std::lock_guard<std::mutex> lock(reason_mutex_);
      reason_ = reason;
      planned_.store(planned);
    }
  }

  bool handoff_requested() const {
    return handoff_requested_.load();
  }

  std::string reason() const {
    std::lock_guard<std::mutex> lock(reason_mutex_);
    return reason_;
  }

  void mark_automatic_handback(const std::string& reason) {
    std::lock_guard<std::mutex> lock(reason_mutex_);
    reason_ = "automatic handback after " + reason;
    planned_.store(true);
  }

  [[noreturn]] void finish() noexcept {
    try {
      std::cout << "[position hold] " << reason()
                << "; last valid TWIST2 position command remains active; "
                   "no automatic retry or process exit\n";
    } catch (...) {}
    for (;;) ::usleep(100000);
  }

  double Now() const noexcept {
    return std::chrono::duration<double>(Clock::now().time_since_epoch()).count();
  }

  int CheckMode(std::string& name) {
    std::string form;
    return switcher_->CheckMode(form, name);
  }

  int GetFsmId(int& id) { return loco_->GetFsmId(id); }

  bool StateValid() const {
    Clock::time_point received;
    const LowState state = snapshot(nullptr, &received);
    validate_state(state, kVelocityLimit, false, received, true);
    return true;
  }

  void PrepareInactiveWriter() {
    if (active_.load() ||
        owner_phase_ != regular_handoff::OwnerPhase::WriterStopped)
      throw std::logic_error("writer preparation requires stopped owner");
    if (!writer_) start_writer();
  }

  void CancelPreparedWriter() noexcept { if (!active_.load()) writer_.reset(); }

  bool EnablePreparedWriter(double observation_started) noexcept {
    const auto enabled_at = Clock::now();
    const double now = std::chrono::duration<double>(
        enabled_at.time_since_epoch()).count();
    if (!writer_ || active_.load() || !handoff_requested_.load() ||
        owner_phase_ != regular_handoff::OwnerPhase::WriterStopped ||
        !regular_handoff::FreshInterval(observation_started, now))
      return false;
    // No RPC, logging, allocation or mutex acquisition after the freshness
    // check. The thread was created inactive before the new CheckMode call.
    activated_at_ = enabled_at;
    owner_phase_ = regular_handoff::OwnerPhase::Holding;
    active_.store(true);
    return true;
  }

  int regular_fsm_id() const noexcept { return start_fsm_id_; }

  bool monitor_regular_handoff() {
    VerifiedRegularHandoffGate gate(start_fsm_id_);
    const double verify_deadline = Now() + 10.0;
    for (;;) {
      const auto observation = regular_handoff::Observe(*this);
      if (gate.Update(observation.finished, observation.mode_result,
                      observation.mode, observation.fsm_result,
                      observation.fsm_id,
                      observation.state_valid && observation.Fresh())) {
        publisher_.reset();
        owner_phase_ = regular_handoff::OwnerPhase::RegularVerified;
        std::fputs("[SHUTDOWN COMPLETE] Regular ai/FSM and fresh LowState "
                   "verified for a sampled continuous second\n", stdout);
        return true;
      }
      const bool delayed = Now() >= verify_deadline;
      if (delayed && observation.Fresh() && observation.mode_result == 0 &&
          observation.mode.empty() && regular_handoff::ResumeOnFreshEmpty(*this)) {
        std::fputs("[handoff fallback] new, fresh CheckMode confirmed an empty "
                   "service; resumed TWIST2 position hold\n", stdout);
        return false;
      }
      // Failed/slow RPC, ai, other service, invalid state: no writer restart.
      // Observe catches RPC exceptions and invalidates partial observations.
      ::usleep(delayed ? 100000 : 50000);
    }
  }

  void ProtectOwnerLifetime() noexcept {
    // This method is called before Controller/dependencies can unwind. It is
    // also applied to normal returns, so neither kind of exit drops an owner.
    if (owner_phase_ == regular_handoff::OwnerPhase::BeforeTakeover ||
        owner_phase_ == regular_handoff::OwnerPhase::RegularVerified)
      return;
    handoff_requested_.store(true);  // no allocation in the recovery latch
    if (owner_phase_ == regular_handoff::OwnerPhase::Holding) finish();
    std::fputs("[handoff unverified] LowCmd remains stopped to prevent owner "
               "overlap; retaining this process and monitoring\n", stderr);
    for (;;) {
      try {
        if (monitor_regular_handoff()) return;
        finish();
      } catch (...) {
        // Includes errors outside RPC observation. Unknown ownership is never
        // turned into an unconditional LowCmd restart or process exit.
        ::usleep(100000);
      }
    }
  }

  bool verified_regular_handoff() {
    // An exception/refusal before stopping the writer keeps the current hold.
    bool settled = false;
    try {
      const auto deadline = Clock::now() + std::chrono::seconds(10);
      ContinuousObservationWindow window(1.0, 0.05);
      while (Clock::now() < deadline) {
        Clock::time_point received;
        const LowState state = snapshot(nullptr, &received);
        validate_state(state, kVelocityLimit, false, received, true);
        const WriterFrame command_frame = writer_frame();
        const double now = Now();
        bool stable = command_frame.valid && regular_handoff::FreshInterval(
            command_frame.write_returned_s, now, 0.02);
        for (std::size_t joint = 15; joint < kDofs; ++joint) {
          stable = stable &&
                   std::abs(state.motor_state()[joint].q() -
                            command_frame.target[joint]) <= PdReadySettle::error_limit &&
                   std::abs(state.motor_state()[joint].dq()) <= PdReadySettle::speed_limit;
        }
        if (window.Update(now, stable)) { settled = true; break; }
        ::usleep(10000);
      }
    } catch (...) { settled = false; }
    if (!settled) {
      std::fputs("[handoff refused] settle timeout/invalid state; current "
                 "TWIST2 writer remains active\n", stderr);
      return false;
    }

    active_.store(false);
    owner_phase_ = regular_handoff::OwnerPhase::WriterStopped;
    // Drain any write already inside the callback before mode selection.
    { std::lock_guard<std::mutex> lock(write_cycle_mutex_); }
    writer_.reset();
    try {
      const auto selected = switcher_->SelectMode("ai");
      if (selected != 0)
        std::fputs("[handoff] selection returned an error; observing owner\n", stderr);
    } catch (...) {
      std::fputs("[handoff] selection threw; observing owner without retry\n", stderr);
    }
    return monitor_regular_handoff();
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
      if(has_state_.load()&&!NativeStateTickAdvances(state_.tick(),incoming->tick()))return;
    state_ = *incoming;
      state_received_ = Clock::now();
    }
    has_state_.store(true);
  }

  Desired desired() const {
    std::lock_guard<std::mutex> lock(desired_mutex_);
    if (!has_desired_) {
      throw std::runtime_error("No desired command");
    }
    return desired_;
  }

  void write_cycle() {
    std::lock_guard<std::mutex> write_lock(write_cycle_mutex_);
    if (!active_.load()) {
      return;
    }
    const auto cycle_started = Clock::now();
    Clock::time_point received;
    const LowState state = snapshot(nullptr,&received);
    Desired command_desired = desired();
    if (!handoff_requested_.load()) {
      try {
        if(input_watchdog_&&!excitation_runtime_){const auto why=input_watchdog_();if(!why.empty())throw std::runtime_error(why);}
        validate_state(state, kVelocityLimit, false, received, true);
        if (!excitation_runtime_ && command_watchdog_expired(
                Clock::now(),
                command_desired.created,
                activated_at_,
                kCommandTimeout,
                kHandoffCommandGrace)) {
          throw std::runtime_error("50-Hz policy command stale");
        }
      } catch (const std::exception& error) {
        latch(std::string("RuntimeError: ") + error.what());
      }
    }

    std::optional<sysid_excitation::RuntimeSample> excitation_sample;
    if (excitation_runtime_) {
      try {
        if (handoff_requested_.load() &&
            excitation_runtime_->state() !=
                sysid_excitation::RuntimeState::kFaultHold) {
          excitation_runtime_->LatchFault("controller handoff requested");
        }
        excitation_sample = excitation_runtime_->Tick();
        if (!handoff_requested_.load()) {
          for (std::size_t arm = 0; arm < kRightArmDofs; ++arm) {
            command_desired.target[kRightArmBegin + arm] = static_cast<float>(
                excitation_sample->right_arm_target_q_rad[arm]);
          }
          command_desired.created = cycle_started;
        }
      } catch (const std::exception& error) {
        excitation_sample.reset();
        latch(std::string("RuntimeError: sysid excitation: ") + error.what());
      }
    }

    std::array<float,kDofs> kp{},kd{};
    {
      std::lock_guard<std::mutex> lock(gains_mutex_);
      kp=kp_;kd=kd_;
    }
    LowCmd command{};
    command.mode_pr() = kExpectedModePr;
    command.mode_machine() = state.mode_machine();
    std::uint64_t cycle_active_commands = 0;
    std::uint64_t cycle_limited_commands = 0;
    double cycle_predicted_torque_abs_max = 0.0;
    for (std::size_t i = 0; i < command.motor_cmd().size(); ++i) {
      auto& motor = command.motor_cmd()[i];
      motor.mode() = 1;
      motor.dq() = 0.0F;
      motor.tau() = 0.0F;
      if (i >= kDofs) {
        motor.q() = 0.0F;
        motor.kp() = 0.0F;
        motor.kd() = (i == 3 || i == 9) ? 2.0F : 1.0F;
        continue;
      }
      if (handoff_requested_.load()) {
        motor.q() = last_target_[i];
        motor.kp() = kp[i];
        motor.kd() = kd[i];
        continue;
      }

      const float rate = i < kLegDofs ? kLegTargetRate : cycle_speed(i);
      const float delta =
          rate * std::chrono::duration<float>(kLowCmdPeriod).count();
      float target = std::clamp(
          command_desired.target[i],
          last_target_[i] - delta,
          last_target_[i] + delta);
      target = std::clamp(
          target,
          kLower[i] + kJointLimitMargin,
          kUpper[i] - kJointLimitMargin);
      const float soft_torque = kTorqueLimit[i] * kSoftTorqueFraction;
      const float feedforward = std::clamp(
          command_desired.feedforward[i], -soft_torque, soft_torque);
      const float torque_without_position =
          -kd[i] * state.motor_state()[i].dq() + feedforward;
      const float lower_from_torque =
          state.motor_state()[i].q() +
          (-soft_torque - torque_without_position) / kp[i];
      const float upper_from_torque =
          state.motor_state()[i].q() +
          (soft_torque - torque_without_position) / kp[i];
      const float target_before_limit = target;
      target = std::clamp(target, lower_from_torque, upper_from_torque);
      if (std::abs(target - target_before_limit) > 1.0e-7F) {
        ++cycle_limited_commands;
      }
      target = std::clamp(
          target,
          kLower[i] + kJointLimitMargin,
          kUpper[i] - kJointLimitMargin);
      const double predicted_torque =
          kp[i] * (target - state.motor_state()[i].q()) -
          kd[i] * state.motor_state()[i].dq() + feedforward;
      cycle_predicted_torque_abs_max = std::max(
          cycle_predicted_torque_abs_max, std::abs(predicted_torque));
      ++cycle_active_commands;
      last_target_[i] = target;
      motor.q() = target;
      motor.kp() = kp[i];
      motor.kd() = kd[i];
      motor.tau() = feedforward;
    }
    command.crc() = crc32_core(
        reinterpret_cast<std::uint32_t*>(&command),
        (sizeof(LowCmd) >> 2U) - 1U);
    const auto write_begin = Clock::now();
    publisher_->Write(command);

    const auto sent = Clock::now();
    WriterFrame frame;
    const auto seconds=[](Clock::time_point t){return std::chrono::duration<double>(t.time_since_epoch()).count();};
    frame.trial_phase=command_desired.trial_phase;frame.trial_cycle=command_desired.trial_cycle;
    frame.state_tick=state.tick();
    frame.state_received_s=seconds(received);
    frame.cycle_started_s=seconds(cycle_started);
    frame.write_returned_s=seconds(sent);
    frame.desired_created_s=seconds(command_desired.created);
    for(std::size_t i=0;i<kDofs;++i){
      frame.q[i]=state.motor_state()[i].q();
      frame.dq[i]=state.motor_state()[i].dq();
      frame.tau_est[i]=state.motor_state()[i].tau_est();
      frame.target[i]=command.motor_cmd()[i].q();
      frame.target_dq[i]=command.motor_cmd()[i].dq();
      frame.kp[i]=command.motor_cmd()[i].kp();
      frame.kd[i]=command.motor_cmd()[i].kd();
      frame.tau_ff[i]=command.motor_cmd()[i].tau();
    }
    writer_frames_.Publish(frame);
    frame=writer_frames_.Read();
    if(sysid_log_){
      sysid::Frame observed;
      const auto ns=[](Clock::time_point t){return static_cast<std::uint64_t>(
          std::chrono::duration_cast<std::chrono::nanoseconds>(t.time_since_epoch()).count());};
      observed.target_ns=ns(command_desired.created);observed.write_begin_ns=ns(write_begin);
      observed.write_end_ns=ns(sent);observed.state_receive_ns=ns(received);
      observed.target_q=command_desired.target;observed.command_q=frame.target;
      observed.command_dq=frame.target_dq;observed.kp=frame.kp;observed.kd=frame.kd;
      observed.tau_ff=frame.tau_ff;observed.q=frame.q;observed.dq=frame.dq;observed.tau=frame.tau_est;
      observed.hold=handoff_requested_.load();
      for(std::size_t i=0;i<kDofs;++i){observed.temperature[i]=static_cast<float>(state.motor_state()[i].temperature()[0]);
        observed.status[i]=state.motor_state()[i].motorstate();}
      for(std::size_t i=0;i<3;++i){observed.rpy[i]=state.imu_state().rpy()[i];
        observed.gyro[i]=state.imu_state().gyroscope()[i];observed.accel[i]=state.imu_state().accelerometer()[i];}
      if(excitation_sample)
        sysid_excitation::AttachObserverTag(*excitation_sample,*excitation_context_,observed);
      (void)sysid_log_->Offer(observed); // no throw; losses invalidate receipt
    }
    if(response_log_){
      RealResponseFrame response;response.writer=frame;
      response.state=handoff_requested_.load()?"hold":"active";
      for(std::size_t i=0;i<7;++i){const auto joint=i+22;response.original_target[i]=command_desired.target[joint];
        response.temperature_c[i]=static_cast<float>(state.motor_state()[joint].temperature()[0]);
        response.motor_status[i]=state.motor_state()[joint].motorstate();}
      const auto& rpy=state.imu_state().rpy();const auto& gyro=state.imu_state().gyroscope();
      for(std::size_t i=0;i<3;++i){response.imu_rpy[i]=rpy[i];response.imu_gyroscope[i]=gyro[i];}
      response_log_->Append(response);
    }
    std::lock_guard<std::mutex> lock(stats_mutex_);
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

  regular_handoff::OwnerPhase owner_phase_{regular_handoff::OwnerPhase::BeforeTakeover};
  std::mutex write_cycle_mutex_;
  std::function<std::string()> input_watchdog_;
  WriterFrameStore writer_frames_;
  std::unique_ptr<RealResponseLog> response_log_;
  std::unique_ptr<sysid::Observer> sysid_log_;
  std::unique_ptr<sysid_excitation::Runtime> excitation_runtime_;
  std::optional<sysid::ExcitationContext> excitation_context_;
  std::string sysid_path_;
  mutable std::mutex state_mutex_;
  LowState state_{};
  Clock::time_point state_received_{};
  std::atomic<bool> has_state_{false};
  std::array<float, kDofs> capture_q_{};
  std::array<float, kDofs> capture_tau_{};
  bool capture_ready_{false};
  std::array<float, kDofs> last_target_{};

  mutable std::mutex desired_mutex_;
  Desired desired_{};
  bool has_desired_{false};

  unitree::robot::ChannelPublisherPtr<LowCmd> publisher_;
  unitree::robot::ChannelSubscriberPtr<LowState> subscriber_;
  std::unique_ptr<unitree::robot::b2::MotionSwitcherClient> switcher_;
  std::unique_ptr<unitree::robot::g1::LocoClient> loco_;
  int start_fsm_id_{-1};
  int start_balance_mode_{-1};
  unitree::common::ThreadPtr writer_;

  std::atomic<bool> active_{false};
  Clock::time_point activated_at_{};
  mutable std::mutex gains_mutex_;
  std::array<float,kDofs> kp_,kd_;
  std::atomic<bool> handoff_requested_{false};
  std::atomic<bool> planned_{false};
  mutable std::mutex reason_mutex_;
  std::string reason_{"not started"};

  mutable std::mutex stats_mutex_;
  std::uint64_t write_count_{0};
  Clock::time_point first_write_{};
  Clock::time_point last_write_{};
  std::vector<double> intervals_ms_;
  double max_handler_ms_{0.0};
  std::uint64_t active_joint_commands_{0};
  std::uint64_t torque_limited_commands_{0};
  double predicted_torque_abs_max_{0.0};
};

std::string csv_header() {
  std::ostringstream stream;
  stream
      << "elapsed_s,phase,alpha,arm_alpha,state_age_ms,inference_ms,"
         "roll_rad,pitch_rad";
  for (std::size_t i = 0; i < kDofs; ++i) {
    stream << ",action_" << i << ",q_" << i << ",dq_" << i
           << ",tau_est_" << i << ",desired_target_" << i
           << ",mimic_target_" << i;
  }
  WriterFrameHeader(stream);
  stream << '\n' << std::setprecision(17);
  return stream.str();
}

void write_csv_sample(std::ostream& stream, const Sample& sample) {
    stream << std::setprecision(17);

    stream << sample.elapsed_s << ',' << sample.phase << ',' << sample.alpha
           << ',' << sample.arm_alpha << ',' << sample.state_age_ms << ','
           << sample.inference_ms << ',' << sample.roll << ','
           << sample.pitch;
    for (std::size_t i = 0; i < kDofs; ++i) {
      stream << ',' << sample.action[i] << ',' << sample.position[i] << ','
             << sample.velocity[i] << ',' << sample.estimated_torque[i] << ','
             << sample.target[i] << ',' << sample.mimic_target[i];
    }
    WriterFrameRow(stream,sample.writer_frame);
    stream << '\n';
}

}  // namespace

int main(int argc, char** argv) {
  std::signal(SIGINT, signal_handler);
  std::signal(SIGTERM, signal_handler);
  try {
    const std::string selected_profile=std::getenv("G1_MINK_SPEED_PROFILE")?std::getenv("G1_MINK_SPEED_PROFILE"):"";
    if(selected_profile!="today"&&selected_profile!="yesterday")throw std::runtime_error("explicit yesterday/today profile required");
    std::cout<<"[CYCLE] profile="<<selected_profile<<"; measured speed guard = selected right-arm cap + 0.8 rad/s; pinch returns; recoverable input faults return home while TWIST2 remains the command owner\n";
    const bool default_duration =
        argc == 4 && std::string(argv[3]) == "--enable-actuation";
    const bool explicit_duration =
        argc == 6 && std::string(argv[3]) == "--enable-actuation" &&
        std::string(argv[4]) == "--policy-seconds";
    const bool right_arm_motion =
        argc == 8 && std::string(argv[3]) == "--enable-actuation" &&
        std::string(argv[4]) == "--policy-seconds" &&
        std::string(argv[6]) == "--right-shoulder-forward-deg";
    const bool pd_sweep = argc>=7 && std::string(argv[6])=="--pd-sweep-trial";
    const bool handoff_only = argc>=7 && std::string(argv[6])=="--handoff-only-trial";
    const bool pd_trial = argc>=7 &&
        (std::string(argv[6])=="--pd-reach-trial"||pd_sweep);
    const bool controlled_trial=pd_trial||handoff_only;
    const bool keyboard_right_arm = argc>=7 && std::string(argv[3])=="--enable-actuation" &&
        std::string(argv[4])=="--policy-seconds" && (std::string(argv[6])=="--udp-right-arm" || controlled_trial);
    if(!keyboard_right_arm)throw std::runtime_error("Use --enable-actuation --policy-seconds 300 with --udp-right-arm, --pd-reach-trial, --pd-sweep-trial, or --handoff-only-trial");
    auto gains=ParsePdGainOptions(argc,argv,kKp,kKd);
    if(pd_sweep)for(std::size_t i=22;i<26;++i){gains.kp[i]=40.F;gains.kd[i]=5.F;}
    if (!default_duration && !explicit_duration && !right_arm_motion &&
        !keyboard_right_arm) {
      std::cerr
          << "Usage: " << argv[0]
          << " eth0 /absolute/twist2_1017_20k_torchscript.pt "
             "--enable-actuation [--policy-seconds 2..20 "
             "[--right-shoulder-forward-deg 30]]\n"
          << "       " << argv[0]
          << " eth0 /absolute/twist2_1017_20k_torchscript.pt "
             "--enable-actuation --policy-seconds 300 "
             "--udp-right-arm\n";
      return 2;
    }
    double policy_seconds = kDefaultPolicySeconds;
    if (explicit_duration || right_arm_motion || keyboard_right_arm) {
      std::size_t parsed = 0;
      const std::string duration_text(argv[5]);
      policy_seconds = std::stod(duration_text, &parsed);
      const double maximum_duration =
          keyboard_right_arm
              ? kKeyboardPolicySeconds
              : kMaximumPolicySeconds;
      if (parsed != duration_text.size() ||
          !std::isfinite(policy_seconds) ||
          policy_seconds < kMinimumPolicySeconds ||
          policy_seconds > maximum_duration) {
        throw std::runtime_error(
            keyboard_right_arm
                ? "keyboard mode requires --policy-seconds 300"
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
    if (keyboard_right_arm) {
      if (std::abs(policy_seconds - kKeyboardPolicySeconds) > 1.0e-9) {
        throw std::runtime_error(
            "keyboard mode requires exactly --policy-seconds 300");
      }
      if (::isatty(STDIN_FILENO) != 1) {
        throw std::runtime_error(
            "keyboard mode requires an interactive terminal on stdin");
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
           "TWIST2 legs " << policy_seconds
        << " s -> safe-waypoint return -> TWIST2 position hold\n";
    if (handoff_only) {
      std::cout<<"[HANDOFF ONLY] Keep captured upper-body references; blend the legs into TWIST2 for 4 s after 1 s capture, then request verified Regular ai/FSM handoff. No arm trajectory and no UDP input. This is NOT a whole-body no-motion test.\n";
    } else if (pd_trial) {
      if(pd_sweep)
        std::cout<<"[PD TRIAL] Move both arms to Mink ready pose, run the small-signal sweep, settle under the same owner, stop the LowCmd writer, then request and verify Regular ai/FSM handoff.\n";
      else
        std::cout<<"[PD TRIAL] Move both arms to Mink ready pose, then full forward reach/return, 3 cycles. No UDP input. Fixed reference for PD comparison; speed cap45 deg/s, acceleration cap10 rad/s^2; dq command stays zero. Completion holds the returned ready pose under the same TWIST2 owner.\n";
      std::cout << "[PD TRIAL] Reference move_seconds=" << PdReachReference::move_seconds
                << "; starts after both arms settle: error <=" << PdReadySettle::error_limit
                << " rad, speed <=" << PdReadySettle::speed_limit << " rad/s for "
                << PdReadySettle::window << " s; timeout=" << PdReadySettle::timeout << " s.\n";
      for (int joint=22; joint<29; ++joint) {
        std::cout << "[PD TRIAL] joint=" << joint << " kp=" << gains.kp[joint]
                  << " kd=" << gains.kd[joint] << '\n';
      }
      if(pd_sweep)std::cout<<"[PD SWEEP] one owner; proximal Kp=40,48,56 with Kd=5; joint 22 only, +8 deg -> -8 deg -> ready, three cycles per candidate; 20 deg/s and 60 deg/s^2 caps; wrist remains at configured gains.\n";
    } else if (keyboard_right_arm) {
      std::cout
          << "control: policy legs 0:12; waist held; "
             "right arm 7-DOF absolute Mink UDP; both arms initialize to Mink ready pose\n";
    } else {
      std::cout
          << "control: policy legs 0:12; captured waist and arms held\n";
    }
    if (right_arm_motion) {
      std::cout
          << "arm timeline: policy 0-10 s hold; policy 10-20 s "
             "right shoulder forward 30 deg S-curve\n";
    }
    if (keyboard_right_arm && !controlled_trial) {
      std::cout
          << "UDP timeline: blend, both-arm initial pose, then absolute right-arm input; 300 s total policy\n";
      std::cout<<"[UDP] Cycle candidate: pinch, Q, Select/B and valid-state faults use safe arm return; TWIST2 remains the full-body owner. No damping or automatic AI handoff. Wait for udp_ready.\n";
      std::cout<<"[UDP] Ctrl+C requests the same checked safe return and does not stop LowCmd or exit the process.\n";
    }
    std::cout
        << "Select/B requests safe-waypoint return; TWIST2 remains the command owner.\n"
        << "Type exactly '" << confirmation_phrase << "' to continue: ";
    std::string confirmation;
    std::getline(std::cin, confirmation);
    if (confirmation != confirmation_phrase) {
      std::cout << "[safety] cancelled before DDS initialization\n";
      return 2;
    }

    Controller controller(argv[1],gains);
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
          state, kPreflightVelocityLimit, true, received);
      if ((remote_buttons(state) & (kSelect | kB)) != 0U)
        throw std::runtime_error("Select/B pressed during warm-up");
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
        readiness_state, kPreflightVelocityLimit, true, readiness_received);
    if ((remote_buttons(readiness_state) & (kSelect | kB)) != 0U)
      throw std::runtime_error("Select/B pressed before handoff");
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
    // The protected owner scope below also covers post-loop artifacts and
    // handoff. An exception must not unwind an unresolved owner.
    ObservationHistory history;
    std::vector<double> inference_ms;
    std::vector<Sample> samples;
    const auto planned_policy_steps = static_cast<std::size_t>(
        std::ceil(
            (kCaptureSeconds + kBlendSeconds + policy_seconds) * 50.0)) +
        10U;
    inference_ms.reserve(planned_policy_steps);
    samples.reserve(planned_policy_steps);
    const auto csv_stamp=std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    const auto csv_directory=std::filesystem::current_path()/
        ("g1_twist2_trial_"+std::to_string(csv_stamp)+"_"+std::to_string(::getpid()));
    if(!std::filesystem::create_directory(csv_directory))
      throw std::runtime_error("CSV directory already exists");
    const auto csv_path=csv_directory/"policy.csv";
    PeriodicCsv<Sample> csv(csv_path.string(),csv_header(),write_csv_sample);
    std::cout<<"[CSV] periodic policy log: "<<csv_path<<std::endl;

    double action_abs_max = 0.0;
    double action_delta_abs_max = 0.0;
    double roll_abs_max = 0.0;
    double pitch_abs_max = 0.0;
    double right_shoulder_tracking_error_abs_max = 0.0;
    double right_shoulder_command_forward_abs_max = 0.0;
    double right_arm_tracking_error_abs_max = 0.0;
    std::array<float, kDofs> previous_action{};

    controller.capture(controller.snapshot());
    // Persist provenance before handoff, outside the real-time loops.
    const auto binary_sha=sha256sum(std::filesystem::read_symlink("/proc/self/exe"));
    const auto response_path=csv_directory/"real_response.jsonl";
    const auto response_session="g1-response-"+std::to_string(csv_stamp)+"-"+std::to_string(::getpid());
    controller.start_response_log(response_path.string(),response_session,binary_sha);
    const nlohmann::json run_manifest={
      {"schema","g1.pd.run.v1"},{"mode",handoff_only?"handoff_only":(pd_sweep?"pd_sweep":(pd_trial?"pd_reach":"udp"))},
      {"binary_sha256",binary_sha},
      {"policy_sha256",kExpectedPolicySha256},
      {"argv",std::vector<std::string>(argv,argv+argc)},
      {"cycle_speed_profile",selected_profile},
      {"kp",gains.kp},{"kd",gains.kd},{"capture_q",controller.capture_q()},
      {"reference",{{"move_seconds",PdReachReference::move_seconds},
                    {"coefficients",PdReachReference::coefficients},
                    {"timing_u",PdReachReference::timing_u},
                    {"timing_du",PdReachReference::timing_du}}},
      {"logging",{{"nominal_policy_hz",50},{"writer_hz",500},
                  {"all_writer_frames",false},{"tau_est_is_estimate",true},
                  {"state_pairing","state used to form command; not subsequent response"},
                  {"real_response_schema","g1.real-response.v1"},{"real_response_file","real_response.jsonl"}}},
      {"physical_context",nullptr}
    };
    {
      std::ofstream metadata;
      metadata.exceptions(std::ios::failbit|std::ios::badbit);
      metadata.open(csv_directory/"run.json");metadata<<run_manifest.dump(2)<<'\n';metadata.close();
    }
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
    if (keyboard_right_arm) {
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
    std::unique_ptr<TerminalKeyboard> keyboard;
    if (keyboard_right_arm) {
      keyboard = std::make_unique<TerminalKeyboard>();
      if(!controlled_trial)std::cout<<"[UDP] Cycle candidate: safe return or position-hold AI handback; no damping output. Wait for udp_ready.\n";
    }
    std::array<float, kDofs> keyboard_command = controller.capture_q();
    std::array<float, kDofs> keyboard_applied = controller.capture_q();
    int keyboard_speed_multiplier = 1;
    controller.set_capture_desired();
    const auto clock=[](){return std::chrono::duration<double>(Clock::now().time_since_epoch()).count();};
    std::array<double,29> baseline{};std::copy(controller.capture_q().begin(),controller.capture_q().end(),baseline.begin());
    auto udp_target=std::make_shared<MinkLiveCycleTarget>(baseline,clock(),clock,!controlled_trial);
    std::unique_ptr<NativeVrCycleUdp> udp;
    std::unique_ptr<PdReachTrial> trial;
    std::unique_ptr<PdSmallSignalTrial> small_trial;
    PdReadySettle pd_settle;
    double trial_started=-1;
    int pd_candidate=0;
    bool pd_active=controlled_trial;
    bool pd_sweep_completed=false;
    bool udp_enabled=false;
    if(pd_sweep)udp=std::make_unique<NativeVrCycleUdp>();
    const auto enable_udp=[&](){
      if(udp_enabled)return;
      if(!udp)udp=std::make_unique<NativeVrCycleUdp>();
      controller.set_input_watchdog([udp_target,clock,&controller](){
        Clock::time_point latest_received;const auto latest=controller.snapshot(nullptr,&latest_received);
        std::array<double,29> q{},dq{};for(size_t i=0;i<29;++i){q[i]=latest.motor_state()[i].q();dq[i]=latest.motor_state()[i].dq();}
        udp_target->Feedback(q,dq,std::chrono::duration<double>(latest_received.time_since_epoch()).count());
        return udp_target->Poll(clock());});
      udp_enabled=true;
    };
    if(!pd_active)enable_udp();
    return regular_handoff::RunOwnerProtected(controller, [&]() -> int {
    controller.start_writer();
    controller.handoff_and_activate();

    const auto started = Clock::now();
    auto next_policy = started + kPolicyPeriod;
    const double active_seconds =
        kCaptureSeconds + kBlendSeconds + policy_seconds;

    std::string automatic_ai_reason;
    bool policy_duration_return_requested = false;
    unsigned handled_operator_signals = gOperatorSignalCount.load();
    try {
      // ReleaseMode can take longer than the normal 60-ms policy watchdog.
      // Refresh the already safe capture command immediately after handoff;
      // the writer permits only the bounded handoff grace before this update.
      controller.set_capture_desired();
      while (!controller.handoff_requested()) {
        const auto now = Clock::now();
        const double elapsed =
            std::chrono::duration<double>(now - started).count();
        const unsigned operator_signals = gOperatorSignalCount.load();
        if (operator_signals != handled_operator_signals) {
          handled_operator_signals = operator_signals;
          if (pd_active) {
            controller.latch("operator signal", true);
            break;
          }
          udp_target->RequestAutomaticHandback(
              "operator Ctrl+C safe return");
          std::cout
              << "\n[operator] Ctrl+C requested a checked safe return; "
                 "LowCmd remains active and the process will not exit\n";
        }
        if (elapsed >= active_seconds && !policy_duration_return_requested) {
          if(keyboard_right_arm&&!pd_active)
            udp_target->RequestAutomaticHandback("planned policy duration completed");
          else {
            controller.latch("planned policy duration completed", true);
            break;
          }
          policy_duration_return_requested = true;
        }
        if (now < next_policy) {
          std::this_thread::sleep_until(next_policy);
          continue;
        }

        double state_age_ms = 0.0;
        Clock::time_point received;
      const LowState state = controller.snapshot(&state_age_ms,&received);
        controller.validate_state(state, kVelocityLimit, false, received, true);
        if((remote_buttons(state)&(kSelect|kB))!=0U){
          if(pd_active)controller.latch("Select/B stop requested",true);
          else udp_target->RequestAutomaticHandback("Select/B requested");
        }
        if(!pd_active){
          for(std::size_t i=kRightArmBegin;i<kRightArmBegin+kRightArmDofs;++i){
            const float q=state.motor_state()[i].q();
            if(q<kLower[i]+kRightArmReturnApproachMargin ||
               q>kUpper[i]-kRightArmReturnApproachMargin){
              udp_target->RequestAutomaticHandback(
                  "right arm joint limit approach joint="+std::to_string(i));
              break;
            }
          }
        }

        float alpha = 0.0F;
        float arm_alpha = 0.0F;
        std::string phase = "capture";
        int trial_phase=0,trial_cycle=0;
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
        if (keyboard_right_arm) {
          for(const char key:keyboard->read_available()){
            if(key=='q'||key=='Q'){
              if(pd_active)controller.latch("keyboard stop requested",true);
              else {
                std::cout << "\n[Q SAFE HOLD] Automatic Regular/AI handoff "
                             "is disabled after the controller-overlap "
                             "incident. Returning through the safe waypoint; "
                             "TWIST2 will remain the command owner.\n";
                udp_target->RequestAutomaticHandback(
                    "operator Q safe hold");
              }
            }else if(key=='p'||key=='P'){
              if(pd_active)controller.latch("keyboard stop requested",true);
              else udp_target->RequestAutomaticHandback("keyboard return requested");
            }
          }
          if(handoff_only&&alpha>=1.0F){
            controller.latch("handoff-only completed",true);
            break;
          }
          if(controller.handoff_requested())break;
          std::array<double,29> applied=baseline;
          if(pd_active){
            std::array<double,29> measured_q{},measured_dq{};
            for(size_t i=0;i<29;++i){
              measured_q[i]=state.motor_state()[i].q();
              measured_dq[i]=state.motor_state()[i].dq();
            }
            udp_target->Feedback(measured_q,measured_dq,
                std::chrono::duration<double>(received.time_since_epoch()).count());
            if(!trial&&!small_trial){
              applied=udp_target->Update(clock(),alpha>=1.0F);
              if(alpha>=1.0F)phase="arm_initializing";
              if(udp_target->Ready()){
                phase="pd_settling";
                const double receipt=std::chrono::duration<double>(received.time_since_epoch()).count();
                if(pd_settle.Update(clock(),receipt,measured_q,measured_dq,applied)){
                  if(pd_sweep)small_trial=std::make_unique<PdSmallSignalTrial>(applied);
                  else trial=std::make_unique<PdReachTrial>(applied);
                  trial_started=elapsed;
                }
              }
            }
            if(trial||small_trial){
              const auto point=small_trial?small_trial->At(elapsed-trial_started):trial->At(elapsed-trial_started);
              applied=point.q;trial_phase=point.phase;trial_cycle=point.cycle;
              if(point.phase==6){
                if(pd_sweep&&pd_candidate<2){
                  ++pd_candidate;
                  const float next_kp=pd_candidate==1?48.F:56.F;
                  controller.set_proximal_pd(next_kp,5.F);
                  small_trial=std::make_unique<PdSmallSignalTrial>(applied);
                  trial_started=elapsed;
                  std::cout<<"\n[PD SWEEP] candidate="<<pd_candidate
                           <<" proximal Kp="<<next_kp<<" Kd=5 begins from ready pose\n";
                }else if(pd_sweep){
                  pd_sweep_completed=true;
                  controller.latch("pd sweep completed",true);
                  break;
                }else{
                  controller.latch("pd trial completed",true);break;
                }
              }
              phase="pd_trial_"+std::to_string(point.phase);
            }
          }else{
            std::array<double,29> measured_q{},measured_dq{};
            for(size_t i=0;i<29;++i){measured_q[i]=state.motor_state()[i].q();measured_dq[i]=state.motor_state()[i].dq();}
            udp_target->Feedback(measured_q,measured_dq,std::chrono::duration<double>(received.time_since_epoch()).count());
            udp->Drain(*udp_target,clock);
            applied=udp_target->Update(clock(),alpha>=1.0F);
            udp->Ack(*udp_target);
            if(udp_target->AutomaticHandbackReady()){
              automatic_ai_reason=udp_target->AutomaticHandbackReason();
              if(!udp_target->ContinueFromSafeHold())
                throw std::runtime_error("safe-hold continuation failed");
              std::cout << "\n[safe hold] return complete after '"
                        << automatic_ai_reason
                        << "'; TWIST2 remains the single owner; re-engage is allowed\n";
              automatic_ai_reason.clear();
            }
          }
          for(std::size_t i=12;i<29;++i){
            upper_target[i]=static_cast<float>(applied[i]);
            if(std::abs(state.motor_state()[i].q()-upper_target[i])>kKeyboardTrackingErrorLimit)
              throw std::runtime_error("upper measured tracking error exceeded 0.25 rad");
            if(std::abs(state.motor_state()[i].dq())>cycle_measured_speed_limit(i))
              throw std::runtime_error("upper measured velocity exceeded selected profile plus 0.8 rad/s margin");
          }
          if(!pd_active&&alpha>=1.0F)phase=udp_target->Phase();
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
        desired.trial_phase=trial_phase;desired.trial_cycle=trial_cycle;
        desired.created = Clock::now();
        for (std::size_t i = 0; i < kDofs; ++i) {
          desired.target[i] =
              (1.0F - alpha) * controller.capture_q()[i] +
              alpha * full_policy_target[i];
          desired.feedforward[i] =
              (1.0F - alpha) * controller.capture_tau()[i];
        }
        controller.set_desired(desired);
        const auto applied = target_as_action(desired.target);
        history.commit(result.current, applied);

        Sample sample;
        sample.writer_frame=controller.writer_frame();
        sample.elapsed_s = elapsed;
        sample.phase = phase;
        sample.alpha = alpha;
        sample.arm_alpha = arm_alpha;
        sample.state_age_ms = state_age_ms;
        sample.inference_ms = result.inference_ms;
        sample.roll = state.imu_state().rpy()[0];
        sample.pitch = state.imu_state().rpy()[1];
        sample.action = result.action;
        sample.target = desired.target;
        sample.mimic_target = mimic_target;
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
        if (right_arm_motion || keyboard_right_arm) {
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
        if (keyboard_right_arm) {
          for (std::size_t arm = 0; arm < kRightArmDofs; ++arm) {
            const std::size_t joint = kRightArmBegin + arm;
            right_arm_tracking_error_abs_max = std::max(
                right_arm_tracking_error_abs_max,
                std::abs(static_cast<double>(
                    sample.position[joint] - sample.target[joint])));
          }
        }
        csv.Append(sample);
        samples.push_back(sample);
        roll_abs_max = std::max(
            roll_abs_max, std::abs(static_cast<double>(sample.roll)));
        pitch_abs_max = std::max(
            pitch_abs_max, std::abs(static_cast<double>(sample.pitch)));
        const std::size_t console_period =
            keyboard_right_arm ? 50U : 10U;
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
    } catch (const std::exception& error) {
      controller.latch(std::string("RuntimeError: ") + error.what());
    }

    std::cout << '\n';
    if(controller.handoff_requested()){
      std::cout << "[safe hold] controller fault '" << controller.reason()
                << "'; automatic AI handoff is disabled to prevent a damping transition\n";
      // The persistent owner intentionally never returns from finish().  Seal
      // the comparison artifacts first so a completed PD run remains usable
      // even though the LowCmd hold continues until a successor owner exists.
      const bool artifacts_sealed = regular_handoff::TryArtifact([&]() {
      csv.Finish();controller.finish_response_log();
      const nlohmann::json persistent_result={{"schema","g1.pd.result.v1"},
        {"reason",controller.reason()},
        {"completed_reach",pd_trial&&(controller.reason()=="pd trial completed"||controller.reason()=="pd sweep completed")},
        {"csv_sha256",sha256sum(csv_path)},
        {"run_sha256",sha256sum(csv_directory/"run.json")},
        {"policy_samples",samples.size()},
        {"pd_sweep_completed",pd_sweep_completed},
        {"owner_state","persistent_twist2_position_hold"},
        {"record_kind","pre_handoff_checkpoint"}};
      {
        std::ofstream metadata;
        metadata.exceptions(std::ios::failbit|std::ios::badbit);
        metadata.open(csv_directory/"result.json");
        metadata<<persistent_result.dump(2)<<'\n';metadata.close();
      }
      });
      if (!artifacts_sealed)
        std::fputs("[artifact error] sealing/hash/result failed; ownership is "
                   "retained and planned handoff processing continues\n", stderr);
      if(controller.reason()=="pd sweep completed"||
         controller.reason()=="handoff-only completed"){
        const bool verified = controller.verified_regular_handoff();
        const bool outcome_recorded = regular_handoff::TryArtifact([&]() {
          std::ofstream outcome;
          outcome.exceptions(std::ios::failbit | std::ios::badbit);
          outcome.open(csv_directory / "handoff.json");
          const nlohmann::json result={
              {"schema","g1.regular.handoff.v1"},
              {"owner_state",verified ? "regular_ai_verified" : "persistent_twist2_position_hold"},
              {"expected_fsm",controller.regular_fsm_id()},
              {"artifacts_sealed",artifacts_sealed},
              {"physical_safety_validated",false}};
          outcome << result.dump(2) << '\n';
          outcome.close();
        });
        if (!outcome_recorded)
          std::fputs("[artifact error] handoff.json could not be recorded\n", stderr);
        if (verified) return artifacts_sealed && outcome_recorded ? 0 : 1;
      }
      controller.finish();
    }
    csv.Finish();controller.finish_response_log();
    {
      const nlohmann::json result={{"schema","g1.pd.result.v1"},
        {"reason",controller.reason()},
        {"completed_reach",pd_trial&&(controller.reason()=="pd trial completed"||controller.reason()=="pd sweep completed")},
        {"csv_sha256",sha256sum(csv_path)},
        {"run_sha256",sha256sum(csv_directory/"run.json")},
        {"policy_samples",samples.size()},
        {"pd_sweep_completed",pd_sweep_completed}};
      std::ofstream metadata;
      metadata.exceptions(std::ios::failbit|std::ios::badbit);
      metadata.open(csv_directory/"result.json");metadata<<result.dump(2)<<'\n';metadata.close();
    }
    const bool completed_duration =
        (controller.reason() == "planned policy duration completed" ||
         controller.reason() == "pd trial completed" ||
         controller.reason() == "pd sweep completed");
    const bool operator_stop =
        controller.reason() == "keyboard stop requested";
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
                      : (operator_stop ? "operator_stop" : "position_hold"))
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
              << "  \"csv_path\": \"" << csv_path.string() << "\",\n"
              << "  \"automatic_ai_handoff_enabled\": false,\n"
              << "  \"twist2_position_hold_requested\": " << (controller.handoff_requested()?"true":"false") << ",\n";
    controller.print_stats();
    std::cout << "}\n";
    std::cout << "[position hold] no damping command or automatic AI handoff was issued\n";
    return completed ? 0 : 1;
    });  // owner remains alive throughout exception recovery
  } catch (const c10::Error& error) {
    std::cerr << "[fatal] Torch error: "
              << error.what_without_backtrace() << '\n';
  } catch (const std::exception& error) {
    std::cerr << "[fatal] " << error.what() << '\n';
  }
  return 1;
}
