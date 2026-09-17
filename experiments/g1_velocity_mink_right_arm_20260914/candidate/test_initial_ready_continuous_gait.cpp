#include "mink_live_cycle_target.hpp"

#include <cstdlib>
#include <iostream>

int main() {
  try {
#ifdef _WIN32
    _putenv_s("G1_MINK_SPEED_PROFILE", "today");
#else
    setenv("G1_MINK_SPEED_PROFILE", "today", 1);
#endif
    using C = MinkLiveCycleContract;
    C::Q q{}, dq{};
    constexpr double rad = 0.017453292519943295;
    const std::array<double, 14> pose = {
        10 * rad, 22 * rad, 0, 55 * rad, 0, 0, 0,
        10 * rad, -22 * rad, 0, 55 * rad, 0, 0, 0};
    for (std::size_t i = 15; i < 29; ++i) {
      q[i] = pose[i - 15];
      dq[i] = (i % 2 == 0) ? 0.30 : -0.30;
    }
    double now = 0.0;
    MinkLiveCycleTarget target(q, now, [&]() { return now; }, true);
    for (int step = 1; step <= 49; ++step) {
      now = step * 0.02;
      target.Feedback(q, dq, now);
      target.Update(now, true);
    }
    if (target.Ready()) {
      throw std::runtime_error("initial ready completed before full gait-cycle dwell");
    }
    for (int step = 50; step <= 60; ++step) {
      now = step * 0.02;
      target.Feedback(q, dq, now);
      target.Update(now, true);
    }
    if (!target.Ready() || target.Phase() != "udp_ready") {
      throw std::runtime_error("continuous-gait arm velocity blocked initial ready");
    }
    auto bad = q;
    bad[22] += C::ready_error[0] + 0.001;
    if (C::MeasuredInitialReadyJoint(bad[22], dq[22], q[22], 0)) {
      throw std::runtime_error("initial position error was accepted");
    }
    if (C::MeasuredReadyJoint(q[22], dq[22], q[22], 0)) {
      throw std::runtime_error("return velocity guard was weakened");
    }
    std::cout << "initial ready continuous gait: PASS\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
