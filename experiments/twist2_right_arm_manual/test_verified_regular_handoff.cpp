#include "verified_regular_handoff.hpp"

#include <cstdlib>
#include <iostream>

void Check(bool value, const char* message) {
  if (!value) {
    std::cerr << "FAIL: " << message << '\n';
    std::exit(1);
  }
}

int main() {
  {
    VerifiedRegularHandoffGate gate(501);
    Check(!gate.Update(0.0, 0, "ai", 0, 501, true), "first valid sample");
    Check(!gate.Update(0.9, 0, "ai", 0, 501, true), "requires full second");
    Check(gate.Update(1.0, 0, "ai", 0, 501, true), "continuous stable second");
  }
  {
    VerifiedRegularHandoffGate gate(501);
    Check(!gate.Update(0.0, 0, "ai", 0, 501, true), "start stability");
    Check(!gate.Update(0.8, 0, "ai", 0, 500, true), "wrong FSM resets");
    Check(!gate.Update(1.0, 0, "ai", 0, 501, true), "restart after reset");
    Check(!gate.Update(1.8, 0, "ai", 0, 501, true), "new window incomplete");
    Check(gate.Update(2.0, 0, "ai", 0, 501, true), "new stable window");
  }
  {
    VerifiedRegularHandoffGate gate(501);
    Check(!gate.Update(0.0, 1, "ai", 0, 501, true), "mode result required");
    Check(!gate.Update(0.0, 0, "", 0, 501, true), "ai service required");
    Check(!gate.Update(0.0, 0, "ai", 1, 501, true), "FSM result required");
    Check(!gate.Update(0.0, 0, "ai", 0, 501, false), "valid state required");
  }
  std::cout << "PASS verified Regular handoff gate\n";
}
