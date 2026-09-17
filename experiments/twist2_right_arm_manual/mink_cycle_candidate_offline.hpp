#pragma once
// OFFLINE sample consumer. No socket, SDK, publisher, policy or physical writer.
// A future native adapter must supply measured feedback, controls and a real
// path checker; this class does not manufacture a collision-free return path.
#include "vendor/json.hpp"
#include <array>
#include <cmath>
#include <functional>
#include <stdexcept>
#include <string>

class MinkCycleCandidateOffline {
public:
 using Q=std::array<double,29>;
 using Arm=std::array<double,7>;
 enum class State { Waiting, Tracking, Returning, Stopped };
 struct Feedback { Q q{},dq{}; double received=0; };
 struct Controls { bool r1=false,stop=false; };
 using PathCheck=std::function<bool(const Q&,const Q&)>;
 inline static constexpr Arm speed={1.5707963267948966,1.5707963267948966,
   1.5707963267948966,1.5707963267948966,3.141592653589793,3.141592653589793,3.141592653589793};
 static constexpr double acceleration=1.0471975511965976;
private:
 Q home_,target_;
 Arm velocity_{};
 Arm lower_,upper_;
 PathCheck path_;
 std::string session_,reason_;
 State state_=State::Waiting;
 unsigned long long sequence_=0,epoch_=0;
 bool seen_=false,released_=false;
 double previous_,receipt_,clock_,settled_=0,return_started_=0;
 void Require(bool ok,const char* why)const {if(!ok)throw std::runtime_error(why);}
 void Stop(const std::string& why){if(reason_.empty())reason_=why;state_=State::Stopped;}
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
 MinkCycleCandidateOffline(const Q& home,const Arm& lower,const Arm& upper,
      double now,PathCheck path):home_(home),target_(home),lower_(lower),upper_(upper),
      path_(std::move(path)),previous_(now),receipt_(now),clock_(now){
  Require(std::isfinite(now)&&now>=0&&bool(path_),"initialization");
  for(double v:home)Require(std::isfinite(v),"baseline");
  for(size_t i=0;i<7;++i)Require(std::isfinite(lower[i])&&std::isfinite(upper[i])&&
    lower[i]<upper[i]&&home[i+22]>=lower[i]&&home[i+22]<=upper[i],"joint_bounds");
 }
 State Mode()const{return state_;}
 const Q& Target()const{return target_;}
 const Arm& Velocity()const{return velocity_;}
 const std::string& Reason()const{return reason_;}
 auto Epoch()const{return epoch_;}
 bool Poll(double now,const Feedback& feedback,const Controls& controls){
  if(state_==State::Stopped)return false;
  try{
   Require(std::isfinite(now)&&now>=clock_,"clock");clock_=now;
   Require(controls.r1&&!controls.stop,"operator_stop");
   Require(std::isfinite(feedback.received)&&feedback.received<=now&&now-feedback.received<=.05,"feedback_timeout");
   for(size_t i=0;i<29;++i)Require(std::isfinite(feedback.q[i])&&std::isfinite(feedback.dq[i]),"feedback_invalid");
   Require(now-receipt_<=.25,"input_timeout");
   if(state_==State::Returning)Require(now-return_started_<=30.,"return_timeout");
   return true;
  }catch(const std::exception& e){Stop(e.what());return false;}
 }
 // Exactly one ordered input sample per call. No queue collapsing.
 bool Receive(const std::string& raw,double now,const Feedback& feedback,const Controls& controls,bool output_settled=true){
  if(!Poll(now,feedback,controls))return false;
  try{
   Require(now>previous_&&now-previous_<=.06,"sample_clock");
   const double dt=now-previous_;
   Require(raw.size()<=4096,"packet_size");
   const auto x=nlohmann::json::parse(raw);
   Require(x.at("schema")=="g1.mink.cycle.offline.v1"&&x.at("provenance")=="offline_only","offline_schema");
   Require(x.at("profile")=="right_arm_90_180_a60","profile");
   const auto seq=Counter(x.at("sequence")),epoch=Counter(x.at("epoch"));
   const auto session=x.at("session").get<std::string>();
   Require(!session.empty()&&session.size()<=128,"session");
   Require(!seen_||(session==session_&&seq>sequence_),"session_or_sequence");
   Require(epoch==epoch_,"epoch");
   const double age=Number(x.at("source_age_s"));Require(age>=0&&age<=.25,"source_timeout");
   const auto event=x.at("event").get<std::string>();
   Require(event=="idle"||event=="active"||event=="pinch"||event=="tracking_disengaged"||event=="return","event");
   Require(x.at("joints").is_array()&&x.at("joints").size()==7,"joint_count");
   Q next=target_;Arm v{};
   for(size_t i=0;i<7;++i){
    next[i+22]=Number(x.at("joints")[i]);
    Require(next[i+22]>=lower_[i]&&next[i+22]<=upper_[i],"joint_limit");
    v[i]=(next[i+22]-target_[i+22])/dt;
    Require(std::abs(v[i])<=speed[i]+1e-7,"speed");
    Require(std::abs(v[i]-velocity_[i])<=acceleration*dt+1e-7,"acceleration");
   }
   State next_state=state_;bool next_released=released_;
   bool begin_return=false;
   if(state_==State::Waiting){
    Require(next==target_,"waiting_target_changed");
    if(event=="idle"||event=="pinch"||event=="tracking_disengaged")next_released=true;
    else if(event=="active"){Require(released_,"idle_required");next_state=State::Tracking;next_released=false;}
    else Require(false,"unexpected_return");
   }else if(state_==State::Tracking){
    if(event=="pinch"||event=="tracking_disengaged"){
     next_state=State::Returning;begin_return=true;next_released=false;
    }else Require(event=="active","unexpected_tracking_event");
   }else Require(event=="return","return_required");
   Require(path_(target_,next),"path_rejected");
   // Commit only after every validation, including the path callback, passes.
   target_=next;velocity_=v;state_=next_state;released_=next_released;
   seen_=true;sequence_=seq;session_=session;previous_=receipt_=now;
   if(begin_return){++epoch_;return_started_=now;settled_=0;}
   if(state_==State::Returning){
    bool settled=output_settled;
    for(size_t i=0;i<7;++i)settled=settled&&std::abs(target_[22+i]-home_[22+i])<1e-6&&
      std::abs(velocity_[i])<1e-6&&std::abs(feedback.q[22+i]-home_[22+i])<=.02&&std::abs(feedback.dq[22+i])<=.05;
    settled_=settled?settled_+dt:0;
    if(settled_>=.5){state_=State::Waiting;released_=false;}
   }
   return true;
  }catch(const std::exception& e){Stop(e.what());return false;}
 }
};
