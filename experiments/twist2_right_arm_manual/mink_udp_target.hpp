#pragma once
#include "raw_input_watch_offline.hpp"
#include <memory>
#include <mutex>
#include <functional>
// Direct absolute Mink input, fixed keyboard 1x rate. No initial input-error gate.
class MinkUdpTarget {
 std::mutex mutex;
 RawInputWatchOffline watch;
 std::unique_ptr<UpperTargetOffline> upper;
 std::array<double,29> target;
 double previous;
 std::function<double()> event_clock;
 bool ready=false;
 bool live_limits=false;
 std::string reason;
 void Fail(const std::string& why){if(reason.empty())reason=why;watch.Stop(reason);}
public:
 MinkUdpTarget(const std::array<double,29>& q,double now,
               std::function<double()> clock={},bool use_live_limits=false):target(q),previous(now),event_clock(clock),live_limits(use_live_limits){}
 bool Receive(const std::string& packet,double now){
  std::lock_guard<std::mutex> lock(mutex);
  // Live callers can wait for this mutex after sampling their argument.
  // Sample the shared steady clock here so validation follows lock order.
  if(event_clock)now=event_clock();
  if(!reason.empty())return false;
  if(!watch.Receive(packet,now)){Fail(watch.Reason());return false;}
  if(!ready&&watch.Depth()){Fail("engage_before_initial_pose");return false;}
  return true;
 }
 std::string Poll(double now){std::lock_guard<std::mutex> lock(mutex);if(event_clock)now=event_clock();if(!watch.Poll(now))Fail(watch.Reason());return reason;}
 bool Ready(){std::lock_guard<std::mutex> lock(mutex);return ready;}
 std::array<double,29> Update(double now,bool blend_complete){
  std::lock_guard<std::mutex> lock(mutex);
  if(event_clock)now=event_clock();
  if(!std::isfinite(now)||now<=previous)Fail("clock");
  const double dt=std::min(.02,now-previous);previous=now;
  if(!watch.Poll(now))Fail(watch.Reason());
  if(!reason.empty())throw std::runtime_error(reason);
  if(!blend_complete)return target;
  if(!ready){
   // Same ready pose as g1_right_arm_common.py, angles in radians.
   constexpr double rad=.017453292519943295;
   const std::array<double,14> pose={10*rad,22*rad,0,55*rad,0,0,0,10*rad,-22*rad,0,55*rad,0,0,0};
   bool reached=true;
   for(std::size_t i=15;i<29;++i){const double d=pose[i-15]-target[i];target[i]+=std::copysign(std::min(std::abs(d),.08*dt),d);reached=reached&&std::abs(pose[i-15]-target[i])<1e-12;}
   if(reached){ready=true;upper=std::make_unique<UpperTargetOffline>(target,now,10.0,live_limits?.7:.08,live_limits?10*.017453292519943295:0);}
   return target;
  }
  if(upper->Tick(watch.Drain(),now)=="stopped"){Fail(upper->Reason());throw std::runtime_error(reason);}
  target=upper->Target();return target;
 }
};
