#include "offline_hg_native_decoder.hpp"
#include <fstream>
#include <iostream>
// Pose-only diagnostic. Deliberately does not claim full health/deadman arming.
int main(int argc,char** argv){
 try{
  if(argc!=2)throw std::runtime_error("capture required");
  std::string packet;std::getline(std::cin,packet);
  std::ifstream file(argv[1]);std::string line;
  MeasuredCompositionOffline pose({.02,1,.1,.01,.025,.25,.17453292519943295});
  OfflineStateSample state{};bool settled=false;size_t count=0;
  while(std::getline(file,line)){
   auto row=nlohmann::json::parse(line);if(row.at("event")!="sample")continue;
   auto hex=row.at("packed_hex").get<std::string>();std::vector<std::uint8_t> bytes;
   for(size_t i=0;i<hex.size();i+=2)bytes.push_back(static_cast<std::uint8_t>(std::stoul(hex.substr(i,2),nullptr,16)));
   state=DecodeOfflineHgNative(bytes,"hg_sdk_crc_le2092_b95a5304",++count,row.at("received_at_s")).sample;
   auto mode=pose.Tick(state,{}, {},state.received_at);
   if(mode=="stopped")throw std::runtime_error(pose.Reason());
   if(mode=="awaiting_alignment"){settled=true;break;}
  }
  if(!settled)throw std::runtime_error("no stable window");
  auto matched=pose;
  ++state.sequence;state.received_at+=.001;
  const auto mode=pose.Tick(state,{},{{packet,state.received_at}},state.received_at);
  auto goal=nlohmann::json::parse(packet);std::array<double,7> errors{};
  for(size_t i=0;i<7;++i)errors[i]=goal.at("right_arm").at("joints").at(i).get<double>()-state.q[i+22];
  // Positive control only: synthetic goal equal to recorded pose, never sent to VR.
  goal["all_joint_q_rad"]=state.q;
  goal["right_arm"]["joints"]=std::vector<double>(state.q.begin()+22,state.q.end());
  const auto positive=matched.Tick(state,{},{{goal.dump(),state.received_at}},state.received_at);
  if(mode!="stopped"||pose.Reason()!="initial_arm_mismatch"||pose.Candidate()
    ||positive=="stopped"||!matched.Candidate())throw std::runtime_error("alignment checks");
  std::cout<<nlohmann::json({{"settle_samples",count},{"measured_q",state.q},{"signed_error_rad",errors},
    {"recorded_goal_result",pose.Reason()},{"candidate_present",false},{"synthetic_matched_goal_passed",true},
    {"different_sessions",true},{"timestamps_rebased_for_pose_comparison",true},
    {"deadman_arming_tested",false},{"physical_output",false}}).dump(2)<<std::endl;
 }catch(const std::exception& e){std::cerr<<e.what();return 1;}
}
