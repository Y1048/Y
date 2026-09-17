#pragma once
#include <cmath>
#include <cstdint>
#include <optional>
#include <string>
// Receipt freshness and tick progress are distinct. No tick unit/rate assumption.
class OfflineStateContinuity {
 std::optional<std::uint32_t> tick;
 std::optional<double> receipt,progress;
 std::string reason;
public:
 const auto& Reason()const{return reason;}
 std::string Poll(double now){
  if(!reason.empty())return reason;
  if(!std::isfinite(now)||now<0||(receipt&&now<*receipt))reason="stale_or_invalid_state_time";
  else if(receipt&&now-*receipt>.02)reason="state_timeout";
  else if(progress&&now-*progress>.02)reason="robot_tick_stalled";
  return reason;
 }
 std::string Check(std::uint32_t next,double received,double now){
  if(!reason.empty())return reason;
  const auto Fail=[&](const char* why){reason=why;return reason;};
  if(!std::isfinite(now)||!std::isfinite(received)||received<0||received>now||now-received>.02)
   return Fail("stale_or_invalid_state_time");
  if(receipt&&(received<=*receipt||received-*receipt>.02))
   return Fail("state_receipt_discontinuity");
  if(progress&&now-*progress>.02)return Fail("robot_tick_stalled");
  if(tick){
   const std::uint32_t advance=next-*tick;
   if(advance>=0x80000000U)return Fail("robot_tick_discontinuity");
   if(advance)progress=received;
  }else progress=received;
  tick=next;receipt=received;return "";
 }
};
