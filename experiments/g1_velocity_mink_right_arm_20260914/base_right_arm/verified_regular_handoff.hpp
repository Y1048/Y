#pragma once

#include <string>

class VerifiedRegularHandoffGate {
 public:
  explicit VerifiedRegularHandoffGate(int expected_fsm,
                                      double stable_seconds = 1.0)
      : expected_fsm_(expected_fsm), stable_seconds_(stable_seconds) {}

  bool Update(double now, int mode_result, const std::string& mode_name,
              int fsm_result, int fsm_id, bool state_valid) {
    const bool valid = mode_result == 0 && mode_name == "ai" &&
                       fsm_result == 0 && fsm_id == expected_fsm_ &&
                       state_valid;
    if (!valid) {
      stable_since_ = -1.0;
      return false;
    }
    if (stable_since_ < 0.0) {
      stable_since_ = now;
      return false;
    }
    return now - stable_since_ >= stable_seconds_;
  }

 private:
  int expected_fsm_;
  double stable_seconds_;
  double stable_since_{-1.0};
};
