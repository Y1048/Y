#include "verified_regular_handoff.hpp"

#include <cstdlib>
#include <iostream>
#include <limits>

void Check(bool value, const char* message) {
  if (!value) { std::cerr << "FAIL: " << message << '\n'; std::exit(1); }
}

void Complete(VerifiedRegularHandoffGate& gate, double start, int fsm = 501) {
  for (int i = 0; i < 10; ++i)
    Check(!gate.Update(start + i * 0.1, 0, "ai", 0, fsm, true), "full window required");
  Check(gate.Update(start + 1.0, 0, "ai", 0, fsm, true), "sampled stable second");
}

int main() {
  for (int fsm : {500, 501}) {
    VerifiedRegularHandoffGate gate(fsm);
    Complete(gate, 0.0, fsm);
  }
  {
    VerifiedRegularHandoffGate gate(501);
    Check(!gate.Update(0.0, 0, "ai", 0, 501, true), "initial");
    Check(!gate.Update(5.0, 0, "ai", 0, 501, true), "5 s gap must reset");
    for (int i = 1; i < 10; ++i)
      Check(!gate.Update(5.0 + i * .1, 0, "ai", 0, 501, true), "restart after gap");
    Check(gate.Update(6.0, 0, "ai", 0, 501, true), "new continuous window");
  }
  for (int fault = 0; fault < 5; ++fault) {
    VerifiedRegularHandoffGate gate(501);
    for (int i = 0; i < 8; ++i) gate.Update(i * .1, 0, "ai", 0, 501, true);
    Check(!gate.Update(.8, fault == 0 ? -1 : 0, fault == 1 ? "" : "ai",
                       fault == 2 ? -1 : 0, fault == 3 ? 500 : 501, fault != 4),
          "bad observation resets");
    Complete(gate, 1.0);
  }
  for (double bad : {std::numeric_limits<double>::quiet_NaN(),
                     std::numeric_limits<double>::infinity(), -1.0, .5, .7}) {
    VerifiedRegularHandoffGate gate(501);
    for (int i = 0; i < 8; ++i) gate.Update(i / 10.0, 0, "ai", 0, 501, true);
    Check(!gate.Update(bad, 0, "ai", 0, 501, true), "invalid/reverse/duplicate time");
    Complete(gate, 1.0);
  }
  {
    VerifiedRegularHandoffGate gate(501);
    gate.Update(0, 0, "ai", 0, 501, true);
    gate.Reset();
    Complete(gate, .1);
  }
  for (int fsm : {-1, 0, 499, 502}) {
    bool rejected = false;
    try { VerifiedRegularHandoffGate bad(fsm); }
    catch (const std::invalid_argument&) { rejected = true; }
    Check(rejected, "invalid expected FSM");
  }
  for (double window : {0.0, -1.0, .25, std::numeric_limits<double>::quiet_NaN()}) {
    bool rejected = false;
    try { VerifiedRegularHandoffGate bad(501, window); }
    catch (const std::invalid_argument&) { rejected = true; }
    Check(rejected, "invalid configured window");
  }
  std::cout << "PASS continuity, long gaps, invalid samples/clocks, configuration\n";
}
