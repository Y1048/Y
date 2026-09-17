#pragma once
#include <chrono>

template<class TimePoint,class Duration>
bool NativeSnapshotFresh(TimePoint received,TimePoint now,Duration maximum_age) {
  return received<=now && now-received<=maximum_age;
}
