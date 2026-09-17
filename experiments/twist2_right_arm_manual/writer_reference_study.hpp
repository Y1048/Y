#pragma once
#include <array>
#include <mutex>
#include <cstdint>
#include <cmath>

// Memory-only model of serialization with a writer. SDK accepted != motor ACK.
class WriterReferenceStudy {
  mutable std::mutex mutex;
  std::array<double,29> command{};
  std::uint64_t sequence=0;
  double completed=-1;
  bool accepted=false, damping=false, stopped=false, bound=false;
public:
  void Complete(const std::array<double,29>& q,double now,bool sdk_accepted,bool is_damping) {
    std::lock_guard<std::mutex> lock(mutex);
    ++sequence;command=q;completed=now;accepted=sdk_accepted;damping=is_damping;
  }
  std::uint64_t Sequence() const {std::lock_guard<std::mutex> lock(mutex);return sequence;}
  void Stop(){std::lock_guard<std::mutex> lock(mutex);stopped=true;}
  // Callback must bind and commit its initial candidate in this critical section.
  // It must not reenter this object or perform network I/O.
  template<class Bind> bool TryBind(std::uint64_t expected,double now,bool safety_passed,Bind bind) {
    std::lock_guard<std::mutex> lock(mutex);
    if(bound||stopped||!safety_passed||!sequence||expected!=sequence||!accepted||damping)return false;
    if(!std::isfinite(now)||!std::isfinite(completed)||completed<0||now<completed||now-completed>.02)return false;
    for(double q:command)if(!std::isfinite(q))return false;
    if(!bind(command))return false;
    bound=true;return true;
  }
};
