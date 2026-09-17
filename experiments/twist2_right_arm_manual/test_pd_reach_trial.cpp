#include "pd_reach_trial.hpp"
#include <iostream>
void check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
int main(){try{
 std::array<double,29> q{};for(int i=0;i<7;++i)q[22+i]=PdReachReference::coefficients[i][0];
 PdReachTrial trial(q);auto last=q;std::array<double,29> lastv{};double vmax=0,amax=0,travel=0;
 int phases=0;
 for(int n=0;n<=static_cast<int>(std::ceil(trial.Total()*500));++n){
  auto p=trial.At(std::min(n*.002,trial.Total()));phases|=1<<p.phase;
  for(int i=0;i<29;++i){
   if(i<22)check(p.q[i]==q[i],"other joint changed");
   const double v=(p.q[i]-last[i])/.002;
   if(n>1)amax=std::max(amax,std::abs(v-lastv[i])/.002);
   vmax=std::max(vmax,std::abs(v));lastv[i]=v;
  }
  travel=std::max(travel,std::abs(p.q[22]-q[22]));last=p.q;
 }
 check(last==q,"not returned");check(phases==126,"missing phase");
 check(PdReachReference::move_seconds>0,"invalid duration");
 check(travel>1,"not a full reach");check(vmax<3.141592653589793/4,"speed");check(vmax>44.9*3.141592653589793/180,"target speed not attained");check(amax<=PdReachReference::max_acceleration_rad_s2,"acceleration cap exceeded");
 for(int n=0;n<=100;++n){
  const double move=PdReachReference::move_seconds;
  const double t=move*n/100;
  PdReachTrial out(q),back(q);
  const auto a=out.At(1+t),b=back.At(1+move+1+move-t);
  for(int i=0;i<29;++i)check(std::abs(a.q[i]-b.q[i])<1e-10,"return path differs");
 }
 trial.Stop();bool fail=false;try{trial.At(999);}catch(...){fail=true;}check(fail,"stop latch");
 q[22]+=.01;fail=false;try{PdReachTrial bad(q);}catch(...){fail=true;}check(fail,"wrong initial pose accepted");
 std::cout<<"PASS full reach/3 returns/frozen joints/phase/stop/initial mismatch; peak rad/s="<<vmax<<" acceleration="<<amax<<'\n';
}catch(const std::exception& e){std::cerr<<e.what();return 1;}}
