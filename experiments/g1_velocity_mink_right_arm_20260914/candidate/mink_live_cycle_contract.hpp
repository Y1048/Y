#pragma once
// Live-cycle protocol candidate. Transport and measured-state adapter are separate.
// Consumes PC geometry-checked samples; does not generate a return path.
#include "vendor/json.hpp"
#include <array>
#include <cmath>
#include <functional>
#include <stdexcept>
#include <string>
#include <set>

class MinkLiveCycleContract {
public:
 using Q=std::array<double,29>;
 using Arm=std::array<double,7>;
 enum class State { Waiting, Tracking, Returning, Stopped };
 struct Feedback { Q q{},dq{}; double received=0; };
 struct Controls { bool stop=false; };
 using PathCheck=std::function<bool(const Q&,const Q&)>;
 inline static constexpr Arm speed={1.5707963267948966,1.5707963267948966,
   1.5707963267948966,1.5707963267948966,3.141592653589793,3.141592653589793,3.141592653589793};
 static constexpr double acceleration=1.0471975511965976;
 // Candidate readiness acceptance only, from trial 7966 sustained pose offsets.
 // Same local joint order for both arms. Runtime tracking protection is separate.
 inline static constexpr Arm ready_error={.02,.09,.02,.04,.025,.02,.02};
 static bool MeasuredReadyJoint(double q,double dq,double target,size_t local_joint){
  return std::isfinite(q)&&std::isfinite(dq)&&std::isfinite(target)&&
   std::abs(q-target)<=ready_error.at(local_joint)&&std::abs(dq)<=.05;
 }
 static bool MeasuredInitialReadyJoint(double q,double dq,double target,size_t local_joint){
  // A continuous gait can inject upper-body joint velocity indefinitely.  For
  // initial arming, require bounded position tracking across a full gait cycle
  // instead of an instantaneous near-zero velocity.  Return completion keeps
  // using MeasuredReadyJoint and therefore retains its velocity requirement.
  return std::isfinite(q)&&std::isfinite(dq)&&std::isfinite(target)&&
   std::abs(q-target)<=ready_error.at(local_joint);
 }
private:
 Q home_,target_;
 Arm speed_;double acceleration_;std::string profile_;
 double sample_time_=0;bool sampled_=false;
 Arm velocity_{};
 Arm lower_,upper_;
 PathCheck path_;
 std::string session_,reason_;
 State state_=State::Waiting;
 bool auto_handback_=false,auto_handback_ready_=false;
 unsigned long long sequence_=0,epoch_=0;
 bool seen_=false,released_=false;
 double previous_,receipt_,clock_,settled_=0,return_started_=0;
 void Require(bool ok,const char* why)const {if(!ok)throw std::runtime_error(why);}
 void Stop(const std::string& why){reason_=why;state_=State::Stopped;}
 bool RecoverableTrackingFault(const std::string& why)const{
  static const std::set<std::string> recoverable={
   "joint_limit","speed","acceleration","unexpected_tracking_event","path_rejected"};
  return state_==State::Tracking&&recoverable.count(why)!=0;
 }
 void BeginAutomaticHandback(const std::string& why,double now){
  if(reason_.empty())reason_=why;
  state_=State::Returning;auto_handback_=true;auto_handback_ready_=false;
  released_=false;++epoch_;return_started_=now;settled_=0;
 }
 static double Number(const nlohmann::json& x){
  if(!x.is_number())throw std::runtime_error("number_type");
  double v=x.get<double>();if(!std::isfinite(v))throw std::runtime_error("nonfinite");return v;
 }
 static unsigned long long Counter(const nlohmann::json& x){
  if(!x.is_number_integer() || (x.is_number_integer()&&!x.is_number_unsigned()&&x.get<long long>()<0))
   throw std::runtime_error("counter_type");
  return x.get<unsigned long long>();
 }
public:
 MinkLiveCycleContract(const Q& home,const Arm& lower,const Arm& upper,
      double now,PathCheck path,const std::string& profile="today"):home_(home),target_(home),lower_(lower),upper_(upper),
      path_(std::move(path)),previous_(now),receipt_(now),clock_(now){
  profile_=profile;Require(profile=="today"||profile=="yesterday","profile_configuration");
  speed_=speed;acceleration_=acceleration;
  if(profile=="yesterday"){speed_.fill(.7);acceleration_=10.*3.141592653589793/180.;}
  Require(std::isfinite(now)&&now>=0&&bool(path_),"initialization");
  for(double v:home)Require(std::isfinite(v),"baseline");
  for(size_t i=0;i<7;++i)Require(std::isfinite(lower[i])&&std::isfinite(upper[i])&&
    lower[i]<upper[i]&&home[i+22]>=lower[i]&&home[i+22]<=upper[i],"joint_bounds");
 }
 State Mode()const{return state_;}
 const Q& Target()const{return target_;}
 const Arm& Velocity()const{return velocity_;}
 const std::string& Reason()const{return reason_;}
 bool AutomaticHandbackRequested()const{return auto_handback_;}
 bool AutomaticHandbackReady()const{return auto_handback_ready_;}
 bool ContinueFromSafeHold(){
  if(state_!=State::Waiting||!auto_handback_ready_)return false;
  auto_handback_=false;auto_handback_ready_=false;reason_.clear();return true;
 }
 bool RequestAutomaticHandback(const std::string& why,double now){
  if(state_==State::Stopped||!std::isfinite(now)||now<clock_)return false;
  if(state_==State::Returning)return auto_handback_;
  if(state_==State::Waiting){
   if(reason_.empty())reason_=why;
   auto_handback_=true;auto_handback_ready_=true;released_=false;
   return true;
  }
  BeginAutomaticHandback(why,now);return true;
 }
 auto Epoch()const{return epoch_;}
 const std::string& Session()const{return session_;}
 bool Poll(double now,const Feedback& feedback,const Controls& controls){
  if(state_==State::Stopped)return false;
  try{
   Require(std::isfinite(now)&&now>=clock_,"clock");clock_=now;
   Require(!controls.stop,"operator_stop");
   Require(std::isfinite(feedback.received)&&feedback.received<=now&&now-feedback.received<=.05,"feedback_timeout");
   for(size_t i=0;i<29;++i)Require(std::isfinite(feedback.q[i])&&std::isfinite(feedback.dq[i]),"feedback_invalid");
   // A fresh idle packet establishes the session, but Waiting may last as long
   // as the operator needs before engage. Apply the packet watchdog only after
   // motion tracking or a coordinated return has begun.
   Require((state_!=State::Tracking&&state_!=State::Returning)||!seen_||now-receipt_<=.25,"input_timeout");
   if(state_==State::Returning)Require(now-return_started_<=30.,"return_timeout");
   return true;
  }catch(const std::exception& e){Stop(e.what());return false;}
 }
 // Exactly one ordered input sample per call. No queue collapsing.
 bool Receive(const std::string& raw,double now,const Feedback& feedback,const Controls& controls,bool output_settled=true){
  if(!Poll(now,feedback,controls))return false;
  try{
   Require(now>=previous_,"receipt_clock");
   Require(raw.size()<=4096,"packet_size");
   std::vector<std::set<std::string>> keys;
   auto callback=[&](int,nlohmann::json::parse_event_t event,nlohmann::json& item){
    if(event==nlohmann::json::parse_event_t::object_start)keys.emplace_back();
    if(event==nlohmann::json::parse_event_t::key)Require(keys.back().insert(item.get<std::string>()).second,"duplicate_key");
    if(event==nlohmann::json::parse_event_t::object_end)keys.pop_back();
    return true;};
   const auto x=nlohmann::json::parse(raw,callback);
   const auto event=x.at("event").get<std::string>();
   Require(event=="idle"||event=="active"||event=="pinch"||event=="tracking_disengaged"||event=="return","event");
   const double sample_time=Number(x.at("sample_time_s"));
   const double raw_dt=sampled_?sample_time-sample_time_:1./60.;
   Require(sample_time>=0&&raw_dt>0,"sample_clock");
   // Windows/Unity may pause while the robot is already measured-ready.  An
   // idle packet cannot move the Waiting target, so rebase its derivative
   // interval instead of turning a harmless display stall into a hard stop.
   const bool waiting_idle_gap=
       state_==State::Waiting&&event=="idle"&&raw_dt>.06;
   Require(raw_dt<=.06||waiting_idle_gap,"sample_clock");
   const double dt=waiting_idle_gap?1./60.:raw_dt;
   Require(x.at("schema")=="g1.mink.cycle.live.v1"&&x.at("command_provenance")=="live_mink"&&!x.value("simulation_only",false),"live_schema");
   Require(x.at("profile")==profile_,"profile");
   const auto seq=Counter(x.at("sequence")),epoch=Counter(x.at("epoch"));
   const auto session=x.at("session").get<std::string>();
   Require(!session.empty()&&session.size()<=128&&session.rfind("replay-",0)!=0,"session");
   Require(!seen_||(session==session_&&seq>sequence_),"session_or_sequence");
   Require(epoch==epoch_,"epoch");
   const double age=Number(x.at("source_age_s"));Require(age>=0&&age<=.25,"source_timeout");
   Require(Number(x.at("clearance_m"))>=.005-1e-7,"clearance");
   Require(x.at("joints").is_array()&&x.at("joints").size()==7,"joint_count");
   // One final tracking packet may arrive before the PC receives the returning
   // ACK. Ignore it without changing the last accepted target.
   if(state_==State::Returning&&auto_handback_&&event!="return")return true;
   Q next=target_;Arm v{};
   for(size_t i=0;i<7;++i){
    next[i+22]=Number(x.at("joints")[i]);
    Require(next[i+22]>=lower_[i]&&next[i+22]<=upper_[i],"joint_limit");
    v[i]=(next[i+22]-target_[i+22])/dt;
    Require(std::abs(v[i])<=speed_[i]+1e-7,"speed");
    Require(std::abs(v[i]-velocity_[i])<=acceleration_*dt+1e-7,"acceleration");
   }
   State next_state=state_;bool next_released=released_;
   bool begin_return=false;
   if(state_==State::Waiting){
    for(size_t i=0;i<7;++i)Require(std::abs(next[i+22]-target_[i+22])<=1e-6,"waiting_target_changed");
    next=target_;v.fill(0);
    if(event=="idle"||event=="pinch"||event=="tracking_disengaged")next_released=true;
    else if(event=="active"){Require(released_,"idle_required");next_state=State::Tracking;next_released=false;}
    else Require(event=="return"&&epoch_>0,"unexpected_return");
   }else if(state_==State::Tracking){
    if(event=="pinch"||event=="tracking_disengaged"){
     next_state=State::Returning;begin_return=true;next_released=false;
    }else Require(event=="active","unexpected_tracking_event");
   }else Require(event=="return","return_required");
   Require(path_(target_,next),"path_rejected");
   // Commit only after every validation, including the path callback, passes.
   target_=next;velocity_=v;state_=next_state;released_=next_released;
   seen_=true;sequence_=seq;session_=session;previous_=receipt_=now;sample_time_=sample_time;sampled_=true;
   if(begin_return){++epoch_;return_started_=now;settled_=0;}
   if(state_==State::Returning){
    bool settled=output_settled;
    for(size_t i=0;i<7;++i)settled=settled&&std::abs(target_[22+i]-home_[22+i])<1e-6&&
      std::abs(velocity_[i])<1e-6&&MeasuredReadyJoint(feedback.q[22+i],feedback.dq[22+i],home_[22+i],i);
    settled_=settled?settled_+dt:0;
    if(settled_>=.5){state_=State::Waiting;released_=false;auto_handback_ready_=auto_handback_;}
   }
   return true;
  }catch(const std::exception& e){
   if(RecoverableTrackingFault(e.what())){BeginAutomaticHandback(e.what(),now);return true;}
   Stop(e.what());return false;
  }
 }
};
