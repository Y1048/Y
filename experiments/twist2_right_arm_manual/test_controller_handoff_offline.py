"""Compile extracted production handoff methods against in-memory fakes only.

This is NOT a Unitree/DDS integration test. No real Controller constructor,
SDK header, socket, transport, policy or motor binary is compiled/executed.
"""
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent

PRELUDE = r'''
#include "regular_handoff_safety.hpp"
#include "verified_regular_handoff.hpp"
#include "writer_frame.hpp"
#include <atomic>
#include <chrono>
#include <cstdio>
#include <functional>
#include <iostream>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>

struct Clock {
  using duration = std::chrono::nanoseconds;
  using time_point = std::chrono::time_point<Clock>;
  static inline duration elapsed{};
  static time_point now() noexcept { return time_point(elapsed); }
  static void Advance(double seconds) {
    elapsed += std::chrono::duration_cast<duration>(std::chrono::duration<double>(seconds));
  }
};
int usleep(unsigned microseconds) { Clock::Advance(microseconds / 1000000.0); return 0; }
constexpr std::size_t kDofs = 29;
constexpr float kVelocityLimit = 12.0F;
struct PdReadySettle { static constexpr float error_limit=.1F, speed_limit=.1F; };
struct Motor { float position=0, velocity=0; float q() const { return position; } float dq() const { return velocity; } };
struct LowState { std::array<Motor,29> motors{}; const auto& motor_state() const { return motors; } };
// These memory objects are NOT SDK channels or publishers.
struct MemoryObject {};
struct ModeReader {
  std::function<int(std::string&)> check;
  std::function<int()> select;
  int CheckMode(std::string&, std::string& name) { return check(name); }
  int SelectMode(const std::string& name) {
    if (name != "ai") throw std::runtime_error("unexpected selection");
    return select();
  }
};
struct FsmReader {
  std::function<int(int&)> get;
  int GetFsmId(int& id) { return get(id); }
};
class Controller {
 public:
  regular_handoff::OwnerPhase owner_phase_{regular_handoff::OwnerPhase::Holding};
  std::atomic<bool> active_{true}, handoff_requested_{true};
  Clock::time_point activated_at_{};
  std::mutex write_cycle_mutex_;
  std::unique_ptr<MemoryObject> writer_{new MemoryObject}, publisher_{new MemoryObject};
  ModeReader mode;
  FsmReader fsm;
  ModeReader* switcher_{&mode};
  FsmReader* loco_{&fsm};
  int start_fsm_id_{501}, checks{0}, selections{0}, starts{0};
  bool valid_state{true}, stale_frame{false};
  LowState state;
  Controller() {
    Clock::elapsed = Clock::duration::zero();
    mode.check = [&](std::string& name) { ++checks; name="ai"; return 0; };
    mode.select = [&] {
      ++selections;
      if (active_.load() || writer_) throw std::runtime_error("writer overlaps SelectMode");
      return 0;
    };
    fsm.get = [](int& id) { id=501; return 0; };
  }
  void start_writer() { ++starts; writer_=std::make_unique<MemoryObject>(); }
  std::string reason() const { return "offline fixture"; }
  LowState snapshot(void*, Clock::time_point* received) const { *received=Clock::now(); return state; }
  void validate_state(const LowState&, float, bool, Clock::time_point, bool) const {
    if (!valid_state) throw std::runtime_error("stale LowState fixture");
  }
  WriterFrame writer_frame() const {
    WriterFrame frame; frame.valid=true; frame.write_returned_s=Now()-(stale_frame ? 1.0 : 0.0); return frame;
  }
'''

SUFFIX = r'''
};
void Check(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
int main() {
  try {
    {
      Controller c;
      Check(c.verified_regular_handoff(), "normal handoff");
      Check(c.selections==1 && !c.writer_ && !c.publisher_ && !c.active_, "stop/select/close sequence");
      Check(c.owner_phase_==regular_handoff::OwnerPhase::RegularVerified, "verified lifecycle");
    }
    for (int fault=0; fault<3; ++fault) {
      Controller c;
      if (fault==0) c.valid_state=false;
      if (fault==1) c.state.motors[15].position=.2F;
      if (fault==2) c.stale_frame=true;
      Check(!c.verified_regular_handoff(), "settle failure must return holding");
      Check(c.active_ && c.writer_ && c.selections==0, "settle failure cannot drop owner");
    }
    {
      Controller c;
      c.mode.select=[&]() -> int { ++c.selections; throw std::runtime_error("select failed"); };
      Check(c.verified_regular_handoff() && c.selections==1, "selection exception classified without retry");
    }
    {
      Controller c;
      c.mode.check=[&](std::string& name) { ++c.checks; if (c.checks<=3) throw 42; name="ai"; return 0; };
      Check(c.verified_regular_handoff() && c.starts==0, "mode exceptions do not resume writer");
    }
    {
      Controller c;
      int calls=0;
      c.fsm.get=[&](int& id) { ++calls; if(calls<=3) throw 42; id=501; return 0; };
      Check(c.verified_regular_handoff() && c.starts==0, "FSM exceptions do not resume writer");
    }
    {
      Controller c;
      c.mode.check=[&](std::string& name) { ++c.checks; name=""; return 0; };
      Check(!c.verified_regular_handoff(), "empty service falls back after timeout");
      Check(c.active_ && c.writer_ && c.starts==1, "fresh empty resumes one memory writer");
      Check(c.owner_phase_==regular_handoff::OwnerPhase::Holding, "fallback phase");
    }
    {
      Controller c;
      // Old observation remains empty, but the final query after preparing
      // the inactive writer sees ai. It must discard, then verify ai normally.
      c.mode.check=[&](std::string& name) { ++c.checks; name=c.starts ? "ai" : ""; return 0; };
      Check(c.verified_regular_handoff(), "changed owner eventually verified");
      Check(c.starts==1 && !c.active_ && !c.writer_, "fresh ai blocks cached-empty fallback");
    }
    {
      Controller c;
      c.mode.check=[&](std::string& name) {
        ++c.checks; name=c.checks<=5 ? "another_service" : "ai"; return 0;
      };
      Check(c.verified_regular_handoff() && c.starts==0, "another service remains stopped");
    }
    {
      Controller c;
      double first_fresh=-1;
      c.mode.check=[&](std::string& name) {
        ++c.checks; name="ai";
        if(c.checks<=3) Clock::Advance(5.0);
        else if(first_fresh<0) first_fresh=c.Now();
        return 0;
      };
      Check(c.verified_regular_handoff(), "slow RPC later recovers");
      Check(first_fresh>=0 && c.Now()-first_fresh>=1.0 && c.starts==0,
            "slow RPC cannot count toward stable second");
    }
    {
      Controller c;
      c.mode.check=[&](std::string& name) { ++c.checks; name=c.checks==1 ? "" : "ai"; return 0; };
      c.fsm.get=[&](int& id) { if(c.checks==1) Clock::Advance(5.0); id=501; return 0; };
      Check(c.verified_regular_handoff() && c.starts==0, "stale empty before slow FSM cannot resume");
    }
    std::cout << "PASS 12 extracted-controller scenarios; no SDK or DDS\n";
  } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
'''


class ControllerHandoffOfflineTest(unittest.TestCase):
    def test_production_handoff_methods_with_memory_fakes(self):
        compiler = os.environ.get("CXX", "g++")
        self.assertIsNotNone(shutil.which(compiler), f"Missing C++ compiler: {compiler}")
        source = (ROOT / "twist2_mink_cycle_trial.cpp").read_text(encoding="utf-8")
        methods = source[source.index("  [[noreturn]] void finish()"):
                         source.index("  void print_stats() const")]
        with tempfile.TemporaryDirectory(prefix="g1-handoff-memory-") as folder:
            cpp = Path(folder) / "controller_memory_test.cpp"
            exe = Path(folder) / "controller_memory_test"
            cpp.write_text(PRELUDE + methods + SUFFIX, encoding="utf-8")
            flags = shlex.split(os.environ.get("G1_OFFLINE_CXXFLAGS", ""))
            build = subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Wpedantic",
                                    "-Werror", "-UNDEBUG", "-pthread", *flags,
                                    "-I", str(ROOT), str(cpp), "-o", str(exe)],
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS 12 extracted-controller scenarios", run.stdout)


if __name__ == "__main__":
    unittest.main()
