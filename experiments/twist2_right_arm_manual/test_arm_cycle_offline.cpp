#include "arm_cycle_offline.hpp"
#include <iostream>
#include <limits>

using C=ArmCycleOffline;
void Check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
struct Fixture {
 C::Q home{},zero{};
 C cycle{home,0};
 C::Arm input{};
 double t=0;
 void Step(C::Event e,bool follow=true,bool fresh=true){
  const auto before=cycle.Target();const auto v=cycle.Velocity();
  t+=.02;cycle.Tick(t,e,input,follow?before:home,zero,fresh);
  if(cycle.State()!=C::Mode::Stopped){
   for(size_t i=0;i<7;++i){
    Check(std::abs(cycle.Velocity()[i])<=.7+1e-10,"speed");
    Check(std::abs(cycle.Velocity()[i]-v[i])<=.17453292519943295*.02+1e-10,"acceleration");
   }
  }
  for(size_t i=0;i<22;++i)Check(cycle.Target()[i]==home[i],"other joint changed");
 }
 void Engage(){Step(C::Event::Idle);Step(C::Event::Active);Check(cycle.State()==C::Mode::Tracking,"engage");}
 void Move(){for(size_t i=0;i<7;++i)input[i]=i%2==0?.5:-.3;for(int i=0;i<100;++i)Step(C::Event::Active);}
};
int main(){
 try{
  Fixture f;
  f.Step(C::Event::Active);Check(f.cycle.State()==C::Mode::Waiting,"requires idle edge");
  for(int repeat=0;repeat<3;++repeat){
   f.input.fill(-.3);f.Engage();
   const auto anchored=f.cycle.Target();
   f.Step(C::Event::Active);Check(f.cycle.Target()==anchored,"anchor jump");
   f.Move();Check(f.cycle.Target()[22]>.1,"no movement");
   f.Step(C::Event::Pinch);Check(f.cycle.State()==C::Mode::Returning,"pinch return");
   for(int i=0;i<1400&&f.cycle.State()==C::Mode::Returning;++i)f.Step(C::Event::Active);
   Check(f.cycle.State()==C::Mode::Waiting,"return completion");
   Check(std::abs(f.cycle.Target()[22])<1e-6,"not home");
   f.Step(C::Event::Active);Check(f.cycle.State()==C::Mode::Waiting,"queued engage survived return");
  }
  Fixture fault;fault.Engage();fault.Move();fault.Step(C::Event::Pinch);
  fault.Step(C::Event::Fault);auto held=fault.cycle.Target();
  fault.Step(C::Event::Idle);fault.Step(C::Event::Active);
  Check(fault.cycle.State()==C::Mode::Stopped&&fault.cycle.Target()==held,"fault not latched");
  Fixture timeout;timeout.Engage();timeout.Move();timeout.Step(C::Event::Pinch);
  for(int i=0;i<15;++i)timeout.Step(C::Event::None);
  Check(timeout.cycle.Reason()=="input_timeout","heartbeat timeout");
  Fixture feedback;feedback.Engage();feedback.Step(C::Event::Active,true,false);
  Check(feedback.cycle.Reason()=="feedback_timeout","stale feedback");
  Fixture invalid;invalid.Engage();invalid.input[0]=std::numeric_limits<double>::quiet_NaN();invalid.Step(C::Event::Active);
  Check(invalid.cycle.Reason()=="input_joint_limit","nan accepted");
  Fixture blocked;blocked.Engage();blocked.Move();blocked.Step(C::Event::Pinch);
  C::Q away{};away[22]=.3;
  for(int i=0;i<1550&&blocked.cycle.State()!=C::Mode::Stopped;++i){
   blocked.t+=.02;blocked.cycle.Tick(blocked.t,C::Event::Idle,blocked.input,away,blocked.zero);
  }
  Check(blocked.cycle.Reason()=="return_timeout","false measured completion");
  Fixture idle;idle.Engage();idle.Step(C::Event::Idle);
  Check(idle.cycle.Reason()=="unexpected_idle","idle mistaken for pinch");
  Fixture clock;clock.cycle.Tick(0,C::Event::Idle,clock.input,clock.home,clock.zero);
  Check(clock.cycle.Reason()=="clock","clock reversal");
  Fixture range;range.input[0]=-3;range.Engage();range.input[0]=2;range.Step(C::Event::Active);
  Check(range.cycle.Reason()=="rebased_joint_limit","rebased limit");
  std::cout<<"PASS: 3 cycles; anchors; return engage rejection; limits; other joints; fault latch; input/feedback/return timeouts; NaN; idle fault\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
