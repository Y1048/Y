#include "mink_cycle_candidate_offline.hpp"
#include <iostream>
using C=MinkCycleCandidateOffline;
using J=nlohmann::json;
void Check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
struct Fixture {
 C::Q home{};C::Arm low{},high{};bool path=true;
 C::Controls controls{true,false};C::Feedback feedback;
 double now=0;unsigned long long seq=0;
 C cycle;
 Fixture():home([]{C::Q q{};q[0]=.2;q[12]=.3;return q;}()),
  low([]{C::Arm a{};a.fill(-3);return a;}()),high([]{C::Arm a{};a.fill(3);return a;}()),
  cycle(home,low,high,0,[this](const C::Q&,const C::Q&){return path;}){feedback.q=home;}
 J Packet(const std::string& event,double joint=0,int axis=0){
  C::Arm a{};a[axis]=joint;
  return J{{"schema","g1.mink.cycle.offline.v1"},{"provenance","offline_only"},
   {"profile","right_arm_90_180_a60"},{"session","test"},{"sequence",++seq},
   {"epoch",cycle.Epoch()},{"source_age_s",0.},{"event",event},{"joints",a}};
 }
 bool Send(J packet,bool follow=true){
  auto before=cycle.Target();auto v=cycle.Velocity();now+=.02;
  if(follow)feedback.q=before;feedback.received=now;
  bool ok=cycle.Receive(packet.dump(),now,feedback,controls);
  for(size_t i=0;i<22;++i)Check(cycle.Target()[i]==home[i],"non-right joint modified");
  if(ok)for(size_t i=0;i<7;++i){
   Check(std::abs(cycle.Velocity()[i])<=C::speed[i]+1e-7,"speed cap");
   Check(std::abs(cycle.Velocity()[i]-v[i])<=C::acceleration*.02+1e-7,"acceleration cap");
  }else Check(cycle.Target()==before,"rejected sample changed target");
  return ok;
 }
 void Engage(){Check(Send(Packet("idle")),"idle");Check(Send(Packet("active")),"engage");}
};
int main(){try{
 unsigned tests=0;
 // Absolute samples, two release types, return completion and re-engagement.
 for(const std::string release:{"pinch","tracking_disengaged"}){
  Fixture f;f.Engage();
  for(int n=1;n<=200;++n){
   const double q=.05*(1-std::cos(3.141592653589793*n/100.));
   const std::string event=n<100?"active":n==100?release:"return";
   Check(f.Send(f.Packet(event,q)),"cycle sample");
   Check(std::abs(f.cycle.Target()[22]-q)<1e-12,"not absolute target");
  }
  for(int n=0;n<30&&f.cycle.Mode()==C::State::Returning;++n)
   Check(f.Send(f.Packet("return")),"settle");
  Check(f.cycle.Mode()==C::State::Waiting,"return completion");
  Check(f.cycle.Epoch()==1,"epoch advance");f.Engage();
  Check(f.cycle.Mode()==C::State::Tracking,"reengage");++tests;
 }
 for(int scenario=0;scenario<12;++scenario){
  Fixture f;f.Engage();J p=f.Packet("active");
  switch(scenario){
   case 0:p["sequence"]=f.seq-1;break;
   case 1:p["session"]="other";break;
   case 2:p["epoch"]=1;break;
   case 3:p["source_age_s"]=.3;break;
   case 4:p["joints"][0]=.1;break;
   case 5:p["joints"][0]=true;break;
   case 6:p["profile"]="old";break;
   case 7:p["provenance"]="live_mink";break;
   case 8:f.controls.r1=false;break;
   case 9:f.controls.stop=true;break;
   case 10:f.path=false;break;
   case 11:p["event"]="idle";break;
  }
  Check(!f.Send(p),"bad input accepted");auto q=f.cycle.Target();
  f.controls={true,false};f.path=true;
  Check(!f.Send(f.Packet("active")),"stop restarted");Check(f.cycle.Target()==q,"stop moved");++tests;
 }
 {Fixture f;f.Engage();Check(!f.cycle.Receive("{",.06,{f.home,{},.06},f.controls),"malformed accepted");++tests;}
 {Fixture f;f.Engage();Check(!f.cycle.Poll(.1,{f.home,{},0.},f.controls),"stale feedback");++tests;}
 {Fixture f;f.Engage();Check(!f.cycle.Poll(.31,{f.home,{},.31},f.controls),"input timeout");++tests;}
 {Fixture f;f.Engage();Check(f.cycle.Poll(.06,{f.home,{},.06},f.controls),"poll");
  Check(!f.cycle.Poll(.05,{f.home,{},.05},f.controls),"reverse clock");++tests;}
 {Fixture f;f.Engage();Check(f.Send(f.Packet("pinch")),"release");
  Check(!f.Send(f.Packet("active")),"early active bypassed return");++tests;}
 {Fixture f;f.Engage();Check(f.Send(f.Packet("pinch")),"release");
  f.feedback.q[22]=.1;
  for(int n=0;n<40;++n)Check(f.Send(f.Packet("return"),false),"lag sample");
  Check(f.cycle.Mode()==C::State::Returning,"ack before measured return");++tests;}
 {Fixture f;Check(!f.Send(f.Packet("active")),"initial active bypassed idle");++tests;}
 {Fixture f;f.Engage();Check(f.Send(f.Packet("pinch")),"release");
  f.feedback.dq[22]=.1;
  for(int n=0;n<30;++n)Check(f.Send(f.Packet("return")),"moving feedback sample");
  Check(f.cycle.Mode()==C::State::Returning,"ack while measured joint moving");
  f.feedback.dq[22]=0;
  for(int n=0;n<30&&f.cycle.Mode()==C::State::Returning;++n)Check(f.Send(f.Packet("return")),"settling feedback");
  Check(f.cycle.Mode()==C::State::Waiting,"settled feedback not acknowledged");
  Check(!f.Send(f.Packet("active")),"reengage bypassed fresh idle");++tests;}
 // At identical ramp speed the proximal cap rejects; wrist cap allows.
 for(int axis:{0,4}){
  Fixture f;f.Engage();double q=0;bool ok=true;
  for(int n=1;n<=110&&ok;++n){q+=.8*(n*.02)*.02;ok=f.Send(f.Packet("active",q,axis));}
  Check(axis==0?!ok:ok,"per-joint profile");++tests;
 }
 std::cout<<"PASS "<<tests<<" offline candidate scenarios; no SDK/socket/publisher\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
