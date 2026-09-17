#pragma once
#include "native_composition_offline.hpp"
#include "offline_writer_study.hpp"
#include "raw_input_watch_offline.hpp"
#include "offline_observation_history.hpp"
#include "offline_blend.hpp"

// Single-thread event harness only. No SDK, timer, transport or motor command.
class OfflineOwner {
 NativeCompositionOffline composition;
 RawInputWatchOffline vr;
 OfflineObservationHistory history;
 std::optional<OfflineObservationFrame> observation;
 std::optional<DecodedOfflineHgState> state;
 OfflineStateContinuity state_continuity;
 std::vector<std::uint8_t> latest_bytes;
 std::string latest_profile;
 std::uint64_t received_sequence=0,request_state_sequence=0;
 std::optional<OfflineWriterStudy> writer;
 std::optional<OfflineDesiredPosition> desired;
 std::optional<std::uint64_t> pending;
 std::uint64_t request=0;
 double requested_at=0;
 std::string reason;
 bool startup_blend=false;
 bool torque_fade=false;
 std::optional<std::array<float,29>> captured_torque;
 double torque_start=0;
 std::optional<std::array<double,29>> captured;
 double blend_start=0;
 float request_alpha=1;
 std::string phase="settling",prepared_mode;
 std::optional<double> tracking_since;
 std::optional<double> startup_started;
 bool CheckStartupDeadline(double now){
  if(!startup_blend||phase=="active")return true;
  if(startup_started&&now-*startup_started>=15.0){Stop("startup_ready_timeout");return false;}
  return true;
 }
 // Experimental offline readiness criteria, not hardware-approved limits.
 void RefreshReadiness(){
  if(!startup_blend||phase=="active"||!reason.empty())return;
  if(!desired||!writer||request_alpha<1){tracking_since.reset();return;}
  bool tracking=true;
  for(std::size_t i=0;i<29;++i){
   if(std::abs(state->sample.q[i]-desired->q[i])>.025||
      std::abs(state->sample.q[i]-writer->LastTarget()[i])>.025||
      std::abs(state->sample.dq[i])>.1)tracking=false;
  }
  if(!tracking)tracking_since.reset();
  else if(!tracking_since)tracking_since=state->sample.received_at;
  phase=tracking_since&&state->sample.received_at-*tracking_since>=1.0
    ?"awaiting_alignment":"verifying_tracking";
 }
public:
 explicit OfflineOwner(bool enable_startup_blend=false,bool enable_torque_fade=false)
  :composition(enable_startup_blend),startup_blend(enable_startup_blend),torque_fade(enable_torque_fade){
  if(torque_fade&&!startup_blend)throw std::invalid_argument("torque fade requires startup blend");
 }
 const auto& Phase()const{return phase;}
 const auto& Reason()const{return reason;}
 const auto& Desired()const{return desired;}
 const auto& Writer()const{return writer;}
 const auto& Observation()const{return observation;}
 std::size_t HistoryCommits()const{return history.Commits();}
 std::uint64_t LatestStateSequence()const{return received_sequence;}
 std::uint64_t RequestStateSequence()const{return request_state_sequence;}
 void Stop(const std::string& why){
  if(reason.empty())reason=why;
  phase="stopped";
  pending.reset();desired.reset();observation.reset();history.Stop();composition.Stop(reason);vr.Stop(reason);
  captured_torque.reset();
  if(writer)writer->Stop(reason);
 }
 bool ReceiveState(const std::vector<std::uint8_t>& bytes,const std::string& profile,double received,double now){
  if(!reason.empty())return false;
  if(!CheckStartupDeadline(now))return false;
  try{
   auto decoded=DecodeOfflineHgNative(bytes,profile,received_sequence+1,received);
   auto why=state_continuity.Check(decoded.robot_tick,received,now);
   if(why.empty())why=CheckOfflineStateHealth(decoded.sample,decoded.health,{.01,.15,.15,1.5,75});
   if(!why.empty()){Stop(why);return false;}
   state=decoded;latest_bytes=bytes;latest_profile=profile;++received_sequence;
   if(!startup_started)startup_started=now;
   RefreshReadiness();return true;
  }catch(const std::exception& e){Stop(e.what());return false;}
 }
 bool ReceiveVR(const std::string& raw,double received){
  if(!reason.empty())return false;
  if(!CheckStartupDeadline(received))return false;
  const auto freshness=state_continuity.Poll(received);
  if(!freshness.empty()){Stop(freshness);return false;}
  if(!vr.Receive(raw,received)){Stop(vr.Reason());return false;}
  if(startup_blend&&phase!="awaiting_alignment"&&phase!="active"&&vr.Depth()>0){
   Stop("engage_before_ready");return false;
  }
  return true;
 }
 std::optional<std::uint64_t> BeginPolicy(const std::vector<ReceivedInput>& packets,double now){
  if(!reason.empty())return {};
  if(!CheckStartupDeadline(now))return {};
  for(const auto& packet:packets)if(!ReceiveVR(packet.payload,packet.received_at))return {};
  if(!vr.Poll(now)){Stop(vr.Reason());return {};}
  if(pending){Stop("overlapping_policy_request");return {};}
  if(!state){Stop("missing_state");return {};}
  prepared_mode=composition.Prepare(latest_bytes,latest_profile,state->sample.received_at,vr.Drain(),now);
  if(prepared_mode=="stopped"){
   Stop(composition.Reason());return {};
  }
  request_state_sequence=received_sequence;
  try{
   std::array<float,29> q{},dq{},mimic{};
   std::array<float,3> gyro{},rpy{};
   const auto& upper=composition.PreparedUpper();
   if(startup_blend&&upper&&!captured){captured=state->sample.q;blend_start=now;}
   request_alpha=startup_blend&&captured?OfflineBlendAlpha(now-blend_start,0,4):1;
   for(std::size_t i=0;i<29;++i){q[i]=static_cast<float>(state->sample.q[i]);
    dq[i]=static_cast<float>(state->sample.dq[i]);mimic[i]=upper?static_cast<float>((*upper)[i]):q[i];}
   if(startup_blend&&captured&&upper)mimic=OfflineMimic(*captured,*upper,request_alpha);
   for(std::size_t i=0;i<3;++i){gyro[i]=static_cast<float>(state->gyro[i]);rpy[i]=static_cast<float>(state->health.rpy[i]);}
   observation=history.Build(q,dq,gyro,rpy,mimic);
  }catch(const std::exception& e){Stop(e.what());return {};}
  requested_at=now;pending=++request;return pending;
 }
 std::optional<std::uint64_t> Begin(const std::vector<std::uint8_t>& bytes,
   const std::string& profile,double received,const std::vector<ReceivedInput>& packets,double now){
  if(!ReceiveState(bytes,profile,received,now))return {};
  return BeginPolicy(packets,now);
 }
 bool Finish(std::uint64_t token,const std::array<float,29>& action,double now){
  if(!reason.empty())return false;
  if(!CheckStartupDeadline(now))return false;
  if(!vr.Poll(now)){Stop(vr.Reason());return false;}
  if(!pending||token!=*pending){Stop("policy_request_mismatch");return false;}
  if(!std::isfinite(now)||now<requested_at||now-requested_at>.01){Stop("policy_deadline");return false;}
  pending.reset();
  if(composition.Poll(now)=="stopped"||composition.Finish(action,now)=="stopped"){
   Stop(composition.Reason());return false;
  }
  if(!composition.Candidate()){history.Discard();observation.reset();return true;}
  auto accepted=*composition.Candidate();
  if(startup_blend&&captured){
   const auto blended=OfflineBlendDesired(*captured,accepted,request_alpha);
   std::copy(blended.begin(),blended.begin()+12,accepted.begin());
  }
  OfflineDesiredPosition next;next.created_at=now;
  std::array<float,29> writer_initial{};
  for(std::size_t i=0;i<29;++i){
   writer_initial[i]=static_cast<float>(state->sample.q[i]);
   next.q[i]=static_cast<float>(accepted[i]);
  }
  try{if(!writer){
   if(torque_fade){
    std::array<float,29> measured{};
    for(std::size_t i=0;i<29;++i)measured[i]=static_cast<float>(state->health.torque[i]);
    captured_torque=OfflineTorqueFade(measured,0);torque_start=now;
   }
   writer.emplace(writer_initial,now);
  }}
  catch(const std::exception& e){Stop(e.what());return false;}
  try{history.Commit(accepted);}
  catch(const std::exception& e){Stop(e.what());return false;}
  phase=startup_blend&&request_alpha<1?"blending":(prepared_mode=="awaiting_alignment"?"awaiting_alignment":"active");
  observation.reset();desired=next;RefreshReadiness();return true;
 }
 bool Tick(double now){
  if(!reason.empty())return false;
  if(!CheckStartupDeadline(now))return false;
  if(!vr.Poll(now)){Stop(vr.Reason());return false;}
  const auto freshness=state_continuity.Poll(now);
  if(!freshness.empty()){Stop(freshness);return false;}
  if(pending&&now-requested_at>.01){Stop("policy_deadline");return false;}
  if(!writer)return false; // Settling or awaiting first VR alignment.
  auto applied=desired;
  if(captured_torque&&applied){
   const float alpha=static_cast<float>(std::clamp((now-torque_start)/1.0,0.0,1.0));
   applied->feedforward=OfflineTorqueFade(*captured_torque,alpha);
  }
  // Keep original desired.created_at: fade must never renew a stale policy command.
  if(!writer->Tick(state->sample,state->health,applied,now)){
   Stop(writer->Reason());return false;
  }
  return true;
 }
};
