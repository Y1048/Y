#include "velocity_keypad_contract.hpp"
#include <iostream>
#include <stdexcept>

void Require(bool value, const char* message) {
  if (!value) throw std::runtime_error(message);
}

int main() {
  VelocityKeypadContract contract;
  const std::string token = "0123456789abcdef";
  auto make = [&](std::uint64_t sequence, float x) {
    nlohmann::json value = {
      {"schema", "g1.velocity.keypad.v1"},
      {"command_provenance", "unity_keypad"},
      {"simulation_only", false}, {"session", "session-a"},
      {"sequence", sequence}, {"source_monotonic_s", 12.5},
      {"velocity", {x, 0.0F, 0.0F}}, {"relay_token", token}};
    return value.dump();
  };
  Require(contract.Parse(make(1, 0.8F), token).velocity[0] == 0.8F,
          "keypad packet rejected");
  bool duplicate_rejected = false;
  try { contract.Parse(make(1, 0.0F), token); }
  catch (const std::runtime_error&) { duplicate_rejected = true; }
  Require(duplicate_rejected, "duplicate accepted");
  bool range_rejected = false;
  try { contract.Parse(make(2, 0.81F), token); }
  catch (const std::runtime_error&) { range_rejected = true; }
  Require(range_rejected, "range accepted");
  contract.Reset();
  Require(contract.Parse(make(0, 0.0F), token).sequence == 0,
          "reset failed");
  contract.Reset();
  nlohmann::json omni = {
      {"schema", "g1.velocity.command.v1"},
      {"command_provenance", "omni_gateway"},
      {"simulation_only", false}, {"session", "omni-session"},
      {"sequence", 0}, {"source_monotonic_s", 13.0},
      {"velocity", {0.1F, -0.2F, 0.3F}}, {"relay_token", token}};
  Require(contract.Parse(omni.dump(), token).velocity[2] == 0.3F,
          "Omni packet rejected");
  std::cout << "velocity command contract: PASS\n";
}
