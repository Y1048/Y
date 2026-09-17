#include "pd_joint_trial.hpp"
#include <iostream>
void check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
int main(){try{
 std::array<double,29> q{};q[22]=.3;PdJointTrial trial(q,-3,2.6);
 auto previous=q;double peak=0;int phases=0;
 for(int n=0;n<=static_cast<int>(std::ceil(trial.Total()*500));++n){
  const double t=std::min(n*.002,trial.Total());auto p=trial.At(t);phases|=1<<p.phase;
  for(int i=0;i<29;++i)if(i!=22)check(p.q[i]==q[i],"other joint changed");
  check(p.q[22]>=q[22]-1e-12&&p.q[22]<=q[22]+trial.distance+1e-12,"overshoot");
  check(std::abs(p.dq)<=trial.speed+1e-12&&std::abs(p.ddq)<=trial.acceleration+1e-12,"analytic limit");
  check(std::abs(p.q[22]-previous[22])<=trial.speed*.002+1e-12,"sampled speed limit");
  peak=std::max(peak,std::abs(p.dq));previous=p.q;
 }
 check(phases==126,"missing phases");check(previous==q,"did not return");
 check(peak>0&&peak<trial.speed,"unexpected peak");
 bool failed=false;trial.Stop();try{trial.At(99);}catch(...){failed=true;}check(failed,"restart after stop");
 failed=false;try{PdJointTrial bad(q,-3,.4);}catch(...){failed=true;}check(failed,"joint limit");
 PdJointTrial clock(q,-3,2.6);clock.At(.2);failed=false;try{clock.At(.1);}catch(...){failed=true;}check(failed,"clock reversal");
 failed=false;try{clock.At(.3);}catch(...){failed=true;}check(failed,"clock not latched");
 std::cout<<"PASS right-only, complete roundtrips, stages, speed/acceleration, bounds, stop/clock latch\n";
}catch(const std::exception& e){std::cerr<<e.what();return 1;}}
