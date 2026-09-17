#pragma once
#include "offline_hg_native_decoder.hpp"
#include "offline_state_continuity.hpp"
// Native-file fixture adapter. Never accepts JSON/Mink as measured state.
// Deployment ABI must be independently confirmed before any real-state use.
class NativeCompositionOffline {
 GuardedCompositionOffline guard;
 OfflineStateContinuity continuity;
 std::uint64_t sequence=0;
public:
 explicit NativeCompositionOffline(bool prealignment=false):guard({.02,1,.1,.01,.025,.25,.17453292519943295},{.01,.15,.15,1.5,75},prealignment){}
 const auto& Candidate()const{return guard.Candidate();}
 const auto& Reason()const{return guard.Reason();}
 const auto& PreparedUpper()const{return guard.PreparedUpper();}
 std::uint64_t Sequence()const{return sequence;}
 std::string Stop(const std::string& why){return guard.Abort(why);}
 // Caller must invoke from its independent clock even when no state arrives.
 // This helper does not create a thread, timer, SDK object or publisher.
 std::string Poll(double now){
  if(!guard.Reason().empty())return "stopped";
  const auto why=continuity.Poll(now);
  return why.empty()?"waiting":guard.Abort(why);
 }
 std::string Prepare(const std::vector<std::uint8_t>& bytes,const std::string& profile,
                     double received_at,const std::vector<ReceivedInput>& packets,double now) {
  if(!guard.Reason().empty())return "stopped";
  try {
   const auto decoded=DecodeOfflineHgNative(bytes,profile,sequence+1,received_at);
   const auto continuity_error=continuity.Check(decoded.robot_tick,received_at,now);
   if(!continuity_error.empty())return guard.Abort(continuity_error);
   const auto mode=guard.Prepare(decoded.sample,decoded.health,packets,now);
   if(mode!="stopped")++sequence;
   return mode;
  }catch(const std::exception& e){return guard.Abort(e.what());}
 }
 std::string Finish(const std::array<float,29>& action,double now) {
  return guard.Finish(OfflinePolicySample{action,sequence,sequence,now},now);
 }
};
