#pragma once
// Offline fixed-grid reference resampler. No transport, SDK or motor output.
#include "mink_cycle_candidate_offline.hpp"
#include <algorithm>
#include <deque>
#include <optional>

class MinkResamplerOffline {
public:
 using C=MinkCycleCandidateOffline;
 using Q=C::Q;using Arm=C::Arm;
 static constexpr double input_dt=1./60.,output_dt=1./500.;
 static constexpr double delay=2.*input_dt;
 struct Sample {Q q;Arm velocity,acceleration;};
private:
 struct Knot {std::uint64_t index;Arm q;};
 Q baseline_;Arm low_,high_,last_,previous_velocity_{};
 std::deque<Knot> knots_;
 C::PathCheck path_;
 double start_,clock_,previous_step_,receipt_;
 std::uint64_t sequence_=0;
 bool stepped_=false;
 std::string reason_;
 std::optional<Sample> output_;
 bool Fail(const std::string& why){if(reason_.empty())reason_=why;output_.reset();return false;}
 bool Clock(double now){if(!reason_.empty())return false;if(!std::isfinite(now)||now+1e-9<clock_)return Fail("clock");clock_=std::max(clock_,now);return true;}
 const Arm& At(std::uint64_t index)const{
  if(knots_.empty()||index<knots_.front().index||index>knots_.back().index)throw std::runtime_error("sample_underrun");
  return knots_[static_cast<size_t>(index-knots_.front().index)].q;
 }
public:
 MinkResamplerOffline(const Q& baseline,const Arm& low,const Arm& high,double start,C::PathCheck path):
 baseline_(baseline),low_(low),high_(high),path_(std::move(path)),start_(start),clock_(start),previous_step_(start),receipt_(start){
  if(!std::isfinite(start)||start<0||!path_)throw std::invalid_argument("initialization");
  for(double x:baseline)if(!std::isfinite(x))throw std::invalid_argument("baseline");
  for(size_t i=0;i<7;++i){last_[i]=baseline[22+i];if(!std::isfinite(low[i])||!std::isfinite(high[i])||low[i]>=high[i]||last_[i]<low[i]||last_[i]>high[i])throw std::invalid_argument("bounds");}
  knots_.push_back({0,last_});
 }
 const auto& Reason()const{return reason_;}
 const auto& Output()const{return output_;}
 // Upstream must supply the fixed simulation grid, not jittered receipt time.
 bool Push(const Arm& q,std::uint64_t sequence,double source,double received){
  if(!Clock(received))return false;
  if(sequence!=sequence_+1)return Fail("sequence");
  if(!std::isfinite(source)||std::abs(source-(start_+static_cast<double>(sequence)*input_dt))>1e-8)return Fail("source_grid");
  if(received+1e-9<source||received-source>.02)return Fail("source_age");
  Arm velocity{};
  for(size_t i=0;i<7;++i){
   if(!std::isfinite(q[i])||q[i]<low_[i]||q[i]>high_[i])return Fail("joint_limit");
   velocity[i]=(q[i]-last_[i])/input_dt;
   if(std::abs(velocity[i])>C::speed[i]+1e-7)return Fail("speed");
   if(std::abs(velocity[i]-previous_velocity_[i])>C::acceleration*input_dt+1e-7)return Fail("acceleration");
  }
  if(knots_.size()>=64)return Fail("queue_overflow");
  knots_.push_back({sequence,q});sequence_=sequence;last_=q;previous_velocity_=velocity;receipt_=received;return true;
 }
 bool Step(double now,bool owner_ok){
  if(!Clock(now))return false;
  if(!owner_ok)return Fail("owner_stop");
  if((stepped_&&std::abs(now-previous_step_-output_dt)>1e-8)||(!stepped_&&std::abs(now-start_)>1e-8))return Fail("output_grid");
  if(now-receipt_>.25)return Fail("input_timeout");
  Sample next{baseline_,{}, {}};
  try{
   const double elapsed=now-start_-delay;
   if(elapsed>=0){
    const double grid=elapsed/input_dt;
    const auto k=static_cast<std::uint64_t>(std::floor(grid));const double u=grid-static_cast<double>(k);
    const auto& a=At(k==0?0:k-1);const auto& b=At(k);const auto& c=At(k+1);
    for(size_t i=0;i<7;++i){
     next.q[i+22]=.5*(1-u)*(1-u)*a[i]+(.5+u-u*u)*b[i]+.5*u*u*c[i];
     next.velocity[i]=((1-u)*(b[i]-a[i])+u*(c[i]-b[i]))/input_dt;
     next.acceleration[i]=(c[i]-2*b[i]+a[i])/(input_dt*input_dt);
     if(std::abs(next.velocity[i])>C::speed[i]+1e-6||std::abs(next.acceleration[i])>C::acceleration+1e-6)return Fail("output_derivative");
    }
    while(knots_.size()>3&&knots_.front().index+1<k)knots_.pop_front();
   }
   if(!path_(output_?output_->q:baseline_,next.q))return Fail("path_rejected");
  }catch(const std::exception& e){return Fail(e.what());}
  output_=next;previous_step_=now;stepped_=true;return true;
 }
};
