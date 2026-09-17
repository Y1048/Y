#include "mink_live_cycle_contract.hpp"
#include <iostream>
using C=MinkLiveCycleContract;
using J=nlohmann::json;
void Check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
struct Fixture {
 C::Q home{};C::Arm low{},high{};bool path=true;
 C::Controls controls{false};C::Feedback feedback;
 double now=0;unsigned long long seq=0;
 C cycle;
 Fixture():home([]{C::Q q{};q[0]=.2;q[12]=.3;return q;}()),
  low([]{C::Arm a{};a.fill(-3);return a;}()),high([]{C::Arm a{};a.fill(3);return a;}()),
  cycle(home,low,high,0,[this](const C::Q&,const C::Q&){return path;}){feedback.q=home;}
 J Packet(const std::string& event,double joint=0,int axis=0){
  C::Arm a{};a[axis]=joint;
  return J{{"schema","g1.mink.cycle.live.v1"},{"command_provenance","live_mink"},
   {"profile","today"},{"clearance_m",.04},{"sample_time_s",now+.02},{"session","test"},{"sequence",++seq},
   {"epoch",cycle.Epoch()},{"source_age_s",0.},{"event",event},{"joints",a}};
 }
 bool Send(J packet,bool follow=true){
  auto before=cycle.Target();auto v=cycle.Velocity();now+=.02;
  if(follow)feedback.q=before;
  feedback.received=now;
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
 for(size_t i=0;i<7;++i){
  Check(C::MeasuredReadyJoint(C::ready_error[i],.05,0,i),"ready boundary");
  Check(!C::MeasuredReadyJoint(C::ready_error[i]+1e-5,0,0,i),"ready error exceeded");
  Check(!C::MeasuredReadyJoint(0,.05001,0,i),"ready speed exceeded");
  ++tests;
 }
 {Fixture f;f.Engage();Check(f.Send(f.Packet("pinch")),"release");
  f.feedback.q[23]=.0768;f.feedback.q[25]=.0268;
  for(int n=0;n<23;++n)Check(f.Send(f.Packet("return"),false),"offset return");
  Check(f.cycle.Mode()==C::State::Returning,"offset bypassed dwell");
  for(int n=0;n<3;++n)Check(f.Send(f.Packet("return"),false),"offset settled");
  Check(f.cycle.Mode()==C::State::Waiting,"measured offsets blocked return");
  f.Engage();Check(f.cycle.Mode()==C::State::Tracking,"offset reengage");++tests;
 }

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
 for(int scenario=0;scenario<11;++scenario){
  Fixture f;f.Engage();J p=f.Packet("active");
  switch(scenario){
   case 0:p["sequence"]=f.seq-1;break;
   case 1:p["session"]="other";break;
   case 2:p["epoch"]=1;break;
   case 3:p["source_age_s"]=.3;break;
   case 4:p["joints"][0]=.1;break;
   case 5:p["joints"][0]=true;break;
   case 6:p["profile"]="old";break;
   case 7:p["command_provenance"]="simulation_only";break;
   case 8:f.controls.stop=true;break;
   case 9:f.path=false;break;
   case 10:p["event"]="idle";break;
  }
  const bool recoverable=scenario==4||scenario==9||scenario==10;
  Check(f.Send(p)==recoverable,"bad input disposition");auto q=f.cycle.Target();
  f.controls={false};f.path=true;
  if(recoverable){
   Check(f.cycle.Mode()==C::State::Returning,"recoverable fault did not return");
   Check(f.cycle.AutomaticHandbackRequested(),"automatic handback not requested");
   for(int n=0;n<30&&!f.cycle.AutomaticHandbackReady();++n)
    Check(f.Send(f.Packet("return")),"automatic return sample");
   Check(f.cycle.AutomaticHandbackReady(),"automatic handback never settled");
  }else{
   Check(!f.Send(f.Packet("active")),"stop restarted");
  }
  Check(f.cycle.Target()==q,"rejected sample changed target");++tests;
 }
 {Fixture f;f.Engage();auto p=f.Packet("active");p["joints"][0]=3.1;
  Check(f.Send(p),"joint limit should request return");
  Check(f.cycle.Mode()==C::State::Returning&&f.cycle.Reason()=="joint_limit","joint limit handback");++tests;}
 {Fixture f;f.Engage();Check(!f.cycle.Receive("{",.06,{f.home,{},.06},f.controls),"malformed accepted");++tests;}
 {Fixture f;f.Engage();Check(!f.cycle.Poll(.1,{f.home,{},0.},f.controls),"stale feedback");++tests;}
 {Fixture f;f.Engage();Check(!f.cycle.Poll(.31,{f.home,{},.31},f.controls),"input timeout");++tests;}
 {Fixture f;Check(f.Send(f.Packet("idle")),"waiting idle");
  Check(f.cycle.Poll(.31,{f.home,{},.31},f.controls),"waiting input timeout");
  Check(f.cycle.Mode()==C::State::Waiting,"waiting timeout changed state");++tests;}
 {Fixture f;Check(f.Send(f.Packet("idle")),"waiting idle before sample gap");
  f.now=1.20;auto p=f.Packet("idle");
  Check(f.Send(p),"waiting sample gap was not rebased");
  Check(f.cycle.Mode()==C::State::Waiting,"waiting sample gap changed state");++tests;}
 {Fixture f;f.Engage();Check(f.cycle.Poll(.06,{f.home,{},.06},f.controls),"poll");
  Check(!f.cycle.Poll(.05,{f.home,{},.05},f.controls),"reverse clock");++tests;}
 {Fixture f;f.Engage();Check(f.Send(f.Packet("pinch")),"release");
  Check(!f.Send(f.Packet("active")),"early active bypassed return");++tests;}
 {Fixture f;f.Engage();
  Check(f.cycle.RequestAutomaticHandback("Select/B requested",f.now),"Select/B handback request");
  Check(f.Send(f.Packet("active")),"in-flight active should be ignored");
  Check(f.cycle.Target()==f.home,"in-flight active moved target");
  for(int n=0;n<30&&!f.cycle.AutomaticHandbackReady();++n)
   Check(f.Send(f.Packet("return")),"Select/B automatic return");
 Check(f.cycle.AutomaticHandbackReady()&&f.cycle.Reason()=="Select/B requested","Select/B handback ready");++tests;}
 {Fixture f;Check(f.Send(f.Packet("idle")),"waiting idle before Q");
  const auto epoch=f.cycle.Epoch();
  Check(f.cycle.RequestAutomaticHandback("operator Q safe hold",f.now),"waiting Q request");
  Check(f.cycle.Mode()==C::State::Waiting&&f.cycle.AutomaticHandbackReady(),"waiting Q was not immediately ready");
  Check(f.cycle.Epoch()==epoch,"waiting Q unnecessarily advanced epoch");++tests;}
 {Fixture f;f.Engage();
  Check(f.cycle.RequestAutomaticHandback("operator Q checked Regular handoff",f.now),"Q return request");
  Check(!f.cycle.Poll(.31,{f.home,{},.31},f.controls),"missing return input accepted");
  Check(f.cycle.Reason()=="input_timeout","request reason masked actual fault");++tests;}
 {Fixture f;f.Engage();f.cycle.RequestAutomaticHandback("transport gap",f.now);
  for(int n=0;n<30&&!f.cycle.AutomaticHandbackReady();++n)
   Check(f.Send(f.Packet("return")),"transport return");
  Check(f.cycle.ContinueFromSafeHold(),"safe hold continuation");
  Check(f.cycle.Mode()==C::State::Waiting&&f.cycle.Reason().empty(),"safe hold did not reset waiting");++tests;}
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
 // Yesterday acceleration bound and duplicate JSON keys must reject.
 {C::Q q{};C::Arm lo{},hi{};lo.fill(-3);hi.fill(3);C c(q,lo,hi,0,[](auto&,auto&){return true;},"yesterday");
  Fixture f;auto p=f.Packet("idle");p["profile"]="yesterday";
  Check(c.Receive(p.dump(),.02,{q,{},.02},{false}),"yesterday idle");
  p=f.Packet("active");p["profile"]="yesterday";p["sample_time_s"]=.04;
  Check(c.Receive(p.dump(),.04,{q,{},.04},{false}),"yesterday active");
  p=f.Packet("active",.0002);p["profile"]="yesterday";p["sample_time_s"]=.06;
  Check(c.Receive(p.dump(),.06,{q,{},.06},{false}),"yesterday acceleration return");
  Check(c.Mode()==C::State::Returning&&c.AutomaticHandbackRequested(),"yesterday handback");++tests;}
 {Fixture f;auto raw=f.Packet("idle").dump();raw.insert(1,"\"sequence\":999,");
  Check(!f.cycle.Receive(raw,.02,{f.home,{},.02},f.controls),"duplicate key accepted");++tests;}
 std::cout<<"PASS "<<tests<<" offline candidate scenarios; no SDK/socket/publisher\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
