#pragma once

#include "vendor/json.hpp"

#include <array>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <string>

struct VelocityKeypadPacket {
  std::string session;
  std::uint64_t sequence{};
  double source_monotonic_s{};
  std::array<float, 3> velocity{};
};

class VelocityKeypadContract {
 public:
  void Reset() {
    have_packet_ = false;
    session_.clear();
    sequence_ = 0;
  }

  VelocityKeypadPacket Parse(const std::string& payload,
                             const std::string& relay_token) {
    const auto packet = nlohmann::json::parse(payload);
    const auto schema = packet.at("schema").get<std::string>();
    const auto provenance = packet.at("command_provenance").get<std::string>();
    const bool keypad = schema == "g1.velocity.keypad.v1" &&
                        provenance == "unity_keypad";
    const bool omni = schema == "g1.velocity.command.v1" &&
                      provenance == "omni_gateway";
    if ((!keypad && !omni) ||
        packet.value("simulation_only", true) ||
        packet.at("relay_token") != relay_token) {
      throw std::runtime_error("velocity relay binding");
    }
    VelocityKeypadPacket result;
    result.session = packet.at("session").get<std::string>();
    if (result.session.empty() || result.session.size() > 128U) {
      throw std::runtime_error("velocity session");
    }
    result.sequence = packet.at("sequence").get<std::uint64_t>();
    result.source_monotonic_s = packet.at("source_monotonic_s").get<double>();
    const auto values = packet.at("velocity").get<std::array<float, 3>>();
    constexpr std::array<float, 3> kLimits{0.80F, 0.80F, 0.80F};
    if (!std::isfinite(result.source_monotonic_s) ||
        result.source_monotonic_s < 0.0) {
      throw std::runtime_error("velocity timestamp");
    }
    for (std::size_t i = 0; i < values.size(); ++i) {
      if (!std::isfinite(values[i]) ||
          std::abs(values[i]) > kLimits[i] + 1.0e-6F) {
        throw std::runtime_error("velocity range");
      }
    }
    if (have_packet_) {
      if (result.session != session_) {
        throw std::runtime_error("velocity session changed");
      }
      if (result.sequence <= sequence_) {
        throw std::runtime_error("velocity sequence");
      }
    }
    have_packet_ = true;
    session_ = result.session;
    sequence_ = result.sequence;
    result.velocity = values;
    return result;
  }

 private:
  bool have_packet_{false};
  std::string session_;
  std::uint64_t sequence_{};
};
