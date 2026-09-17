#include "offline_owner.hpp"
#include "hg_classes_only.hpp"
#include <iostream>
using unitree_hg::msg::dds_::LowState_;
void Check(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
std::vector<std::uint8_t> Bytes(LowState_& s){
 std::vector<std::uint8_t> b(sizeof(s));std::memcpy(b.data(),&s,sizeof(s));
 s.crc(OfflineWordCrc({b.begin(),b.end()-4}));std::memcpy(b.data(),&s,sizeof(s));return b;
}
int main(){try{
 std::string line;std::getline(std::cin,line);const auto original=nlohmann::json::parse(line);
 for(int fault=0;fault<13;++fault){
  OfflineOwner owner;LowState_ s;s.mode_machine(5);s.imu_state().quaternion()[0]=1;s.wireless_remote()[2]=1;
  std::array<double,29> q{};for(std::size_t i=0;i<29;++i){q[i]=offline_twist2::kDefault[i];s.motor_state()[i].q(static_cast<float>(q[i]));}
  for(int n=0;n<102;++n){double t=1+n*.01;s.tick(n+1);
   const auto token=owner.Begin(Bytes(s),"hg_native_le2092_9754cd15",t,{},t);
   Check(token.has_value(),"settle begin");Check(owner.Finish(*token,{},t+.001),"settle finish");}
  auto packet=original;packet["all_joint_q_rad"]=q;packet["right_arm"]["joints"]=std::vector<double>(q.begin()+22,q.end());
  s.tick(103);auto token=owner.Begin(Bytes(s),"hg_native_le2092_9754cd15",2.02,{{packet.dump(),2.02}},2.02);
  Check(token.has_value(),"align begin");std::array<float,29> action{};action[0]=.02F;
  Check(owner.Observation().has_value(),"observation missing");
  Check(owner.HistoryCommits()==0,"unaccepted history committed");
  Check(owner.Finish(*token,action,2.021),"align finish");Check(owner.Tick(2.023),"writer first tick");
  Check(owner.HistoryCommits()==1&&!owner.Observation(),"accepted history missing");
  Check(owner.Writer()->LastTarget()[0]>q[0],"policy leg not applied");
  for(std::size_t i=12;i<29;++i)Check(owner.Writer()->LastTarget()[i]==static_cast<float>(q[i]),"upper changed");
  const auto last=owner.Writer()->LastTarget();
  if(fault==0)owner.Tick(2.041); // No new state or policy call.
  if(fault==1)owner.Finish(*token,action,2.024); // Duplicate result.
  if(fault>=2){s.tick(104);auto bytes=Bytes(s);if(fault==2)bytes[80]^=1;
   if(fault==4){packet["input_command_mode"]="pinch_disengaged";packet["sequence"]=2;}
   auto pending=owner.Begin(bytes,"hg_native_le2092_9754cd15",2.03,
     fault==4?std::vector<ReceivedInput>{{packet.dump(),2.03}}:std::vector<ReceivedInput>{},2.03);
   if(fault==3){Check(pending.has_value(),"pending");owner.Tick(2.051);owner.Finish(*pending,action,2.052);}
   if(fault==5){Check(pending.has_value(),"deadline pending");owner.Finish(*pending,action,2.045);}
   if(fault==6){Check(pending.has_value(),"deadline tick pending");owner.Tick(2.042);}
   if(fault>=7&&fault<=9){
    Check(pending.has_value(),"cache pending");const auto snapshot=owner.RequestStateSequence();
    const auto frozen_observation=owner.Observation()->observation;
    s.tick(105);auto update=Bytes(s);
    if(fault==8)update[80]^=1;
    if(fault==9){s.wireless_remote()[2]=0;update=Bytes(s);}
    const bool accepted=owner.ReceiveState(update,"hg_native_le2092_9754cd15",2.034,2.034);
    if(fault==7){
     Check(accepted,"cache update");Check(owner.LatestStateSequence()>snapshot,"new state absent");
     Check(owner.RequestStateSequence()==snapshot,"request rebound");
     Check(owner.Observation()->observation==frozen_observation,"observation rebound");
     Check(owner.Finish(*pending,action,2.035),"fresh update invalidated policy");
     owner.Stop("test_complete");
    }else{
     Check(!accepted,"invalid pending update accepted");
     Check(!owner.Finish(*pending,action,2.035),"result after bad state accepted");
    }
   }
   if(fault==10){
    packet["input_command_mode"]="pinch_disengaged";
    Check(!owner.ReceiveVR(packet.dump(),2.034),"pending pinch ignored");
    Check(!owner.Finish(*pending,action,2.035),"pinch result resumed");
   }
   if(fault==11){
    Check(!owner.ReceiveVR("not json",2.034),"pending malformed ignored");
    Check(!owner.Finish(*pending,action,2.035),"bad VR result resumed");
   }
   if(fault==12){
    const auto seq=packet.at("sequence").get<std::uint64_t>();
    for(int n=1;n<=65;++n){packet["sequence"]=seq+n;
     Check(owner.ReceiveVR(packet.dump(),2.034+n*.000001)==(n<=64),"FIFO overflow handling");}
   }
  }
  Check(!owner.Reason().empty(),"fault not stopped");Check(!owner.Desired(),"desired survived");
  Check(owner.HistoryCommits()==(fault==7?2U:1U),"failed request committed history");
  Check(!owner.Observation(),"stopped observation survived");
  const char* reasons[]={"state_timeout","policy_request_mismatch","crc_mismatch","state_timeout","input_disengaged","policy_deadline","policy_deadline","test_complete","crc_mismatch","operator_stop","input_disengaged","parse_error","queue_overflow"};
  Check(owner.Reason()==reasons[fault],"unexpected stop reason");
  Check(!owner.Tick(2.06),"tick resumed");Check(!owner.Finish(999,action,2.06),"late result resumed");
  Check(owner.Writer()->LastTarget()==last,"target changed after stop");
 }
 std::cout<<"PASS owner settle/VR/policy/writer; silence, duplicate, CRC, late finish, disengage latch\n";
}catch(const std::exception& e){std::cerr<<e.what();return 1;}}
