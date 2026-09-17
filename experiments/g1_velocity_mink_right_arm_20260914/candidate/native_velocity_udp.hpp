#pragma once

#include "g1_velocity_policy.hpp"
#include "native_relay_contract.hpp"
#include "velocity_keypad_contract.hpp"

#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cerrno>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <string>

class NativeVelocityUdp {
 public:
  NativeVelocityUdp() {
    const char* bind_ip = std::getenv("G1_VELOCITY_BIND_IPV4");
    const char* source_ip = std::getenv("G1_VELOCITY_SOURCE_IPV4");
    const char* port_text = std::getenv("G1_VELOCITY_UDP_PORT");
    const char* token = std::getenv("G1_VELOCITY_RELAY_TOKEN");
    if (!token || !NativeRelayTokenValid(token)) {
      throw std::runtime_error("explicit velocity relay token required");
    }
    relay_token_ = token;
    if (!bind_ip || !port_text) {
      throw std::runtime_error("explicit velocity bind IPv4 and port required");
    }
    sockaddr_in bind_address{};
    bind_address.sin_family = AF_INET;
    if (inet_pton(AF_INET, bind_ip, &bind_address.sin_addr) != 1) {
      throw std::runtime_error("invalid velocity IPv4");
    }
    if (source_ip) {
      if (inet_pton(AF_INET, source_ip, &source_) != 1) {
        throw std::runtime_error("invalid velocity source IPv4");
      }
      source_locked_ = true;
    }
    const std::string port_string(port_text);
    std::size_t end = 0;
    const int port = std::stoi(port_string, &end);
    if (end != port_string.size() || port < 1024 || port > 65535) {
      throw std::runtime_error("invalid velocity port");
    }
    bind_address.sin_port = htons(static_cast<std::uint16_t>(port));
    socket_ = ::socket(AF_INET, SOCK_DGRAM | SOCK_NONBLOCK, 0);
    if (socket_ < 0) throw std::runtime_error("velocity socket failed");
    if (::bind(socket_, reinterpret_cast<sockaddr*>(&bind_address),
               sizeof(bind_address)) != 0) {
      ::close(socket_);
      socket_ = -1;
      throw std::runtime_error("velocity bind failed");
    }
    int broadcast = 1;
    if (setsockopt(socket_, SOL_SOCKET, SO_BROADCAST, &broadcast,
                   sizeof(broadcast)) != 0) {
      throw std::runtime_error("velocity broadcast setup failed");
    }
    velocity_port_ = port;
    const char* discovery_port_text = std::getenv("G1_VELOCITY_DISCOVERY_PORT");
    if (discovery_port_text) {
      const std::string discovery_port_string(discovery_port_text);
      std::size_t discovery_end = 0;
      discovery_port_ = std::stoi(discovery_port_string, &discovery_end);
      if (discovery_end != discovery_port_string.size()) {
        throw std::runtime_error("invalid velocity discovery port");
      }
    }
    if (discovery_port_ < 1024 || discovery_port_ > 65535) {
      throw std::runtime_error("invalid velocity discovery port");
    }
  }

  NativeVelocityUdp(const NativeVelocityUdp&) = delete;
  NativeVelocityUdp& operator=(const NativeVelocityUdp&) = delete;
  ~NativeVelocityUdp() { if (socket_ >= 0) ::close(socket_); }

  void Drain() {
    AnnounceIfDue();
    const auto before_receive = std::chrono::steady_clock::now();
    if (received_ && before_receive - last_received_ >
                         std::chrono::milliseconds(500)) {
      contract_.Reset();
    }
    for (int n = 0; n <= 64; ++n) {
      char data[2049];
      sockaddr_in sender{};
      socklen_t length = sizeof(sender);
      const auto size = recvfrom(socket_, data, sizeof(data), 0,
          reinterpret_cast<sockaddr*>(&sender), &length);
      if (size < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) break;
        throw std::runtime_error("velocity receive failed");
      }
      if (n == 64) throw std::runtime_error("velocity receive batch overflow");
      if (source_locked_ && sender.sin_addr.s_addr != source_.s_addr) {
        throw std::runtime_error("unexpected velocity sender");
      }
      const auto parsed = contract_.Parse(
          std::string(data, static_cast<std::size_t>(size)), relay_token_);
      if (!source_locked_) {
        source_ = sender.sin_addr;
        source_locked_ = true;
      }
      twist2::VelocityCommand::SetTarget(parsed.velocity);
      last_received_ = std::chrono::steady_clock::now();
      received_ = true;
    }
    if (received_ && std::chrono::steady_clock::now() - last_received_ >
                         std::chrono::milliseconds(250)) {
      twist2::VelocityCommand::Stop();
    }
  }

 private:
  void AnnounceIfDue() {
    const auto now = std::chrono::steady_clock::now();
    if (discovery_sent_ && now - last_discovery_ < std::chrono::seconds(1)) return;
    char hostname[128]{};
    if (gethostname(hostname, sizeof(hostname) - 1) != 0) {
      std::strcpy(hostname, "g1");
    }
    const nlohmann::json packet{
        {"schema", "g1.velocity.discovery.v1"},
        {"robot_id", std::string(hostname)},
        {"velocity_port", velocity_port_},
        {"sequence", discovery_sequence_++},
        {"relay_token", relay_token_}};
    const auto payload = packet.dump();
    sockaddr_in destination{};
    destination.sin_family = AF_INET;
    destination.sin_port = htons(static_cast<std::uint16_t>(discovery_port_));
    destination.sin_addr.s_addr = htonl(INADDR_BROADCAST);
    (void)sendto(socket_, payload.data(), payload.size(), 0,
                 reinterpret_cast<sockaddr*>(&destination), sizeof(destination));
    last_discovery_ = now;
    discovery_sent_ = true;
  }

  int socket_{-1};
  in_addr source_{};
  bool source_locked_{false};
  std::string relay_token_;
  int velocity_port_{5017};
  int discovery_port_{5018};
  std::uint64_t discovery_sequence_{0};
  bool discovery_sent_{false};
  std::chrono::steady_clock::time_point last_discovery_{};
  VelocityKeypadContract contract_;
  bool received_{false};
  std::chrono::steady_clock::time_point last_received_{};
};
