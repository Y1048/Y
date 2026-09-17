#include "native_snapshot_freshness.hpp"
#include <cassert>

int main() {
  using Clock=std::chrono::steady_clock;
  using namespace std::chrono;
  const Clock::time_point old_sample{};
  const auto latest_sample=old_sample+milliseconds(29);
  const auto validation=old_sample+milliseconds(30);
  assert(NativeSnapshotFresh(latest_sample,validation,milliseconds(20)));
  // A new callback cannot rejuvenate the snapshot actually being validated.
  assert(!NativeSnapshotFresh(old_sample,validation,milliseconds(20)));
  assert(NativeSnapshotFresh(old_sample,old_sample+milliseconds(20),milliseconds(20)));
  assert(!NativeSnapshotFresh(old_sample,old_sample+milliseconds(20)+nanoseconds(1),milliseconds(20)));
  assert(!NativeSnapshotFresh(latest_sample,old_sample,milliseconds(20)));
}
