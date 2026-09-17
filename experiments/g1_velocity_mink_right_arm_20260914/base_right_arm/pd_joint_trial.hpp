#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>
#include <string>

// SDK-free fixed shoulder-pitch baseline experiment. No transport or auto-retry.
// Codes: 0=not trial, 1=start hold, 2=out, 3=far hold, 4=return, 5=end hold, 6=done.
struct PdTrialPoint {std::array<double,29> q;int phase=1,cycle=0;double dq=0,ddq=0;};
class PdJointTrial {
 std::array<double,29> baseline;
 double previous=-1;
 bool stopped=false;
public:
 static constexpr double distance=10.0*3.14159265358979323846/180.0;
 static constexpr double speed=45.0*3.14159265358979323846/180.0;
 static constexpr double acceleration=.32;
 const double move=std::max(1.875*distance/speed,std::sqrt(10/std::sqrt(3.0)*distance/acceleration));
 explicit PdJointTrial(const std::array<double,29>& q,double lower,double upper):baseline(q){
  for(auto value:q)if(!std::isfinite(value))throw std::runtime_error("pd_invalid_baseline");
  if(!std::isfinite(lower)||!std::isfinite(upper)||lower>=upper||q[22]<lower||q[22]+distance>upper)
   throw std::runtime_error("pd_trial_joint_limit");
 }
 double Total() const{return 1+3*2*(move+1);}
 void Stop(){stopped=true;}
 PdTrialPoint At(double elapsed){
  if(stopped)throw std::runtime_error("pd_trial_stopped");
  if(!std::isfinite(elapsed)||elapsed<0||elapsed<previous){Stop();throw std::runtime_error("pd_trial_clock");}
  previous=elapsed;PdTrialPoint result{baseline};
  if(elapsed<1)return result;
  if(elapsed>=Total()){result.phase=6;result.cycle=3;return result;}
  const double period=2*(move+1);const double t=elapsed-1;
  result.cycle=static_cast<int>(t/period);const double local=t-result.cycle*period;
  if(local>=2*move+1){result.phase=5;return result;}
  if(local>=move&&local<move+1){result.phase=3;result.q[22]+=distance;return result;}
  const bool back=local>=move+1;
  const double s=std::clamp((back?local-move-1:local)/move,0.0,1.0);
  const double x=distance*(10*s*s*s-15*s*s*s*s+6*s*s*s*s*s);
  result.phase=back?4:2;result.q[22]+=back?distance-x:x;
  const double sign=back?-1:1;
  result.dq=sign*distance/move*30*s*s*(1-s)*(1-s);
  result.ddq=sign*distance/(move*move)*60*s*(1-s)*(1-2*s);
  return result;
 }
};
