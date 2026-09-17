#pragma once
#include "raw_input_watch_offline.hpp"
#include "upper_target_offline.hpp"
#include <mutex>

// Integration boundary for the existing native Policy/Controller path.
// Owns VR targets only; does not create a publisher, run a policy or change mode.
// The caller must validate SDK CRC, motor health and mode before Update.
class NativeVrPolicyAdapter {
 std::mutex mutex;
 RawInputWatchOffline input;
 UpperTargetOffline upper;
 InputValidator alignment;
 std::optional<double> ready_since;
 double started;
 bool engaged=false,ready=false;
 std::string reason;
 void Fail(const std::string& why){if(reason.empty())reason=why;input.Stop(reason);ready=false;}
public:
 std::string Phase(){
  std::lock_guard<std::mutex> lock(mutex);
  if(!reason.empty())return "stopped";
  if(engaged)return "vr_active";
  return ready?"vr_ready":"vr_wait_tracking";
 }
 NativeVrPolicyAdapter(const std::array<double,29>& captured,double now)
  :upper(captured,now,.17453292519943295),started(now){}
 bool Receive(const std::string& packet,double receipt){
  std::lock_guard<std::mutex> lock(mutex);
  if(!reason.empty())return false;
  if(!input.Receive(packet,receipt)){Fail(input.Reason());return false;}
  if(!engaged&&!ready&&input.Depth()){Fail("engage_before_ready");return false;}
  return true;
 }
 // Call from the existing writer's watchdog path as well as the policy loop.
 std::string Poll(double now){
  std::lock_guard<std::mutex> lock(mutex);
  if(reason.empty()&&!input.Poll(now))Fail(input.Reason());
  if(reason.empty()&&!engaged&&now-started>=15)Fail("startup_ready_timeout");
  return reason;
 }
 std::array<double,29> Update(const std::array<double,29>& measured,
   const std::array<double,29>& velocity,const std::array<double,29>& previous_desired,
   double receipt,double now,bool blend_complete){
  std::lock_guard<std::mutex> lock(mutex);
  if(!reason.empty())throw std::runtime_error(reason);
  if(!std::isfinite(now)||!std::isfinite(receipt)||receipt<0||receipt>now||now-receipt>.02)
   Fail("native_state_stale");
  if(!engaged&&now-started>=15)Fail("startup_ready_timeout");
  bool tracking=blend_complete;
  for(std::size_t i=0;i<29;++i){
   if(!std::isfinite(measured[i])||!std::isfinite(velocity[i])||!std::isfinite(previous_desired[i]))
    Fail("native_state_nonfinite");
   if(std::abs(measured[i]-previous_desired[i])>.025||std::abs(velocity[i])>.1)tracking=false;
   if(i>=12&&(std::abs(measured[i]-upper.Target()[i])>.25||std::abs(velocity[i])>1.5))
    Fail("native_upper_tracking");
  }
  if(!input.Poll(now))Fail(input.Reason());
  if(!reason.empty())throw std::runtime_error(reason);
  if(!engaged){
   if(!tracking)ready_since.reset();
   else if(!ready_since)ready_since=receipt;
   ready=ready_since&&receipt-*ready_since>=1;
  }
  const auto packets=input.Drain();
  if(!engaged&&!packets.empty()){
   if(!ready)Fail("engage_before_ready");
   std::array<double,7> goal{};
   const auto error=alignment.Validate(packets.front().payload,now,&goal,packets.front().received_at);
   if(!error.empty())Fail(error);
   for(std::size_t i=0;i<7;++i)if(std::abs(goal[i]-measured[i+22])>.025)Fail("initial_arm_mismatch");
   if(reason.empty())engaged=true;
  }
  if(!reason.empty())throw std::runtime_error(reason);
  if(upper.Tick(packets,now)=="stopped"){Fail(upper.Reason());throw std::runtime_error(reason);}
  return upper.Target(); // hybrid_target still supplies policy legs 0..11.
 }
};
