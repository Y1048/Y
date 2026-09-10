#pragma once

#include <cmath>
#include <string>
#include <utility>

namespace regular_handoff {

// Main-thread lifecycle; this does not claim atomic ownership of a service.
enum class OwnerPhase { BeforeTakeover, Holding, WriterStopped, RegularVerified };
constexpr double kMaximumObservationSeconds = 0.25;

inline bool FreshInterval(double started, double finished,
                          double limit = kMaximumObservationSeconds) noexcept {
  return std::isfinite(started) && std::isfinite(finished) &&
         std::isfinite(limit) && limit > 0.0 && started >= 0.0 &&
         finished >= started && finished - started <= limit;
}

struct Observation {
  double started{-1.0}, finished{-1.0};
  int mode_result{-1}, fsm_result{-1}, fsm_id{-1};
  std::string mode;
  bool state_valid{false};
  bool Fresh() const noexcept { return FreshInterval(started, finished); }
};

// The same orchestration is exercised by SDK-free fault-injection tests.
// Backend: Now(), CheckMode(name), GetFsmId(id), StateValid().
template<class Backend>
Observation Observe(Backend& backend) noexcept {
  Observation result;
  try {
    result.started = backend.Now();
    result.mode_result = backend.CheckMode(result.mode);
    result.fsm_result = backend.GetFsmId(result.fsm_id);
    result.state_valid = backend.StateValid();
    result.finished = backend.Now();
  } catch (...) {
    // Never reuse a partial successful mode result after another RPC threw.
    result.mode_result = result.fsm_result = -1;
    result.state_valid = false;
  }
  return result;
}

// Prepare an INACTIVE thread before querying ownership. The final enabling
// callback must recheck elapsed time and perform no blocking work or RPC.
// An empty service observation is necessary, NOT an ownership lease. A later
// external service change cannot be excluded by CheckMode alone.
template<class Backend>
bool ResumeOnFreshEmpty(Backend& backend) noexcept {
  static_assert(noexcept(backend.CancelPreparedWriter()), "cancel must not throw");
  static_assert(noexcept(backend.EnablePreparedWriter(0.0)), "enable must not throw");
  bool enabled = false;
  try {
    backend.PrepareInactiveWriter();
    const double started = backend.Now();
    std::string name;
    const int result = backend.CheckMode(name);  // new query, never cached
    if (result == 0 && name.empty() && backend.StateValid() &&
        FreshInterval(started, backend.Now()))
      enabled = backend.EnablePreparedWriter(started);
  } catch (...) {
    enabled = false;
  }
  if (!enabled) backend.CancelPreparedWriter();
  return enabled;
}

// Artifact failures are reported by the caller but cannot unwind the owner.
template<class Work>
bool TryArtifact(Work&& work) noexcept {
  try {
    std::forward<Work>(work)();
    return true;
  } catch (...) {
    return false;
  }
}

// Owner and its dependencies must live OUTSIDE this callback. Recovery happens
// before they can be destroyed, including for non-std exceptions.
template<class Owner, class Work>
int RunOwnerProtected(Owner& owner, Work&& work) noexcept {
  static_assert(noexcept(owner.ProtectOwnerLifetime()), "recovery must not throw");
  int status = 1;
  try { status = std::forward<Work>(work)(); } catch (...) {}
  owner.ProtectOwnerLifetime();
  return status;
}

}  // namespace regular_handoff
