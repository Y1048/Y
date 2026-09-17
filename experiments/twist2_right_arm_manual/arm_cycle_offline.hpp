#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>
#include <string>

// Offline state-machine prototype ONLY. Events are trusted test inputs, not UDP.
// A future adapter must validate session, sequence, source age and event identity.
class ArmCycleOffline {
public:
 enum class Mode { Waiting, Tracking, Returning, Stopped };
 enum class Event { None, Idle, Active, Pinch, Fault };
 using Q = std::array<double,29>;
 using Arm = std::array<double,7>;
private:
 Q home_, q_;
 Arm velocity_{}, anchor_input_{}, anchor_q_{}, goal_{};
 double previous_, receipt_, settled_ = 0, return_started_ = 0;
 bool released_ = false;
 Mode mode_ = Mode::Waiting;
 std::string reason_;
 static constexpr double speed_ = .7, accel_ = .17453292519943295;
 inline static constexpr Arm lower_={-3.0892,-2.2515,-2.618,-1.0472,-1.97222,-1.61443,-1.61443};
 inline static constexpr Arm upper_={2.6704,1.5882,2.618,2.0944,1.97222,1.61443,1.61443};
 void Stop(const char* reason) { mode_=Mode::Stopped; reason_=reason; }
 static bool Valid(const Arm& a) {
  for(size_t i=0;i<7;++i)
   if(!std::isfinite(a[i])||a[i]<lower_[i]||a[i]>upper_[i])return false;
  return true;
 }
public:
 explicit ArmCycleOffline(const Q& ready,double now):home_(ready),q_(ready),previous_(now),receipt_(now) {
  for(double x:ready)if(!std::isfinite(x))throw std::invalid_argument("baseline");
  for(size_t i=0;i<7;++i)goal_[i]=ready[i+22];
  if(!Valid(goal_)||!std::isfinite(now)||now<0)throw std::invalid_argument("baseline");
 }
 Mode State()const{return mode_;}
 const Q& Target()const{return q_;}
 const Arm& Velocity()const{return velocity_;}
 const std::string& Reason()const{return reason_;}
 // One ordered event per tick; never collapse pinch/fault with a later active.
 // measured/dq are synthetic feedback; freshness is an explicit test precondition.
 void Tick(double now,Event event,const Arm& input,const Q& measured,const Q& dq,bool feedback_fresh=true) {
  if(mode_==Mode::Stopped)return;
  if(!std::isfinite(now)||now<=previous_){Stop("clock");return;}
  if(now-previous_>.06){Stop("tick_timeout");return;}
  const double dt=now-previous_; previous_=now;
  if(!feedback_fresh){Stop("feedback_timeout");return;}
  for(size_t i=0;i<29;++i)if(!std::isfinite(measured[i])||!std::isfinite(dq[i])){Stop("feedback_invalid");return;}
  if(event==Event::Fault){Stop("input_fault");return;}
  if(now-receipt_>.25){Stop("input_timeout");return;}
  if(event!=Event::None)receipt_=now;
  if(event==Event::Active&&!Valid(input)){Stop("input_joint_limit");return;}
  if(mode_==Mode::Waiting){
   if(event==Event::Idle||event==Event::Pinch)released_=true;
   if(event==Event::Active&&released_){
    anchor_input_=input;
    for(size_t i=0;i<7;++i)anchor_q_[i]=goal_[i]=q_[i+22];
    released_=false; mode_=Mode::Tracking;
   }
   return; // Engagement captures anchors without a target jump.
  }
  if(mode_==Mode::Tracking){
   if(event==Event::Pinch){
    mode_=Mode::Returning; released_=false; settled_=0;return_started_=now;
    for(size_t i=0;i<7;++i)goal_[i]=home_[i+22];
   }else if(event==Event::Idle){Stop("unexpected_idle");return;}
   else if(event==Event::Active){
    Arm candidate{};
    for(size_t i=0;i<7;++i)candidate[i]=anchor_q_[i]+input[i]-anchor_input_[i];
    if(!Valid(candidate)){Stop("rebased_joint_limit");return;}
    goal_=candidate;
   }
  }
  // Returning ignores active input, but still checks heartbeat and fault events.
  if(mode_==Mode::Returning&&now-return_started_>30){Stop("return_timeout");return;}
  auto next=q_; auto next_v=velocity_;
  for(size_t i=0;i<7;++i){
   const double delta=goal_[i]-q_[i+22],ad=accel_*dt;
   const double braking=std::sqrt(ad*ad+2*accel_*std::abs(delta))-ad;
   const double wanted=std::copysign(std::min(speed_,braking),delta);
   next_v[i]+=std::clamp(wanted-next_v[i],-ad,ad);
   next[i+22]+=next_v[i]*dt;
   if(next[i+22]<lower_[i]||next[i+22]>upper_[i]){Stop("target_joint_limit");return;}
  }
  q_=next;velocity_=next_v;
  if(mode_==Mode::Returning){
   bool settled=true;
   for(size_t i=0;i<7;++i)
    settled=settled&&std::abs(q_[i+22]-home_[i+22])<1e-6&&std::abs(velocity_[i])<1e-6
     &&std::abs(measured[i+22]-home_[i+22])<=.02&&std::abs(dq[i+22])<=.05;
   settled_=settled?settled_+dt:0;
   if(settled_>=.5){
    // Remove sub-microradian numerical residuals before a new anchor is captured.
    for(size_t i=0;i<7;++i)q_[i+22]=home_[i+22];
    velocity_.fill(0);mode_=Mode::Waiting;released_=false;
   }
  }
 }
};
