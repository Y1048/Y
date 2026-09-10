#pragma once

#include <cmath>
#include <stdexcept>
#include <string>

// Sampled continuity, not proof of the unobserved state between samples.
class ContinuousObservationWindow {
 public:
  ContinuousObservationWindow(double stable_seconds, double maximum_gap)
      : stable_seconds_(stable_seconds), maximum_gap_(maximum_gap) {
    if (!std::isfinite(stable_seconds) || stable_seconds <= 0.0 ||
        !std::isfinite(maximum_gap) || maximum_gap <= 0.0 ||
        maximum_gap >= stable_seconds)
      throw std::invalid_argument("invalid observation window");
  }

  void Reset() noexcept { stable_since_ = previous_ = -1.0; }

  bool Update(double now, bool valid) noexcept {
    if (!valid || !std::isfinite(now) || now < 0.0 ||
        (previous_ >= 0.0 && now <= previous_)) {
      Reset();
      return false;
    }
    if (previous_ < 0.0 || now - previous_ > maximum_gap_) {
      stable_since_ = now;
      previous_ = now;
      return false;
    }
    previous_ = now;
    return now - stable_since_ >= stable_seconds_;
  }

 private:
  double stable_seconds_, maximum_gap_;
  double stable_since_{-1.0}, previous_{-1.0};
};

class VerifiedRegularHandoffGate {
 public:
  // Software candidate: 250 ms bounds the existing 50/100 ms polling paths.
  // RPC timing on the installed robot still requires separate validation.
  explicit VerifiedRegularHandoffGate(int expected_fsm,
                                      double stable_seconds = 1.0,
                                      double maximum_gap = 0.25)
      : expected_fsm_(expected_fsm), window_(stable_seconds, maximum_gap) {
    if (expected_fsm != 500 && expected_fsm != 501)
      throw std::invalid_argument("expected Regular FSM must be 500 or 501");
  }

  void Reset() noexcept { window_.Reset(); }

  bool Update(double now, int mode_result, const std::string& mode_name,
              int fsm_result, int fsm_id, bool state_valid) noexcept {
    return window_.Update(now, mode_result == 0 && mode_name == "ai" &&
                              fsm_result == 0 && fsm_id == expected_fsm_ &&
                              state_valid);
  }

 private:
  int expected_fsm_;
  ContinuousObservationWindow window_;
};
