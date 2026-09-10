#include "regular_handoff_safety.hpp"
#include "verified_regular_handoff.hpp"

#include <cstdlib>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

using namespace regular_handoff;
void Check(bool x, const char* why) {
  if (!x) { std::cerr << "FAIL: " << why << '\n'; std::exit(1); }
}

// In-memory fake only: no SDK, channels, sockets, publishers or robot objects.
struct Backend {
  double time{0}, prepare_delay{0}, mode_delay{0}, fsm_delay{0}, state_delay{0}, enable_delay{0};
  int mode_result{0}, fsm_result{0}, fsm{501}, fault{0};
  std::string mode{"ai"};
  bool state_valid{true}, prepared{false}, enabled{false};
  int queries{0}, cancels{0}, fsm_calls{0};
  std::vector<std::string> trace;
  double Now() const { return time; }
  void PrepareInactiveWriter() {
    trace.push_back("prepare"); time += prepare_delay;
    if (fault == 1) throw std::runtime_error("prepare");
    prepared = true;
  }
  int CheckMode(std::string& name) {
    trace.push_back("mode"); ++queries; time += mode_delay;
    if (fault == 2) throw std::runtime_error("mode");
    name = mode; return mode_result;
  }
  int GetFsmId(int& id) {
    ++fsm_calls; time += fsm_delay;
    if (fault == 3) throw 3;
    id = fsm; return fsm_result;
  }
  bool StateValid() {
    trace.push_back("state"); time += state_delay;
    if (fault == 4) throw std::runtime_error("state");
    return state_valid;
  }
  bool EnablePreparedWriter(double started) noexcept {
    time += enable_delay;
    if (!FreshInterval(started, time)) return false;
    enabled = prepared;
    return enabled;
  }
  void CancelPreparedWriter() noexcept { ++cancels; prepared = false; }
};

struct Owner {
  OwnerPhase phase{OwnerPhase::Holding};
  int held{0}, monitored{0}, resolved{0};
  void ProtectOwnerLifetime() noexcept {
    if (phase == OwnerPhase::Holding) ++held;
    else if (phase == OwnerPhase::WriterStopped) ++monitored;
    else ++resolved;
  }
};

int main() {
  Check(FreshInterval(0, .25), "freshness boundary");
  Check(!FreshInterval(0, .251) && !FreshInterval(1, 0), "gap/reversal");
  Check(!FreshInterval(0, std::numeric_limits<double>::quiet_NaN()), "NaN");
  Check(!FreshInterval(0, std::numeric_limits<double>::infinity()), "infinity");
  {
    Backend b; auto sample = Observe(b);
    Check(sample.Fresh() && sample.state_valid && sample.mode == "ai", "valid observation");
    Check(b.queries == 1 && !b.prepared, "observation does not prepare writer");
  }
  for (int kind = 0; kind < 3; ++kind) {
    Backend b;
    if (kind == 0) b.mode_delay = 5;
    if (kind == 1) b.fsm_delay = 5;
    if (kind == 2) b.state_delay = 5;
    const auto sample = Observe(b);
    Check(!sample.Fresh(), "slow round rejected even with successful RPCs");
    VerifiedRegularHandoffGate gate(501);
    gate.Update(0, 0, "ai", 0, 501, true);
    Check(!gate.Update(sample.finished, sample.mode_result, sample.mode,
                       sample.fsm_result, sample.fsm_id,
                       sample.state_valid && sample.Fresh()), "slow round not stable");
  }
  for (int fault : {2, 3, 4}) {
    Backend b; b.fault = fault;
    const auto sample = Observe(b);
    Check(sample.mode_result != 0 && !sample.state_valid, "RPC exception clears partial success");
  }
  for (const auto& name : {std::string("ai"), std::string("other"), std::string("unknown")}) {
    Backend b;
    b.mode = ""; const auto cached = Observe(b);
    Check(cached.mode.empty(), "cached empty fixture");
    b.mode = name;  // owner changes AFTER old empty observation
    Check(!ResumeOnFreshEmpty(b) && !b.enabled, "fresh other owner must block resume");
    Check(b.queries == 2 && b.cancels == 1, "requery and discard inactive thread");
  }
  {
    Backend b; b.mode = ""; b.prepare_delay = 5;
    Check(ResumeOnFreshEmpty(b) && b.enabled, "prepare delay occurs before ownership query");
    Check(b.trace == std::vector<std::string>({"prepare", "mode", "state"}), "resume order");
    Check(b.fsm_calls == 0 && b.queries == 1 && b.cancels == 0, "no FSM RPC after fresh empty");
  }
  for (int kind = 0; kind < 7; ++kind) {
    Backend b; b.mode = "";
    if (kind == 0) b.mode_result = -1;
    if (kind == 1) b.mode_delay = 5;
    if (kind == 2) b.state_delay = .3;
    if (kind == 3) b.enable_delay = .3;
    if (kind == 4) b.state_valid = false;
    if (kind == 5) b.time = std::numeric_limits<double>::quiet_NaN();
    if (kind == 6) b.time = -1;
    Check(!ResumeOnFreshEmpty(b) && !b.enabled && b.cancels == 1, "invalid fallback refused");
  }
  for (int fault : {1, 2, 4}) {
    Backend b; b.mode = ""; b.fault = fault;
    Check(!ResumeOnFreshEmpty(b) && !b.enabled, "fallback exception cannot activate");
  }
  for (OwnerPhase phase : {OwnerPhase::BeforeTakeover, OwnerPhase::Holding,
                           OwnerPhase::WriterStopped, OwnerPhase::RegularVerified}) {
    for (bool throw_nonstd : {false, true}) {
      Owner owner; owner.phase = phase;
      const int result = RunOwnerProtected(owner, [&]() -> int {
        if (throw_nonstd) throw 42;
        throw std::runtime_error("settle/log/RPC failure");
      });
      Check(result == 1, "guard reports error");
      Check(owner.held == (phase == OwnerPhase::Holding), "holding error keeps same owner");
      Check(owner.monitored == (phase == OwnerPhase::WriterStopped), "stopped error monitors, not resumes");
    }
    Owner owner; owner.phase = phase;
    Check(RunOwnerProtected(owner, [] { return 0; }) == 0, "normal return status");
    Check(owner.held + owner.monitored + owner.resolved == 1, "normal exits also guarded");
  }
  for (const char* stage : {"csv_finish", "csv_hash", "run_hash", "result_open",
                            "result_write", "result_close", "handoff_outcome"}) {
    Owner owner; bool continued = false;
    const int status = RunOwnerProtected(owner, [&] {
      Check(!TryArtifact([&] { throw std::runtime_error(stage); }), "artifact failure reported");
      continued = true;
      owner.phase = OwnerPhase::RegularVerified;  // modeled successful subsequent handoff
      return 1;  // do not report complete artifacts
    });
    Check(continued && status == 1 && owner.resolved == 1, "artifact failure isolated from handoff");
  }
  Check(!TryArtifact([] { throw 1; }), "unknown artifact exception");
  std::cout << "PASS fresh-owner ordering, RPC/clock/prepare/state faults, owner lifetime, artifact isolation\n";
}
