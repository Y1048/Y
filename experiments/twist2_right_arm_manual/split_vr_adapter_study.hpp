#pragma once
// Experimental adapter; native use requires an explicit candidate build.
#include "split_settle_window.hpp"
#include "raw_input_watch_offline.hpp"
#include "anchored_upper_study.hpp"
#include <mutex>

// Integration boundary for the existing native Policy/Controller path.
// Owns VR targets only; does not create a publisher, run a policy or change mode.
// The caller must validate SDK CRC, motor health and mode before Update.
class SplitVrAdapterStudy {
 std::mutex mutex;
 RawInputWatchOffline input;
 AnchoredUpperStudy upper;
 InputValidator alignment;
 SplitSettleWindow settle;
 double started;
 bool engaged=false,ready=false;
 bool reference_bound=false;
 bool require_reference;
 std::string reason;
 void Fail(const std::string& why){if(reason.empty())reason=why;input.Stop(reason);ready=false;}
public:
 bool NeedsCommandReference(){
  std::lock_guard<std::mutex> lock(mutex);
  return reason.empty()&&!engaged&&!reference_bound&&input.Depth()>0;
 }
 bool BindCommandReference(const std::array<double,29>& command){
  std::lock_guard<std::mutex> lock(mutex);
  if(!reason.empty()||!ready||engaged||reference_bound)return false;
  if(!upper.BindCommandReference(command)){Fail("writer_reference_invalid");return false;}
  reference_bound=true;return true;
 }
 std::string Phase(){
  std::lock_guard<std::mutex> lock(mutex);
  if(!reason.empty())return "stopped";
  if(engaged)return "vr_active";
  return ready?"vr_ready":"vr_wait_tracking";
 }
 SplitVrAdapterStudy(const std::array<double,29>& captured,double now,SplitSettleLimits limits,bool require_writer_reference=false)
  :upper(captured,now,.17453292519943295),settle(limits),started(now),require_reference(require_writer_reference){}
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
   double receipt,double now,bool blend_complete,
   const std::array<double,3>& rpy,const std::array<double,3>& gyro,bool external_checks_passed){
  std::lock_guard<std::mutex> lock(mutex);
  if(!reason.empty())throw std::runtime_error(reason);
  if(!std::isfinite(now)||!std::isfinite(receipt)||receipt<0||receipt>now||now-receipt>.02)
   Fail("native_state_stale");
  if(!engaged&&now-started>=15)Fail("startup_ready_timeout");
  if(!external_checks_passed)Fail("external_safety_stop");
  bool tracking=false;
  if(reason.empty()){
   try{tracking=settle.Update(measured,velocity,rpy,gyro,receipt,blend_complete);}
   catch(const std::exception& e){Fail(e.what());}
  }
  for(std::size_t i=0;i<29;++i){
   if(!std::isfinite(measured[i])||!std::isfinite(velocity[i])||!std::isfinite(previous_desired[i]))
    Fail("native_state_nonfinite");
   // Fixed target offsets are not settle-window motion.
   if(i>=12&&(std::abs(measured[i]-upper.Target()[i])>.25||std::abs(velocity[i])>1.5))
    Fail("native_upper_tracking");
  }
  if(!input.Poll(now))Fail(input.Reason());
  if(!reason.empty())throw std::runtime_error(reason);
  if(!engaged){
   ready=tracking;
  }
  const auto packets=input.Drain();
  if(!engaged&&!packets.empty()){
   if(!ready)Fail("engage_before_ready");
   if(require_reference&&!reference_bound)Fail("writer_reference_required");
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
