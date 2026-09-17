#include "pd_ready_settle.hpp"
#include <iostream>
#include <limits>
#include <string>
void check(bool ok){if(!ok)throw std::runtime_error("assertion failed");}
template<class F> void rejects(F action,const char* reason){
  try{action();}catch(const std::runtime_error& e){check(std::string(e.what())==reason);return;}
  throw std::runtime_error("expected rejection");
}
int main(){try{
  std::array<double,29> q{},dq{},target{};
  PdReadySettle settled;
  // Leg motion does not veto the arm-specific condition.
  dq[0]=2;
  for(int n=0;n<50;++n)check(!settled.Update(n*.02,n*.02,q,dq,target));
  check(settled.Update(1,1,q,dq,target));
  PdReadySettle moving;
  for(int n=0;n<40;++n)check(!moving.Update(n*.02,n*.02,q,dq,target));
  dq[15]=.11;check(!moving.Update(.8,.8,q,dq,target));dq[15]=0;
  for(int n=41;n<91;++n)check(!moving.Update(n*.02,n*.02,q,dq,target));
  check(moving.Update(1.84,1.84,q,dq,target));
  PdReadySettle error;
  q[28]=.11;
  for(int n=0;n<100;++n)check(!error.Update(n*.02,n*.02,q,dq,target));
  q[28]=0;
  PdReadySettle duplicate;
  check(!duplicate.Update(0,0,q,dq,target));
  check(!duplicate.Update(.04,0,q,dq,target));
  rejects([&]{duplicate.Update(.061,0,q,dq,target);},"pd_settle_stale");
  rejects([&]{duplicate.Update(.08,.08,q,dq,target);},"pd_settle_stopped");
  PdReadySettle gap;
  for(int n=0;n<40;++n)check(!gap.Update(n*.02,n*.02,q,dq,target));
  check(!gap.Update(.9,.9,q,dq,target));
  check(!gap.Update(.92,.92,q,dq,target));
  PdReadySettle timeout;
  check(!timeout.Update(0,0,q,dq,target));
  rejects([&]{timeout.Update(10,10,q,dq,target);},"pd_settle_timeout");
  PdReadySettle clock;
  check(!clock.Update(1,1,q,dq,target));
  rejects([&]{clock.Update(.9,.9,q,dq,target);},"pd_settle_clock");
  PdReadySettle invalid;
  q[22]=std::numeric_limits<double>::quiet_NaN();
  rejects([&]{invalid.Update(0,0,q,dq,target);},"pd_settle_nonfinite");
  std::cout<<"PASS: dwell, arm speed/error, leg exclusion, duplicate/stale, gap, timeout, clock, nonfinite, latch\n";
  return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
