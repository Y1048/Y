#include "offline_writer_study.hpp"
#include <iostream>
#include <limits>
#include <stdexcept>
using namespace offline_twist2;
void Check(bool ok,const char* message) {if(!ok) throw std::runtime_error(message);}
struct Fixture {
 OfflineStateSample s{}; OfflineStateHealth h{}; OfflineDesiredPosition d{};
 Fixture(){for(size_t i=0;i<29;++i)s.q[i]=d.q[i]=kDefault[i];
 h.crc_verified=true;h.mode_pr=0;h.mode_machine=5;h.deadman=true;h.emergency_stop=false;}
};
float Reference(size_t i,float last,float desired,float q,float dq,float ff) {
 float delta=(i<12?2.F:.8F)*.002F,soft=kTorqueLimit[i]*.5F;
 float target=std::clamp(desired,last-delta,last+delta);
 target=std::clamp(target,kLower[i]+.05F,kUpper[i]-.05F);
 ff=std::clamp(ff,-soft,soft);
 float nonpos=-kKd[i]*dq+ff;
 target=std::clamp(target,q+(-soft-nonpos)/kKp[i],q+(soft-nonpos)/kKp[i]);
 return std::clamp(target,kLower[i]+.05F,kUpper[i]-.05F);
}
int main() {
 try {
 Fixture f;OfflineWriterStudy normal(kDefault,0);
 for(int n=1;n<=500;++n) {
  double now=n*.002;f.s.received_at=f.d.created_at=now;
  auto previous=normal.LastTarget();
  for(size_t i=0;i<29;++i) {f.s.q[i]=previous[i]; f.d.q[i]=kDefault[i]+(i%2?.01F:-.01F);}
  Check(normal.Tick(f.s,f.h,f.d,now),"normal");
  for(size_t i=0;i<29;++i) {
   const auto& m=normal.Diagnostics()[i];
   Check(m.q==Reference(i,previous[i],f.d.q[i],static_cast<float>(f.s.q[i]),0,0),"reference equality");
   Check(std::abs(m.q-previous[i])<=(i<12?.004F:.0016F)+1e-7F,"rate");
   Check(m.q>=std::min(previous[i],f.d.q[i])&&m.q<=std::max(previous[i],f.d.q[i]),"overshoot");
   Check(m.kp==kKp[i]&&m.kd==kKd[i]&&std::abs(m.predicted_torque)<=kTorqueLimit[i]*.5F+1e-4F,"gains torque");
  }
 }
 Fixture arm;OfflineWriterStudy arm_only(kDefault,0);
 for(size_t i=22;i<29;++i)arm.d.q[i]+=.00016F; // 0.08 rad/s x 2 ms
 Check(arm_only.Tick(arm.s,arm.h,arm.d,.002),"right arm only");
 for(size_t i=0;i<29;++i)Check(arm_only.LastTarget()[i]==(i<22?kDefault[i]:arm.d.q[i]),"non-arm hold");
 for(int scenario=0;scenario<12;++scenario) {
  Fixture x;OfflineWriterStudy w(kDefault,0);double now=.002;
  switch(scenario) {
   case 0:x.h.deadman=false;break;
   case 1:x.h.emergency_stop=true;break;
   case 2:x.h.crc_verified=false;break;
   case 3:x.h.rpy[0]=.36;break;
   case 4:x.h.faults[28]=1;break;
   case 5:x.d.q[28]=std::numeric_limits<float>::quiet_NaN();break;
   case 6:now=.022;break;
   case 7:now=.252;x.s.received_at=now;break;
   case 8:x.s.dq[28]=13;break;
   case 9:x.h.temperature[28]=76;break;
   case 10:x.h.mode_machine=0;break;
   case 11:now=.001;break;
  }
  Check(!w.Tick(x.s,x.h,x.d,now),"fault accepted");
  Check(w.LastTarget()==kDefault,"partial update");
  const auto reason=w.Reason();
  for(size_t i=0;i<35;++i)Check(w.Diagnostics()[i].kp==0&&w.Diagnostics()[i].feedforward==0&&w.Diagnostics()[i].kd==((i==3||i==9)?2:1),"damping");
  Fixture fresh;fresh.s.received_at=fresh.d.created_at=1;
  Check(!w.Tick(fresh.s,fresh.h,fresh.d,1)&&w.Reason()==reason&&w.LastTarget()==kDefault,"latch");
 }
 Fixture a;OfflineWriterStudy conflict(kDefault,0);a.s.q[27]=.2;
 float jumped=Reference(27,0,0,.2F,0,0);
 Check(jumped>.0016F,"reference rate counterexample");
 Check(!conflict.Tick(a.s,a.h,a.d,.002)&&conflict.Reason()=="incompatible_rate_joint_torque_limits","intersection rate");
 auto edge=kDefault;edge[27]=kUpper[27]-.05F;
 Fixture b;b.s.q[27]=b.d.q[27]=edge[27];b.s.dq[27]=1.5;b.d.feedforward[27]=-2.5F;
 float qref=Reference(27,edge[27],edge[27],edge[27],1.5F,-2.5F);
 float tref=kKp[27]*(qref-edge[27])-kKd[27]*1.5F-2.5F;
 Check(std::abs(tref)>2.5F,"reference torque counterexample");
 OfflineWriterStudy edge_writer(edge,0);
 Check(!edge_writer.Tick(b.s,b.h,b.d,.002),"intersection torque");
 Fixture grace;OfflineWriterStudy watchdog(kDefault,0);grace.s.received_at=.25;
 Check(watchdog.Tick(grace.s,grace.h,grace.d,.25),"handoff grace");
 grace.s.received_at=.252;Check(!watchdog.Tick(grace.s,grace.h,grace.d,.252)&&watchdog.Reason()=="command_timeout","watchdog");
 Fixture empty;OfflineWriterStudy missing(kDefault,0);Check(!missing.Tick(empty.s,empty.h,std::nullopt,.002),"missing");
 OfflineWriterStudy stopped(kDefault,0);stopped.Stop("release");Check(!stopped.Tick(empty.s,empty.h,empty.d,.002),"external stop");
 std::array<float,29> tau{};tau.fill(1000);
 for(int n=0;n<=100;++n){float alpha=n/100.F;auto faded=OfflineTorqueFade(tau,alpha);
 for(size_t i=0;i<29;++i)Check(faded[i]==(1-alpha)*kTorqueLimit[i]*.5F,"fade");}
 bool rejected=false;try{OfflineTorqueFade(tau,2);}catch(const std::invalid_argument&){rejected=true;}Check(rejected,"invalid fade");
 std::cout<<"PASS: 500 ticks x 29 reference/rate/overshoot/gain/torque checks; 12 fault+latch cases; 2 conflict reproductions; watchdog, missing, stop, 101 fade steps\n";
 std::cout<<"Synthetic reference conflicts: wrist rate step="<<jumped<<" rad; predicted torque="<<tref<<" Nm\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
