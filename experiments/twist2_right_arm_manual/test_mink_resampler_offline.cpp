#include "mink_resampler_offline.hpp"
#include <iostream>
using R=MinkResamplerOffline;
void Check(bool v,const char* why){if(!v)throw std::runtime_error(why);}
struct Fixture {
 R::Q baseline{};R::Arm low{},high{},zero{};bool safe=true;size_t checks=0;
 R r;
 Fixture():baseline([]{R::Q q{};for(size_t i=0;i<22;++i)q[i]=.1;return q;}()),
 low([]{R::Arm a{};a.fill(-20);return a;}()),high([]{R::Arm a{};a.fill(20);return a;}()),
 r(baseline,low,high,0,[this](const auto&,const auto&){++checks;return safe;}){}
 void Stopped(const char* reason){Check(r.Reason()==reason,"reason");Check(!r.Output(),"output survives stop");Check(!r.Step(100,true),"stop not latched");}
};
int main(){try{
 unsigned scenarios=0;size_t outputs=0;double maximum_v=0,maximum_a=0;
 // Full forward/return plus final hold, both punctual and jittered arrivals.
 for(bool jitter:{false,true}){
  Fixture f;unsigned index=1;R::Arm last_velocity{};R::Q last_q=f.baseline;
  for(unsigned tick=0;tick<=4000;++tick){
   double now=tick*R::output_dt;
   while(true){double source=index*R::input_dt;double receipt=source+(jitter?.008:0.);if(receipt>now+1e-10)break;
    R::Arm q{};double t=std::min(source,5.);double value=.5*(1-std::cos(2*3.141592653589793*t/5.));q[0]=value;q[4]=value*.5;
    Check(f.r.Push(q,index,source,receipt),"valid push");++index;
   }
   if(!f.r.Step(now,true))throw std::runtime_error("tick="+std::to_string(tick)+" "+f.r.Reason());const auto& s=*f.r.Output();
   for(size_t i=0;i<22;++i)Check(s.q[i]==f.baseline[i],"non-right changed");
   Check(s.q[22]>=-1e-12&&s.q[22]<=1+1e-12,"overshoot");
   for(size_t i=0;i<7;++i){
    maximum_v=std::max(maximum_v,std::abs(s.velocity[i]));maximum_a=std::max(maximum_a,std::abs(s.acceleration[i]));
    Check(std::abs(s.velocity[i]-last_velocity[i])<=R::C::acceleration*R::output_dt+1e-7,"velocity discontinuity");
    Check(std::abs(s.q[22+i]-last_q[22+i])/R::output_dt<=R::C::speed[i]+1e-7,"sample speed");
   }
   last_velocity=s.velocity;last_q=s.q;++outputs;
  }
  Check(std::abs(f.r.Output()->q[22])<1e-12,"return not exact");Check(f.checks==4001,"missing path check");++scenarios;
 }
 // Reach each group's actual velocity cap with a bounded acceleration ramp.
 for(size_t axis:{size_t(0),size_t(4)}){
  Fixture f;unsigned index=1;double peak=0;const double cap=R::C::speed[axis],ramp=cap;
  const double end=2*ramp+.1;R::Arm previous_v{};
  for(unsigned tick=0;tick<=3600;++tick){double now=tick*.002;
   while(index*R::input_dt<=now+1e-10){double source=index*R::input_dt,t=std::min(source,end),q;
    if(t<ramp)q=.5*t*t;
    else if(t<ramp+.1)q=.5*ramp*ramp+cap*(t-ramp);
    else {double d=t-ramp-.1;q=.5*ramp*ramp+cap*.1+cap*d-.5*d*d;}
    R::Arm arm{};arm[axis]=q;Check(f.r.Push(arm,index,source,source),"cap push");++index;
   }
   Check(f.r.Step(now,true),"cap step");const auto& out=*f.r.Output();peak=std::max(peak,out.velocity[axis]);maximum_v=std::max(maximum_v,std::abs(out.velocity[axis]));maximum_a=std::max(maximum_a,std::abs(out.acceleration[axis]));
   Check(std::abs(out.velocity[axis]-previous_v[axis])<=R::C::acceleration*.002+1e-7,"cap acceleration");previous_v=out.velocity;
   Check(out.q[22+axis]<=cap*cap+cap*.1+1e-9,"cap trajectory overshoot");++outputs;
  }
  Check(std::abs(peak-cap)<1e-7,"group speed cap not reached");++scenarios;
 }
 {Fixture f;Check(!f.r.Step(0,false),"owner stop");f.Stopped("owner_stop");++scenarios;}
 {Fixture f;Check(f.r.Step(0,true),"start");f.safe=false;Check(!f.r.Step(.002,true),"collision");f.Stopped("path_rejected");++scenarios;}
 {Fixture f;Check(f.r.Step(0,true),"start");Check(!f.r.Step(.004,true),"missed output tick");f.Stopped("output_grid");++scenarios;}
 {Fixture f;Check(f.r.Step(0,true),"start");for(unsigned n=1;n<=16;++n)Check(f.r.Step(n*.002,true),"initial delay");Check(!f.r.Step(.034,true),"extrapolated missing sample");f.Stopped("sample_underrun");++scenarios;}
 {Fixture f;Check(!f.r.Push(f.zero,2,2*R::input_dt,2*R::input_dt),"sequence skip");f.Stopped("sequence");++scenarios;}
 {Fixture f;Check(!f.r.Push(f.zero,1,.018,.018),"receipt used as source");f.Stopped("source_grid");++scenarios;}
 {Fixture f;Check(!f.r.Push(f.zero,1,R::input_dt,.05),"old input");f.Stopped("source_age");++scenarios;}
 {Fixture f;auto q=f.zero;q[0]=.0005;Check(!f.r.Push(q,1,R::input_dt,R::input_dt),"acceleration jump");f.Stopped("acceleration");++scenarios;}
 {Fixture f;auto q=f.zero;q[0]=.1;Check(!f.r.Push(q,1,R::input_dt,R::input_dt),"speed jump");f.Stopped("speed");++scenarios;}
 {Fixture f;auto q=f.zero;q[0]=std::nan("");Check(!f.r.Push(q,1,R::input_dt,R::input_dt),"nan");f.Stopped("joint_limit");++scenarios;}
 {Fixture f;Check(f.r.Step(0,true),"start");Check(!f.r.Step(-.002,true),"clock");f.Stopped("clock");++scenarios;}
 {Fixture f;for(unsigned n=1;n<64;++n)Check(f.r.Push(f.zero,n,n*R::input_dt,n*R::input_dt),"queue fill");Check(!f.r.Push(f.zero,64,64*R::input_dt,64*R::input_dt),"queue overflow");f.Stopped("queue_overflow");++scenarios;}
 std::cout<<"PASS "<<scenarios<<" resampler scenarios; outputs="<<outputs<<" max_velocity="<<maximum_v<<" max_acceleration="<<maximum_a<<"; offline only\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}

