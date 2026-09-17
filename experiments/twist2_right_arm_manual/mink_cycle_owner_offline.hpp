#pragma once
// OFFLINE reference composition only. No SDK, transport or motor writer.
#include "mink_resampler_offline.hpp"
#include "offline_hg_native_decoder.hpp"
#include "offline_state_continuity.hpp"

class MinkCycleOwnerOffline {
public:
 using Cycle=MinkCycleCandidateOffline;
 using Q=Cycle::Q;
 struct PolicyPositions {
  std::array<double,12> q{}; // Already decoded motor-order positions, NOT actions.
  std::uint64_t state_sequence=0;
  double created=0;
 };
 struct Reference {Q q;std::uint64_t state_sequence,epoch;Cycle::Arm velocity{},acceleration{};
  std::uint64_t policy_state_sequence=0;double policy_created=0;
 };
 struct PolicyTicket {std::uint64_t id;DecodedOfflineHgState snapshot;double requested;};
private:
 Cycle cycle_;
 Q ready_;
 std::optional<MinkResamplerOffline> resampler_;
 std::uint64_t input_sequence_=0;
 std::optional<double> output_time_;
 OfflineStateContinuity continuity_;
 OfflineHealthLimits limits_;
 Cycle::PathCheck full_path_;
 std::optional<DecodedOfflineHgState> state_;
 std::optional<Reference> reference_;
 struct CachedPolicy {PolicyPositions policy;double input_received;};
 std::optional<PolicyTicket> pending_policy_;
 std::optional<CachedPolicy> cached_policy_;
 std::uint64_t policy_request_id_=0;
 std::uint64_t sequence_=0;
 std::string reason_;
 double clock_;
 bool Fail(const std::string& why){if(reason_.empty())reason_=why;reference_.reset();pending_policy_.reset();cached_policy_.reset();return false;}
 Cycle::Feedback Feedback()const{return {state_->sample.q,state_->sample.dq,state_->sample.received_at};}
 Cycle::Controls Controls(bool stop)const{return {state_->health.deadman,stop||state_->health.emergency_stop};}
public:
 MinkCycleOwnerOffline(const Q& ready,const Cycle::Arm& low,const Cycle::Arm& high,
  double now,OfflineHealthLimits limits,Cycle::PathCheck arm_path,Cycle::PathCheck full_path,bool resample=false):
  cycle_(ready,low,high,now,arm_path),ready_(ready),limits_(limits),full_path_(std::move(full_path)),clock_(now){
  if(resample)resampler_.emplace(ready,low,high,now,std::move(arm_path));
  if(!full_path_)throw std::invalid_argument("missing_full_body_path_checker");
  for(double v:{limits.policy_age,limits.roll,limits.pitch,limits.velocity,limits.temperature})
   if(!std::isfinite(v)||v<=0)throw std::invalid_argument("health_limits");
 }
 const auto& Reason()const{return reason_;}
 const auto& Candidate()const{return reference_;}
 std::uint64_t StateSequence()const{return sequence_;}
 auto Epoch()const{return cycle_.Epoch();}
 auto Mode()const{return reason_.empty()?cycle_.Mode():Cycle::State::Stopped;}
 bool Poll(double now,bool stop=false){
  if(!reason_.empty())return false;
  if(!std::isfinite(now)||now<clock_)return Fail("clock");
  clock_=now;
  if(!state_)return Fail("missing_measured_state");
  auto error=continuity_.Poll(now);if(!error.empty())return Fail(error);
  if(!cycle_.Poll(now,Feedback(),Controls(stop)))return Fail(cycle_.Reason());
  return true;
 }
 // Raw fixture/native-packed bytes only. Not DDS CDR or producer JSON.
 bool Observe(const std::vector<std::uint8_t>& bytes,const std::string& profile,double received,double now){
  if(!reason_.empty())return false;
  reference_.reset();
  if(!std::isfinite(now)||now<clock_)return Fail("clock");
  try{
   auto decoded=DecodeOfflineHgNative(bytes,profile,sequence_+1,received);
   auto error=continuity_.Check(decoded.robot_tick,received,now);
   if(!error.empty())return Fail(error);
   error=CheckOfflineStateHealth(decoded.sample,decoded.health,limits_);
   if(!error.empty())return Fail(error);
   state_=decoded;++sequence_;
   return Poll(now);
  }catch(const std::exception& e){return Fail(e.what());}
 }
 bool Receive(const std::string& packet,double now,bool stop=false){
  reference_.reset();
  if(!Poll(now,stop))return false;
  bool output_settled=!resampler_;
  if(resampler_&&resampler_->Output()&&output_time_&&now-*output_time_<=.002+1e-9){
   output_settled=true;const auto& out=*resampler_->Output();
   for(size_t i=0;i<7;++i)output_settled=output_settled&&
    std::abs(out.q[22+i]-ready_[22+i])<1e-6&&std::abs(out.velocity[i])<1e-6;
  }
  if(!cycle_.Receive(packet,now,Feedback(),Controls(stop),output_settled))return Fail(cycle_.Reason());
  if(resampler_){
   Cycle::Arm q{};for(size_t i=0;i<7;++i)q[i]=cycle_.Target()[22+i];
   if(!resampler_->Push(q,++input_sequence_,now,now))return Fail(resampler_->Reason());
  }
  return true;
 }
 // Policy worker receives an immutable state copy, not a pointer to live state.
 std::optional<PolicyTicket> BeginPolicy(double now){
  if(!Poll(now))return std::nullopt;
  if(pending_policy_){Fail("policy_request_pending");return std::nullopt;}
  pending_policy_=PolicyTicket{++policy_request_id_,*state_,now};return pending_policy_;
 }
 bool SubmitPolicy(std::uint64_t request,const PolicyPositions& policy,double now){
  if(!Poll(now))return false;
  if(!pending_policy_||request!=pending_policy_->id)return Fail("policy_request_mismatch");
  const auto& ticket=*pending_policy_;
  if(policy.state_sequence!=ticket.snapshot.sample.sequence)return Fail("policy_state_mismatch");
  const double budget=std::min(limits_.policy_age,.025);
  if(!std::isfinite(policy.created)||policy.created<ticket.requested||policy.created>now||
    now-ticket.snapshot.sample.received_at>budget)return Fail("policy_time");
  for(size_t i=0;i<12;++i)
   if(!std::isfinite(policy.q[i])||policy.q[i]<offline_twist2::kLower[i]+offline_twist2::kJointLimitMargin||
    policy.q[i]>offline_twist2::kUpper[i]-offline_twist2::kJointLimitMargin)return Fail("reference_joint_limit");
  cached_policy_=CachedPolicy{policy,ticket.snapshot.sample.received_at};pending_policy_.reset();
  reference_.reset();return true;
 }
 bool ComposeHeldPolicy(double now,bool stop=false){
  reference_.reset();
  if(!Poll(now,stop))return false;
  if(!cached_policy_)return Fail("missing_policy");
  if(now-cached_policy_->input_received>std::min(limits_.policy_age,.025))return Fail("policy_expired");
  return ComposeReference(cached_policy_->policy,now);
 }
 // A reference snapshot, deliberately NOT a 500 Hz command or write permit.
 bool Compose(const PolicyPositions& policy,double now,bool stop=false){
  reference_.reset();
  if(!Poll(now,stop))return false;
  if(policy.state_sequence!=sequence_)return Fail("policy_state_mismatch");
  if(!std::isfinite(policy.created)||policy.created<state_->sample.received_at||
    policy.created>now||now-policy.created>limits_.policy_age)return Fail("policy_time");
  return ComposeReference(policy,now);
 }
private:
 bool ComposeReference(const PolicyPositions& policy,double now){
  Q q=cycle_.Target();Cycle::Arm velocity{},acceleration{};
  if(resampler_){
   if(!resampler_->Step(now,true))return Fail(resampler_->Reason());
   const auto& out=*resampler_->Output();q=out.q;velocity=out.velocity;acceleration=out.acceleration;
  }
  for(size_t i=0;i<12;++i)q[i]=policy.q[i];
  for(size_t i=0;i<29;++i)
   if(!std::isfinite(q[i])||q[i]<offline_twist2::kLower[i]+offline_twist2::kJointLimitMargin||
     q[i]>offline_twist2::kUpper[i]-offline_twist2::kJointLimitMargin)return Fail("reference_joint_limit");
  // Check from measured full-body pose, including changed leg targets.
  try{if(!full_path_(state_->sample.q,q))return Fail("full_body_path_rejected");}
  catch(const std::exception& e){return Fail(e.what());}
  reference_=Reference{q,sequence_,cycle_.Epoch(),velocity,acceleration,policy.state_sequence,policy.created};output_time_=now;return true;
 }
};
