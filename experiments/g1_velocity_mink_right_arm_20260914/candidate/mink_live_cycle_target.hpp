#pragma once
#include "mink_live_cycle_contract.hpp"
#include "mink_udp_target.hpp"
#include "offline_twist2_constants.hpp"
#include <cstdlib>
#include <mutex>
class MinkLiveCycleTarget {
 using C=MinkLiveCycleContract;using J=nlohmann::json;
 std::mutex mutex_;MinkUdpTarget initializer_;std::unique_ptr<C> cycle_;
 C::Q target_;C::Feedback feedback_;std::function<double()> clock_;
 std::string profile_,reason_,pending_handback_;double settle_start_=-1;unsigned long long ack_seq_=0;
public:
 static constexpr double kLiveTargetMargin=0.0801;
 MinkLiveCycleTarget(const C::Q& baseline,double now,std::function<double()> clock,bool):
  initializer_(baseline,now,clock,false),target_(baseline),clock_(clock){
  const char* p=std::getenv("G1_MINK_SPEED_PROFILE");profile_=p?p:"";
  if(profile_!="today"&&profile_!="yesterday")throw std::runtime_error("explicit speed profile required");
 }
 void Feedback(const C::Q& q,const C::Q& dq,double received){std::lock_guard<std::mutex> lock(mutex_);feedback_={q,dq,received};}
 std::string Phase(){std::lock_guard<std::mutex> lock(mutex_);
  if(!cycle_)return "arm_initializing";
  if(cycle_->Mode()==C::State::Waiting)return "udp_ready";
  if(cycle_->Mode()==C::State::Returning)return "arm_returning";
  return cycle_->Mode()==C::State::Tracking?"arm_tracking":"cycle_stopped";
 }
 bool Ready(){std::lock_guard<std::mutex> lock(mutex_);return bool(cycle_);}
 bool AutomaticHandbackReady(){std::lock_guard<std::mutex> lock(mutex_);return cycle_&&cycle_->AutomaticHandbackReady();}
 std::string AutomaticHandbackReason(){std::lock_guard<std::mutex> lock(mutex_);return cycle_?cycle_->Reason():std::string{};}
 bool ContinueFromSafeHold(){std::lock_guard<std::mutex> lock(mutex_);
  if(!cycle_||!cycle_->ContinueFromSafeHold())return false;
  reason_.clear();pending_handback_.clear();return true;
 }
 void RequestAutomaticHandback(const std::string& why){std::lock_guard<std::mutex> lock(mutex_);
  if(pending_handback_.empty())pending_handback_=why;
  if(cycle_)cycle_->RequestAutomaticHandback(pending_handback_,clock_());
 }
 std::string Poll(double){std::lock_guard<std::mutex> lock(mutex_);double now=clock_();
  if(cycle_&&!cycle_->Poll(now,feedback_,{false}))reason_=cycle_->Reason();
  return reason_;}
 bool Receive(const std::string& raw,double){std::lock_guard<std::mutex> lock(mutex_);double now=clock_();
  if(!reason_.empty())return false;
  try{
   const auto p=J::parse(raw);
   if(p.at("schema")!="g1.mink.cycle.live.v1"||p.at("profile")!=profile_)throw std::runtime_error("cycle schema/profile");
   if(!cycle_){if(p.at("event")!="idle")throw std::runtime_error("engage_before_measured_ready");return true;}
   if(!cycle_->Receive(raw,now,feedback_,{false})){reason_=cycle_->Reason();return false;}
   target_=cycle_->Target();return true;
  }catch(const std::exception& e){reason_=e.what();return false;}
 }
 C::Q Update(double,bool blend_complete){std::lock_guard<std::mutex> lock(mutex_);double now=clock_();
  if(!reason_.empty())throw std::runtime_error(reason_);
  if(!cycle_){
   target_=initializer_.Update(now,blend_complete);
   bool settled=initializer_.Ready()&&feedback_.received<=now&&now-feedback_.received<=.05;
   for(size_t i=15;i<29;++i)settled=settled&&C::MeasuredInitialReadyJoint(feedback_.q[i],feedback_.dq[i],target_[i],(i-15)%7);
   if(!settled)settle_start_=-1;else if(settle_start_<0)settle_start_=now;
   if(settle_start_>=0&&now-settle_start_>=1.0){
    C::Arm lo{},hi{};for(size_t i=0;i<7;++i){lo[i]=offline_twist2::kLower[i+22]+kLiveTargetMargin;hi[i]=offline_twist2::kUpper[i+22]-kLiveTargetMargin;}
    // Existing path trusts PC geometry checks; do not call this a measured
    // full-body collision checker. Packet clearance is checked by contract.
    cycle_=std::make_unique<C>(target_,lo,hi,now,[](const auto&,const auto&){return true;},profile_);
    if(!pending_handback_.empty())cycle_->RequestAutomaticHandback(pending_handback_,now);
   }
  }
  return target_;
 }
 J Acknowledgement(const std::string& token){std::lock_guard<std::mutex> lock(mutex_);
  std::string state="initializing";
  if(cycle_){switch(cycle_->Mode()){case C::State::Waiting:state="waiting";break;case C::State::Tracking:state="tracking";break;case C::State::Returning:state="returning";break;case C::State::Stopped:state="stopped";break;}}
  J ack{{"schema","g1.mink.cycle.ack.v1"},{"relay_token",token},{"profile",profile_},{"sequence",++ack_seq_},{"epoch",cycle_?cycle_->Epoch():0},{"session",cycle_?cycle_->Session():""},{"state",state}};
  if(!cycle_){
   J blockers=J::array();
   for(size_t i=15;i<29;++i){
    const double error=std::abs(feedback_.q[i]-target_[i]);
    const double rate=std::abs(feedback_.dq[i]);
    if(!C::MeasuredInitialReadyJoint(feedback_.q[i],feedback_.dq[i],target_[i],(i-15)%7))
     blockers.push_back(J{{"joint",i},{"error_rad",error},{"limit_rad",C::ready_error[(i-15)%7]},{"speed_rad_s_observed",rate},{"speed_used_for_initial_ready",false}});
   }
   ack["ready_blockers"]=blockers;
   ack["initial_target_complete"]=initializer_.Ready();
  }
  return ack;
 }
};
