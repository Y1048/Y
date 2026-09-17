#include "split_vr_adapter_study.hpp"
#include "writer_reference_study.hpp"
#include "native_relative_reference.hpp"
#include "native_relay_contract.hpp"
#include "native_state_tick.hpp"
#include "native_command_limits.hpp"
#include <iostream>
void Check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
int main(){try{
 Check(!NativeStateTickAdvances(7,7),"duplicate tick refresh");
 Check(!NativeStateTickAdvances(7,6),"backward tick refresh");
 Check(NativeStateTickAdvances(7,8),"forward tick rejected");
 Check(NativeStateTickAdvances(0xffffffffU,0),"tick wrap rejected");
 Check(!NativeStateTickAdvances(0,0x80000000U),"ambiguous tick accepted");
 // A torque clamp must not override a rate bound; empty intersections reject.
 Check(!NativeLimitedPosition(0,0,.1F,.0016F,-1,1,100,0,2),"incompatible limits accepted");
 Check(!NativeLimitedPosition(0,0,0,.0016F,-1,1,100,20,2),"damping term conflict accepted");
 const auto valid=NativeLimitedPosition(.1F,0,0,.0016F,-1,1,100,0,2);
 Check(valid&&std::abs(*valid-.0016F)<1e-8F,"rate interval not preserved");
 Check(!NativeLimitedPosition(0,0,0,.0016F,-1,1,0,0,2),"zero gain accepted");
 {
  struct Audit {unsigned sequence=1;bool sdk_accepted=true,damping=false;
    std::array<double,29> target{},kp{},kd{},feedforward{};};
  Audit initial,latest,desired;
  latest.sequence=12;
  Check(NativeRelativeReferenceMatches(latest,initial,desired),"identical newer write rejected");
  for(int field=0;field<7;++field){auto changed=latest;
   if(field==0)changed.target[22]=.001;
   if(field==1)changed.kp[23]=1;
   if(field==2)changed.kd[24]=1;
   if(field==3)changed.feedforward[25]=1;
   if(field==4)changed.sdk_accepted=false;
   if(field==5)changed.damping=true;
   if(field==6)changed.sequence=0;
   Check(!NativeRelativeReferenceMatches(changed,initial,desired),"invalid reference accepted");
  }
  desired.target[28]=.001;
  Check(!NativeRelativeReferenceMatches(latest,initial,desired),"first command jump accepted");
  desired=initial;desired.feedforward[28]=1;
  Check(!NativeRelativeReferenceMatches(latest,initial,desired),"first torque jump accepted");
 }
 {
  SplitSettleWindow window({1,.005,.01,.1,.1,.15});
  std::array<double,29> still{};
  bool overflow=false;
  try{for(int i=0;i<129;++i)window.Update(still,still,{}, {},.001*(i+1),true);}
  catch(const std::runtime_error& e){overflow=std::string(e.what())=="study_window_overflow";}
  Check(overflow,"bounded settle history silently lost samples");
 }
 std::string line;std::getline(std::cin,line);const auto original=nlohmann::json::parse(line);
 const auto q=original.at("all_joint_q_rad").get<std::array<double,29>>();
 if(original.contains("relay_token"))ValidateNativeRelay(line,"offlineContractTest1234");
 {
  const std::string token="offlineContractTest1234";
  auto fixture=original;
  fixture["command_provenance"]="live_mink";fixture["simulation_only"]=false;
  fixture["session_id"]="synthetic-contract";fixture["relay_token"]=token;
  ValidateNativeRelay(fixture.dump(),token);
  for(int n=0;n<5;++n){
   auto bad=fixture;
   if(n==0)bad["command_provenance"]="simulation_only";
   if(n==1)bad["command_provenance"]="recorded_replay";
   if(n==2)bad["relay_token"]="differentToken123456";
   if(n==3)bad["simulation_only"]=true;
   if(n==4)bad["session_id"]="replay-test";
   bool rejected=false;try{ValidateNativeRelay(bad.dump(),token);}catch(const std::exception&){rejected=true;}
   Check(rejected,"native relay provenance bypass");
  }
 }
 std::array<double,29> dq{};
 {
  SplitVrAdapterStudy adapter(q,.1,{1,.005,.01,.1,.1,.15});
  for(int n=1;n<=52;++n)adapter.Update(q,dq,q,.1+n*.02,.1+n*.02,true,{}, {},true);
  WriterReferenceStudy writer;
  auto sent=q;sent[23]+=.01;
  writer.Complete(sent,1.15,true,false);
  const auto old=writer.Sequence();
  sent[23]+=.001;
  writer.Complete(sent,1.151,true,false);
  bool called=false;
  Check(!writer.TryBind(old,1.152,true,[&](const auto&){called=true;return true;}),"changed writer accepted old reference");
  Check(!called,"stale reference invoked binder");
  Check(adapter.Receive(original.dump(),1.153),"writer binding input rejected");
  Check(writer.TryBind(writer.Sequence(),1.154,true,[&](const auto& reference){
    if(!adapter.BindCommandReference(reference))return false;
    const auto first=adapter.Update(q,dq,q,1.154,1.154,true,{}, {},true);
    for(std::size_t i=22;i<29;++i)Check(first[i]==sent[i],"first command differs from accepted writer reference");
    for(std::size_t i=0;i<22;++i)Check(first[i]==q[i],"writer binding changed other owner");
    return true;
  }),"fresh writer reference rejected");
  Check(!writer.TryBind(writer.Sequence(),1.155,true,[](const auto&){return true;}),"writer reference rebound");
 }
 for(int failure=0;failure<5;++failure){
  WriterReferenceStudy writer;
  writer.Complete(q,1,true,false);
  if(failure==0)writer.Complete(q,1.001,false,false);
  if(failure==1)writer.Complete(q,1.001,true,true);
  if(failure==2)writer.Stop();
  bool called=false;
  Check(!writer.TryBind(writer.Sequence(),failure==3?1.1:1.002,failure!=4,[&](const auto&){called=true;return true;}),"invalid reference accepted");
  Check(!called,"invalid reference callback invoked");
 }
 {
  auto baseline=q;baseline[22]=2.61;
  AnchoredUpperStudy bounded(baseline,.1,.17453292519943295);
  auto packet=original;
  packet["all_joint_q_rad"][22]=2.5;packet["right_arm"]["joints"][0]=2.5;
  Check(bounded.Step(packet.dump(),.12)=="active","bound anchor rejected");
  Check(bounded.Target()==baseline,"bound anchor jumped");
  packet["sequence"]=packet.at("sequence").get<std::uint64_t>()+1;
  packet["all_joint_q_rad"][22]=2.52;packet["right_arm"]["joints"][0]=2.52;
  Check(bounded.Step(packet.dump(),.14)=="stopped","mapped limit ignored");
  Check(bounded.Reason()=="mapped_joint_limit"&&bounded.Target()==baseline,"mapped limit mutated target");
  Check(bounded.Step(original.dump(),.16)=="stopped","mapped failure restarted");
 }
 {
  SplitVrAdapterStudy relative(q,.1,{1,.005,.01,.1,.1,.15});
  auto measured=q;measured[23]+=.03;
  for(int n=1;n<=52;++n)relative.Update(measured,dq,q,.1+n*.02,.1+n*.02,true,{}, {},true);
  auto packet=original;
  packet["all_joint_q_rad"][23]=measured[23];packet["right_arm"]["joints"][1]=measured[23];
  Check(relative.Receive(packet.dump(),1.15),"relative first input rejected");
  Check(relative.Update(measured,dq,q,1.16,1.16,true,{}, {},true)==q,"first anchor changed command");
  auto target=q;
  for(int n=0;n<4;++n){
   packet["sequence"]=packet.at("sequence").get<std::uint64_t>()+1;
   packet["all_joint_q_rad"][23]=measured[23]+.003;packet["right_arm"]["joints"][1]=measured[23]+.003;
   const double t=1.17+n*.02;
   Check(relative.Receive(packet.dump(),t),"relative move rejected");
   const auto next=relative.Update(measured,dq,target,t+.01,t+.01,true,{}, {},true);
   Check(next[23]>=q[23]&&next[23]<=q[23]+.003+1e-12,"relative overshoot");
   Check(std::abs(next[23]-target[23])<=.001600000001,"relative rate exceeded");
   for(std::size_t i=0;i<29;++i)if(i!=23)Check(next[i]==q[i],"relative changed other joint");
   target=next;
  }
  Check(std::abs(target[23]-q[23]-.003)<1e-12,"relative anchor drifted");
  packet["sequence"]=packet.at("sequence").get<std::uint64_t>()+1;
  packet["input_command_mode"]="pinch_disengaged";
  Check(!relative.Receive(packet.dump(),1.26),"relative release ignored");
  Check(!relative.Poll(1.27).empty(),"relative stop not latched");
 }
 {
  SplitVrAdapterStudy timeout(q,.1,{1,.005,.01,.1,.1,.15});
  Check(timeout.Poll(15.1)=="startup_ready_timeout","startup watchdog lost");
  Check(!timeout.Receive(original.dump(),15.11),"timeout restarted");
 }
 {
  SplitVrAdapterStudy load(q,.1,{1,.005,.01,.1,.1,.15});
  auto measured=q;measured[16]-=.03;measured[23]+=.03;
  for(int n=1;n<=52;++n)load.Update(measured,dq,q,.1+n*.02,.1+n*.02,true,{}, {},true);
  Check(load.Phase()=="vr_ready","fixed load error blocked study");
  bool stopped=false;
  try{load.Update(measured,dq,q,1.15,1.15,true,{}, {},false);}catch(const std::exception&){stopped=true;}
  Check(stopped&&load.Poll(1.16)=="external_safety_stop","external safety missing");
 }
 {
  SplitVrAdapterStudy invalid(q,.1,{1,.005,.01,.1,.1,.15});
  Check(!invalid.Receive("{",.11),"invalid JSON accepted");
  Check(!invalid.Receive(original.dump(),.12),"invalid JSON stop not latched");
 }
 {
  SplitVrAdapterStudy display(q,.1,{1,.005,.01,.1,.1,.15});
  for(int n=1;n<=52;++n)display.Update(q,dq,q,.1+n*.02,.1+n*.02,true,{}, {},true);
  Check(display.Phase()=="vr_ready","ready display missing");
  auto displaced=q;displaced[0]+=.03;
  display.Update(displaced,dq,q,1.15,1.15,true,{}, {},true);
  Check(display.Phase()=="vr_wait_tracking","ready display did not revoke");
 }
 {
  SplitVrAdapterStudy strict(q,.1,{1,.005,.01,.1,.1,.15},true);
  for(int n=1;n<=52;++n)strict.Update(q,dq,q,.1+n*.02,.1+n*.02,true,{}, {},true);
  Check(strict.Receive(original.dump(),1.15),"strict input rejected");
  Check(strict.NeedsCommandReference(),"missing reference request");
  bool stopped=false;
  try{strict.Update(q,dq,q,1.16,1.16,true,{}, {},true);}catch(const std::runtime_error&){stopped=true;}
  Check(stopped&&strict.Poll(1.161)=="writer_reference_required","unbound native path accepted");
 }
 {
  SplitVrAdapterStudy strict(q,.1,{1,.005,.01,.1,.1,.15},true);
  for(int n=1;n<=52;++n)strict.Update(q,dq,q,.1+n*.02,.1+n*.02,true,{}, {},true);
  Check(strict.Receive(original.dump(),1.15),"strict bind input rejected");
  Check(strict.BindCommandReference(q),"strict reference bind failed");
  Check(!strict.NeedsCommandReference(),"bound reference requested again");
  const auto first=strict.Update(q,dq,q,1.16,1.16,true,{}, {},true);
  Check(first==q&&strict.Phase()=="vr_active","strict first command changed");
 }
 for(int scenario=0;scenario<4;++scenario){
  SplitVrAdapterStudy adapter(q,.1,{1,.005,.01,.1,.1,.15});auto packet=original;
  Check(adapter.Phase()=="vr_wait_tracking","initial readiness display");
  if(scenario==0){Check(!adapter.Receive(packet.dump(),.11),"early engage accepted");continue;}
  for(int n=1;n<=52;++n)adapter.Update(q,dq,q,.1+n*.02,.1+n*.02,true,{}, {},true);
  Check(adapter.Phase()=="vr_ready","ready display missing");
  if(scenario==1){
   packet["all_joint_q_rad"][22]=q[22]+.1;packet["right_arm"]["joints"][0]=q[22]+.1;
  }
  Check(adapter.Receive(packet.dump(),1.15),"ready input rejected");
  if(scenario==1){
   bool stopped=false;try{adapter.Update(q,dq,q,1.16,1.16,true,{}, {},true);}catch(const std::runtime_error&){stopped=true;}
   Check(stopped&&adapter.Poll(1.161)=="initial_arm_mismatch","alignment mismatch ignored");continue;
  }
  adapter.Update(q,dq,q,1.16,1.16,true,{}, {},true);
  Check(adapter.Phase()=="vr_active","active display missing");
  packet["sequence"]=packet.at("sequence").get<std::uint64_t>()+1;
  packet["all_joint_q_rad"][22]=q[22]+.02;packet["right_arm"]["joints"][0]=q[22]+.02;
  Check(adapter.Receive(packet.dump(),1.17),"move input rejected");
  const auto target=adapter.Update(q,dq,q,1.18,1.18,true,{}, {},true);
  Check(std::abs(target[22]-q[22]-.0016)<1e-9,"native rate mapping");
  for(std::size_t i=0;i<29;++i)if(i!=22)Check(target[i]==q[i],"unrelated axis changed");
  if(scenario==2){
   packet["input_command_mode"]="pinch_disengaged";
   Check(!adapter.Receive(packet.dump(),1.181),"release accepted");
   Check(adapter.Poll(1.182)=="input_disengaged","release not latched");
   Check(adapter.Phase()=="stopped","stop display missing");
  }else Check(!adapter.Poll(1.5).empty(),"writer poll missed VR timeout");
 }
 std::cout<<"PASS offline split VR bridge: ready, alignment, right-only rate, release and writer watchdog\n";
}catch(const std::exception& e){std::cerr<<e.what();return 1;}}
