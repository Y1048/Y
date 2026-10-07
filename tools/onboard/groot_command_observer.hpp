#pragma once
// Observation only: no SDK dependency, sockets, publisher, or command mutation.
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <limits>
#include <string>
#include <thread>

namespace groot_observer {
static_assert(std::atomic<std::size_t>::is_always_lock_free &&
              std::atomic<std::uint64_t>::is_always_lock_free &&
              std::atomic<bool>::is_always_lock_free,
              "observer requires lock-free counters on this platform");
inline std::int64_t monotonic_ns() noexcept {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count();
}
struct Sample {
  std::uint64_t writer_sequence{}, input_sequence{};
  std::int64_t target_created_ns{}, input_observed_ns{}, state_received_ns{};
  std::int64_t write_begin_ns{}, write_end_ns{};
  double input_source_timestamp{}; // Opaque producer timestamp; not clock-aligned.
  bool input_valid{}, arms_specified{}, arms_active{}, state_available{};
  bool safe_stand{}, damping{};
  std::array<float, 14> received_arm_q{};
  std::array<float, 29> target_q{}, sent_q{}, sent_dq{}, kp{}, kd{}, tau_ff{};
  std::array<float, 29> measured_q{}, measured_dq{}, tau_est{};
};
inline bool finite(const Sample& s) noexcept {
  if (!std::isfinite(s.input_source_timestamp)) return false;
  for (float x : s.received_arm_q) if (!std::isfinite(x)) return false;
  for (const auto* a : {&s.target_q, &s.sent_q, &s.sent_dq, &s.kp, &s.kd,
                        &s.tau_ff, &s.measured_q, &s.measured_dq, &s.tau_est})
    for (float x : *a) if (!std::isfinite(x)) return false;
  return true;
}
// Single producer (existing writer), single consumer. Fixed memory; producer
// never takes a mutex, allocates, waits, formats text, or accesses the file.
template <std::size_t Capacity> class Ring {
  static_assert(Capacity >= 2, "capacity must be >= 2");
 public:
  bool push(const Sample& s) noexcept {
    const auto w = write_.load(std::memory_order_relaxed);
    const auto next = (w + 1) % Capacity;
    if (next == read_.load(std::memory_order_acquire)) return false;
    data_[w] = s;
    write_.store(next, std::memory_order_release);
    return true;
  }
  bool pop(Sample* s) noexcept {
    const auto r = read_.load(std::memory_order_relaxed);
    if (r == write_.load(std::memory_order_acquire)) return false;
    *s = data_[r];
    read_.store((r + 1) % Capacity, std::memory_order_release);
    return true;
  }
 private:
  std::array<Sample, Capacity> data_{};
  std::atomic<std::size_t> write_{0}, read_{0};
};
class Logger {
 public:
  Logger() noexcept { // Explicit opt-in; unique filename, no overwrite.
    try {
      const char* directory = std::getenv("GROOT_COMMAND_OBSERVER_DIR");
      if (!directory || !*directory) return;
      path_ = std::string(directory) + "/groot_command_v1_" +
              std::to_string(monotonic_ns()) + ".csv";
      worker_ = std::thread(&Logger::consume, this);
    } catch (...) { errors_.fetch_add(1); }
  }
  ~Logger() { stop_.store(true); if (worker_.joinable()) worker_.join(); }
  Logger(const Logger&) = delete;
  Logger& operator=(const Logger&) = delete;
  bool enabled() const noexcept { return enabled_.load(); }
  void observe(const Sample& sample) noexcept {
    if (!enabled()) return;
    if (!finite(sample)) { invalid_.fetch_add(1); return; }
    if (!queue_.push(sample)) dropped_.fetch_add(1);
  }
  std::uint64_t dropped() const noexcept { return dropped_.load(); }
  std::uint64_t errors() const noexcept { return errors_.load(); }
 private:
  void consume() noexcept {
    try {
      std::ofstream out(path_);
      if (!out) { errors_.fetch_add(1); return; }
      out << "# schema=groot.command.observation.v1; clock=G1 std::chrono::steady_clock ns; q=rad; dq=rad/s; tau=Nm; kp=Nm/rad; kd=Nm*s/rad; motor_acceptance=unknown; input_source_clock=opaque; state_received=validated LowState cache time; sampling=existing periodic writer only (initial synchronous handoff excluded)\n";
      out << "writer_sequence,input_sequence,target_created_ns,input_observed_ns,state_received_ns,write_begin_ns,write_end_ns,input_source_timestamp,input_valid,arms_specified,arms_active,state_available,safe_stand,damping,dropped_total,invalid_total,nonmonotonic_total,gap_total";
      for (int i=15; i<29; ++i) out << ",received_q" << i;
      for (int i=0; i<29; ++i)
        for (const char* key : {"target_q", "sent_q", "sent_dq", "kp", "kd", "tau_ff", "measured_q", "measured_dq", "tau_est"})
          out << ',' << key << i;
      out << '\n' << std::setprecision(std::numeric_limits<double>::max_digits10);
      enabled_.store(true);
      std::uint64_t last_seq=0, nonmonotonic=0, gaps=0, rows=0;
      std::int64_t last_time=0;
      Sample s;
      for (;;) {
        if (!queue_.pop(&s)) {
          if (stop_.load()) break;
          std::this_thread::sleep_for(std::chrono::milliseconds(2));
          continue;
        }
        if (last_seq && (s.writer_sequence <= last_seq || s.write_begin_ns <= last_time)) ++nonmonotonic;
        if (last_seq && s.writer_sequence > last_seq + 1) gaps += s.writer_sequence-last_seq-1;
        last_seq=s.writer_sequence; last_time=s.write_begin_ns;
        out << s.writer_sequence << ',' << s.input_sequence << ',' << s.target_created_ns << ',' << s.input_observed_ns << ',' << s.state_received_ns << ',' << s.write_begin_ns << ',' << s.write_end_ns << ',' << s.input_source_timestamp << ',' << s.input_valid << ',' << s.arms_specified << ',' << s.arms_active << ',' << s.state_available << ',' << s.safe_stand << ',' << s.damping << ',' << dropped_.load() << ',' << invalid_.load() << ',' << nonmonotonic << ',' << gaps;
        for (float v : s.received_arm_q) out << ',' << v;
        for (int i=0; i<29; ++i)
          for (const auto* a : {&s.target_q, &s.sent_q, &s.sent_dq, &s.kp, &s.kd, &s.tau_ff, &s.measured_q, &s.measured_dq, &s.tau_est}) out << ',' << (*a)[i];
        out << '\n';
        if (++rows % 500 == 0) out.flush();
        if (!out) { errors_.fetch_add(1); break; }
      }
      enabled_.store(false);
      out << "# final dropped=" << dropped_.load() << " invalid=" << invalid_.load() << " errors=" << errors_.load() << '\n';
      out.flush();
      if (!out) errors_.fetch_add(1);
    } catch (...) { enabled_.store(false); errors_.fetch_add(1); }
  }
  Ring<256> queue_;
  std::string path_;
  std::thread worker_;
  std::atomic<bool> enabled_{false}, stop_{false};
  std::atomic<std::uint64_t> dropped_{0}, invalid_{0}, errors_{0};
};
} // namespace groot_observer
