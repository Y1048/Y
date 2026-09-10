#pragma once
#include "upper_target_offline.hpp"
#include <vector>
// Single event-owner only. Validate arrival immediately, retain FIFO for Prepare.
class RawInputWatchOffline {
 InputValidator validator;
 std::vector<ReceivedInput> packets;
 std::string reason;
public:
 const auto& Reason() const{return reason;}
 size_t Depth() const{return packets.size();}
 void Stop(const std::string& why){if(reason.empty())reason=why;packets.clear();}
 bool Poll(double now){
  if(reason.empty()){auto why=validator.CheckTimeout(now);if(!why.empty())Stop(why);}
  return reason.empty();
 }
 bool Receive(const std::string& raw,double now){
  if(!Poll(now))return false;
  if(raw.size()>16384){Stop("datagram_too_large");return false;}
  const auto status=validator.Validate(raw,now,nullptr,now,nullptr,true);
  if(!status.empty()&&status!="waiting"){Stop(status);return false;}
  // Fully validated pre-engage inactive packets carry no target or sequence state.
  if(status=="waiting")return true;
  if(packets.size()>=64){Stop("queue_overflow");return false;}
  packets.push_back({raw,now});return true;
 }
 std::vector<ReceivedInput> Drain(){auto result=std::move(packets);packets.clear();return result;}
};
