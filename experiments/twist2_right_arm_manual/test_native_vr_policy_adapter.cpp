#include "native_vr_policy_adapter.hpp"
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
  NativeVrPolicyAdapter display(q,.1);
  for(int n=1;n<=52;++n)display.Update(q,dq,q,.1+n*.02,.1+n*.02,true);
  Check(display.Phase()=="vr_ready","ready display missing");
  auto displaced=q;displaced[0]+=.03;
  display.Update(displaced,dq,q,1.15,1.15,true);
  Check(display.Phase()=="vr_wait_tracking","ready display did not revoke");
 }
 for(int scenario=0;scenario<4;++scenario){
  NativeVrPolicyAdapter adapter(q,.1);auto packet=original;
  Check(adapter.Phase()=="vr_wait_tracking","initial readiness display");
  if(scenario==0){Check(!adapter.Receive(packet.dump(),.11),"early engage accepted");continue;}
  for(int n=1;n<=52;++n)adapter.Update(q,dq,q,.1+n*.02,.1+n*.02,true);
  Check(adapter.Phase()=="vr_ready","ready display missing");
  if(scenario==1){
   packet["all_joint_q_rad"][22]=q[22]+.1;packet["right_arm"]["joints"][0]=q[22]+.1;
  }
  Check(adapter.Receive(packet.dump(),1.15),"ready input rejected");
  if(scenario==1){
   bool stopped=false;try{adapter.Update(q,dq,q,1.16,1.16,true);}catch(const std::runtime_error&){stopped=true;}
   Check(stopped&&adapter.Poll(1.161)=="initial_arm_mismatch","alignment mismatch ignored");continue;
  }
  adapter.Update(q,dq,q,1.16,1.16,true);
  Check(adapter.Phase()=="vr_active","active display missing");
  packet["sequence"]=packet.at("sequence").get<std::uint64_t>()+1;
  packet["all_joint_q_rad"][22]=q[22]+.02;packet["right_arm"]["joints"][0]=q[22]+.02;
  Check(adapter.Receive(packet.dump(),1.17),"move input rejected");
  const auto target=adapter.Update(q,dq,q,1.18,1.18,true);
  Check(std::abs(target[22]-q[22]-.0016)<1e-9,"native rate mapping");
  for(std::size_t i=0;i<29;++i)if(i!=22)Check(target[i]==q[i],"unrelated axis changed");
  if(scenario==2){
   packet["input_command_mode"]="pinch_disengaged";
   Check(!adapter.Receive(packet.dump(),1.181),"release accepted");
   Check(adapter.Poll(1.182)=="input_disengaged","release not latched");
   Check(adapter.Phase()=="stopped","stop display missing");
  }else Check(!adapter.Poll(1.5).empty(),"writer poll missed VR timeout");
 }
 std::cout<<"PASS native VR bridge: ready, alignment, right-only rate, release and writer watchdog\n";
}catch(const std::exception& e){std::cerr<<e.what();return 1;}}
