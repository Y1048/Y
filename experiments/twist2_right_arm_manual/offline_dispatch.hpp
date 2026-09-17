#pragma once
#include "offline_owner.hpp"

// Memory-only transport contract. No SDK serialization, network or mode changes.
struct OfflineDispatchFrame {
 std::uint64_t sequence=0,state_sequence=0;
 double created_at=0;
 std::array<OfflineMotorDiagnostic,35> motors{};
};
class OfflineMemorySink {
 std::optional<OfflineDispatchFrame> last;
 std::size_t count=0;
 double minimum_gap=0,maximum_gap=0;
public:
 bool reject_next=false;
 bool Accept(const OfflineDispatchFrame& frame){
  if(reject_next){reject_next=false;return false;}
  if(last){const double gap=frame.created_at-last->created_at;
   minimum_gap=count==1?gap:std::min(minimum_gap,gap);maximum_gap=std::max(maximum_gap,gap);}
  last=frame;++count;return true;
 }
 const auto& Last()const{return last;}
 std::size_t Count()const{return count;}
 double MinimumGap()const{return minimum_gap;}
 double MaximumGap()const{return maximum_gap;}
};
class OfflineDispatch {
 OfflineOwner& owner;
 OfflineMemorySink& sink;
 double last_call,last_step;
 std::uint64_t sequence=0;
 bool stopped=false;
 void Stop(const std::string& why){owner.Stop(why);stopped=true;}
public:
 // Caller supplies a monotonic clock. This class does not create a scheduler.
 OfflineDispatch(OfflineOwner& o,OfflineMemorySink& s,double now)
  :owner(o),sink(s),last_call(now),last_step(now){
  if(!std::isfinite(now)||now<0)throw std::invalid_argument("dispatch_start_time");
 }
 OfflineDispatch(const OfflineDispatch&)=delete;
 OfflineDispatch& operator=(const OfflineDispatch&)=delete;
 bool HandoffRequired()const{return stopped||!owner.Reason().empty();}
 bool Pump(double now){
  if(stopped)return false;
  if(!owner.Reason().empty()){stopped=true;return false;}
  if(!std::isfinite(now)||now<last_call){Stop("dispatch_clock");return false;}
  last_call=now;
  const double elapsed=now-last_step;
  // Experimental 2 ms cadence / 6 ms maximum gap; never catch up in a burst.
  if(elapsed>.006+1e-12){Stop("dispatch_deadline");return false;}
  if(elapsed<.002-1e-12)return false;
  last_step=now;
  if(!owner.Tick(now)){
   if(!owner.Reason().empty())stopped=true;
   return false;
  }
  OfflineDispatchFrame frame;
  frame.sequence=sequence+1;frame.state_sequence=owner.LatestStateSequence();frame.created_at=now;
  frame.motors=owner.Writer()->Diagnostics();
  if(!sink.Accept(frame)){Stop("dispatch_sink_rejected");return false;}
  ++sequence;return true;
 }
};
