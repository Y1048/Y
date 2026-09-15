#include "sysid_excitation_observer_bridge.hpp"

#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <string>
#include <unistd.h>

namespace {

constexpr const char* kHashA =
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
constexpr const char* kHashB =
    "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

sysid_excitation::RuntimeSample Sample() {
  sysid_excitation::RuntimeSample sample;
  sample.state = sysid_excitation::RuntimeState::kRunning;
  sample.plan_file_sha256 = kHashA;
  sample.request_sha256 = kHashB;
  sample.contract_id = "offline-contract";
  sample.termination_owner_status = "unresolved";
  sample.episode = "training";
  sample.tick = 42;
  sample.segment_index = 7;
  sample.active_joint = 24;
  sample.right_arm_target_q_rad = {0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7};
  sample.active_velocity_rad_s = 0.25;
  sample.active_acceleration_rad_s2 = -0.5;
  return sample;
}

template <typename Function>
void ExpectReject(Function function) {
  bool rejected = false;
  try {
    function();
  } catch (const std::exception&) {
    rejected = true;
  }
  assert(rejected);
}

}  // namespace

int main() {
  auto sample = Sample();
  const auto context = sysid_excitation::MakeObserverContext(sample);
  sysid::Frame frame;
  frame.target_ns = 100;
  frame.write_begin_ns = 110;
  frame.write_end_ns = 120;
  frame.target_q[22] = 9.0F;
  frame.command_q[22] = 8.0F;
  frame.q[22] = 7.0F;
  const auto target_before = frame.target_q;
  const auto command_before = frame.command_q;
  const auto measured_before = frame.q;

  sysid_excitation::AttachObserverTag(sample, context, frame);
  assert(frame.target_q == target_before);
  assert(frame.command_q == command_before);
  assert(frame.q == measured_before);
  const auto encoded =
      sysid::Encode(frame, 3, "session", "offline", "generated", &context);
  const auto& excitation = encoded.at("excitation");
  assert(excitation.at("plan_file_sha256") == kHashA);
  assert(excitation.at("request_sha256") == kHashB);
  assert(excitation.at("runtime_state") == "running");
  assert(excitation.at("plan_tick") == 42);
  assert(excitation.at("segment_index") == 7);
  assert(excitation.at("active_joint") == 24);
  assert(excitation.at("fault_reason") == "");
  assert(encoded.at("target_q").at(22) == 9.0F);
  assert(encoded.at("command_q").at(22) == 8.0F);

  const std::string path =
      "/tmp/g1_sysid_excitation_observer_" + std::to_string(::getpid()) +
      ".jsonl";
  {
    sysid::Observer observer(path, "session", "offline", "generated", context);
    assert(observer.Offer(frame));
    const auto receipt = observer.Finish();
    assert(receipt.at("complete").get<bool>());
    assert(receipt.at("written") == 1);
  }
  std::ifstream stream(path);
  nlohmann::json async_row;
  stream >> async_row;
  assert(async_row.at("excitation").at("plan_tick") == 42);
  assert(async_row.at("target_q").at(22) == 9.0F);
  assert(async_row.at("command_q").at(22) == 8.0F);
  stream.close();
  std::remove(path.c_str());

  ExpectReject([&] { sysid::Encode(frame, 0, "s", "p", "k"); });
  auto changed = sample;
  changed.contract_id = "changed";
  ExpectReject(
      [&] { sysid_excitation::AttachObserverTag(changed, context, frame); });
  changed = sample;
  changed.active_joint = 21;
  ExpectReject(
      [&] { sysid_excitation::AttachObserverTag(changed, context, frame); });
  changed = sample;
  changed.right_arm_target_q_rad[0] =
      std::numeric_limits<double>::quiet_NaN();
  ExpectReject(
      [&] { sysid_excitation::AttachObserverTag(changed, context, frame); });
  changed = sample;
  changed.fault_reason.assign(96, 'x');
  ExpectReject(
      [&] { sysid_excitation::AttachObserverTag(changed, context, frame); });
  changed = sample;
  changed.fault_reason = std::string("bad\0reason", 10);
  ExpectReject(
      [&] { sysid_excitation::AttachObserverTag(changed, context, frame); });
  changed = sample;
  changed.plan_file_sha256 = "bad";
  ExpectReject([&] { sysid_excitation::MakeObserverContext(changed); });

  auto fault = sample;
  fault.state = sysid_excitation::RuntimeState::kFaultHold;
  fault.fault_reason = "fixture fault";
  sysid_excitation::AttachObserverTag(fault, context, frame);
  const auto fault_json =
      sysid::Encode(frame, 4, "session", "offline", "generated", &context);
  assert(fault_json.at("excitation").at("runtime_state") == "fault_hold");
  assert(fault_json.at("excitation").at("fault_reason") == "fixture fault");
  return 0;
}
