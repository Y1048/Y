#include "native_composition_offline.hpp"
#include <iostream>
#include <limits>
void Check(bool ok){if(!ok)throw std::runtime_error("watchdog assertion");}
int main(){
 try{
  OfflineStateContinuity silence;
  Check(silence.Check(1,1,1).empty());Check(silence.Poll(1.019).empty());
  Check(silence.Poll(1.021)=="state_timeout");
  Check(silence.Check(2,1.022,1.022)=="state_timeout");
  OfflineStateContinuity frozen;
  Check(frozen.Check(1,1,1).empty());Check(frozen.Check(1,1.015,1.015).empty());
  Check(frozen.Poll(1.021)=="robot_tick_stalled");
  NativeCompositionOffline adapter;
  Check(adapter.Poll(0)=="waiting");
  Check(adapter.Poll(std::numeric_limits<double>::quiet_NaN())=="stopped");
  Check(!adapter.Candidate());Check(adapter.Poll(1)=="stopped");
  std::cout<<"PASS silence timeout, latch, frozen tick, adapter abort\n";
 }catch(const std::exception& e){std::cerr<<e.what();return 1;}
}
