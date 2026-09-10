#pragma once
#include "pd_joint_trial.hpp"
#include "pd_reach_reference.hpp"
// Offline Mink reference. Requires the reference ready posture, not an arbitrary
// captured pose. Hardware transition/collision validation remains separate.
class PdReachTrial {
 std::array<double,29> baseline;
 double previous=-1;
 bool stopped=false;
 static double Value(int joint,double u){
  double value=0;for(int k=7;k>=0;--k)value=value*u+PdReachReference::coefficients[joint][k];return value;
 }
 static double Parameter(double seconds){
  const auto& values=PdReachReference::timing_u;
  const auto& slopes=PdReachReference::timing_du;
  if(seconds<=0)return 0;
  if(seconds>=PdReachReference::move_seconds)return 1;
  const double dt=PdReachReference::move_seconds/(values.size()-1);
  const auto i=static_cast<std::size_t>(seconds/dt);
  const double s=(seconds-i*dt)/dt,s2=s*s,s3=s2*s;
  return (2*s3-3*s2+1)*values[i]+(s3-2*s2+s)*dt*slopes[i]
      +(-2*s3+3*s2)*values[i+1]+(s3-s2)*dt*slopes[i+1];
 }
public:
 explicit PdReachTrial(const std::array<double,29>& q):baseline(q){
  for(double v:q)if(!std::isfinite(v))throw std::runtime_error("pd_reach_invalid_baseline");
  for(int i=0;i<7;++i)if(std::abs(q[22+i]-Value(i,0))>1e-6)
   throw std::runtime_error("pd_reach_requires_ready_pose");
 }
 double Total() const{return 1+3*2*(PdReachReference::move_seconds+1);}
 void Stop(){stopped=true;}
 PdTrialPoint At(double elapsed){
  if(stopped)throw std::runtime_error("pd_reach_stopped");
  if(!std::isfinite(elapsed)||elapsed<0||elapsed<previous){Stop();throw std::runtime_error("pd_reach_clock");}
  previous=elapsed;PdTrialPoint result{baseline};
  if(elapsed<1)return result;
  if(elapsed>=Total()){result.phase=6;result.cycle=3;return result;}
  const double move=PdReachReference::move_seconds,period=2*(move+1),t=elapsed-1;
  result.cycle=static_cast<int>(t/period);const double local=t-result.cycle*period;
  if(local>=2*move+1){result.phase=5;return result;}
  double u=1;
  if(local>=move&&local<move+1)result.phase=3;
  else {
   const bool back=local>=move+1;
   const double leg_time=back?local-move-1:local;
   u=Parameter(back?move-leg_time:leg_time);result.phase=back?4:2;
  }
  for(int i=0;i<7;++i)result.q[22+i]=Value(i,u);
  return result;
 }
};
