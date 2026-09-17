#include "offline_observation_history.hpp"
#include "offline_blend.hpp"
#include "offline_writer_study.hpp"
#include <iostream>
#include "raw_input_watch_offline.hpp"
// Synthetic file-only event loop: no network, SDK, or command serialization.
int main() {
 try {
  using J=nlohmann::json;
  std::string line;std::getline(std::cin,line);const auto cfg=J::parse(line);
  if(cfg.at("fixture")!="frozen_policy_previous_target_writer")throw std::invalid_argument("fixture");
  auto baseline=cfg.at("baseline").get<std::array<double,29>>();
  GuardedCompositionOffline guard({.03,1,.1,.01,.025,.25,.17453292519943295},{.01,.15,.15,1.5,75});
  OfflineObservationHistory history;
  RawInputWatchOffline input;const bool raw_input=cfg.value("raw_input",false);
  std::optional<OfflineWriterStudy> writer;
  std::optional<OfflineDesiredPosition> desired;
  OfflineStateHealth health;health.crc_verified=true;health.mode_pr=0;health.mode_machine=5;
  health.deadman=true;health.emergency_stop=false;
  bool pending=false;double started=0,last_event=-1;std::uint64_t sequence=0,discarded=0,writes=0;
  float alpha=0;std::string reason;
  const auto Stop=[&](const std::string& why){
   if(reason.empty())reason=why;
   guard.Abort(reason);history.Stop();if(writer)writer->Stop(reason);
   desired.reset();pending=false;input.Stop(reason);
  };
  while(std::getline(std::cin,line)) {
   const auto req=J::parse(line);const double now=req.at("now");
   if(!std::isfinite(now)||now<last_event)throw std::invalid_argument("event_clock");
   last_event=now;const auto op=req.at("op").get<std::string>();J out;
   if(raw_input&&!input.Poll(now))Stop(input.Reason());
   if(op=="packet"){
    if(!raw_input)throw std::invalid_argument("raw_mode_required");
    auto hex=req.at("hex").get<std::string>();std::string raw;
    if(hex.size()%2||hex.find_first_not_of("0123456789abcdef")!=std::string::npos)throw std::invalid_argument("hex");
    for(size_t i=0;i<hex.size();i+=2)raw.push_back(static_cast<char>(std::stoi(hex.substr(i,2),nullptr,16)));
    if(!input.Receive(raw,now))Stop(input.Reason());
   }
   else if(op=="poll"){}
   else if(op=="stop")Stop(req.at("reason"));
   else if(op=="build") {
    if(reason.empty()) {
     if(pending)throw std::runtime_error("pending_build");
     ++sequence;started=now;
     OfflineStateSample state{baseline,{},sequence,now};std::vector<ReceivedInput> packets;
     for(const auto& p:req.at("packets")) {
      auto hex=p.at("hex").get<std::string>();std::string raw;
      if(hex.size()%2||hex.find_first_not_of("0123456789abcdef")!=std::string::npos)throw std::invalid_argument("hex");
      for(size_t i=0;i<hex.size();i+=2)raw.push_back(static_cast<char>(std::stoi(hex.substr(i,2),nullptr,16)));
      packets.push_back({raw,p.at("at")});
     }
     if(raw_input){
      if(!packets.empty())throw std::invalid_argument("raw_mode_build_packets");
      packets=input.Drain();
     }
     auto mode=guard.Prepare(state,health,packets,now);
     alpha=OfflineBlendAlpha(now,1,4);
     if(mode=="stopped")Stop(guard.Reason());
     else if(mode=="active"&&alpha<1)Stop("vr_before_blend_complete");
     else {
      auto upper=guard.PreparedUpper().value_or(baseline);
      std::array<float,29> q{};for(size_t i=0;i<29;++i)q[i]=static_cast<float>(baseline[i]);
      out["observation"]=history.Build(q,{},{},{},OfflineMimic(baseline,upper,alpha)).observation;
      pending=true;
     }
    }
   } else if(op=="finish") {
    if(!reason.empty())++discarded;
    else {
     if(!pending)throw std::runtime_error("finish_without_build");
     // Completion time is real simulated completion, not the Prepare timestamp.
     OfflinePolicySample policy{req.at("action").get<std::array<float,29>>(),sequence,sequence,now};
     auto mode=guard.Finish(policy,now);pending=false;
     if(mode=="stopped")Stop(guard.Reason());
     else if(guard.Candidate()) {
      const auto q=OfflineBlendDesired(baseline,*guard.Candidate(),alpha);
      OfflineDesiredPosition next;next.created_at=now;
      for(size_t i=0;i<29;++i)next.q[i]=static_cast<float>(q[i]);
      if(!writer) {
       std::array<float,29> initial{};for(size_t i=0;i<29;++i)initial[i]=static_cast<float>(baseline[i]);
       writer.emplace(initial,now);
      }
      desired=next;history.Commit(q);out["committed_q"]=q;
     } else history.Discard();
    }
   } else if(op=="writer") {
    if(writer&&reason.empty()) {
     OfflineStateSample state{};state.received_at=req.value("state_at",now);
     for(size_t i=0;i<29;++i)state.q[i]=writer->LastTarget()[i];
     if(!writer->Tick(state,health,desired,now))Stop(writer->Reason());
     else ++writes;
    }
   } else throw std::invalid_argument("op");
   out["reason"]=reason;out["pending"]=pending;out["commits"]=history.Commits();
   out["previous_action"]=history.PreviousAction();out["history"]=history.History();
   out["discarded"]=discarded;out["writes"]=writes;
   out["writer_q"]=writer?J(writer->LastTarget()):J(nullptr);
   out["desired"]=desired?J(desired->q):J(nullptr);
   out["started"]=started;out["input_depth"]=input.Depth();
   std::cout<<out.dump()<<std::endl;
  }
 }catch(const std::exception& e){std::cerr<<e.what();return 2;}
}
