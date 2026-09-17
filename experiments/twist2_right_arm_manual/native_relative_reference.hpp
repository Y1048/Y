#pragma once
#include <cmath>
// Caller holds the command mutex and validates active state and write freshness.
// Repeated writes of an identical right-arm frame do not invalidate the anchor.
template<class Audit,class Desired>
bool NativeRelativeReferenceMatches(const Audit& latest,const Audit& initial,const Desired& desired){
  if(!latest.sequence||!latest.sdk_accepted||latest.damping||
     !initial.sequence||!initial.sdk_accepted||initial.damping)return false;
  for(unsigned i=22;i<29;++i){
    if(!std::isfinite(latest.target[i])||!std::isfinite(latest.kp[i])||
       !std::isfinite(latest.kd[i])||!std::isfinite(latest.feedforward[i])||
       latest.target[i]!=initial.target[i]||latest.kp[i]!=initial.kp[i]||
       latest.kd[i]!=initial.kd[i]||latest.feedforward[i]!=initial.feedforward[i]||
       desired.target[i]!=initial.target[i]||desired.feedforward[i]!=initial.feedforward[i])return false;
  }
  return true;
}
