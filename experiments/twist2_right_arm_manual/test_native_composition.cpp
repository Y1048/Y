#include "native_composition_offline.hpp"
#include "hg_classes_only.hpp"
#include <iostream>
using unitree_hg::msg::dds_::LowState_;
void Check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
std::vector<std::uint8_t> Bytes(LowState_& state){
 std::vector<std::uint8_t> bytes(sizeof(state));std::memcpy(bytes.data(),&state,sizeof(state));
 state.crc(OfflineWordCrc({bytes.begin(),bytes.end()-4}));
 std::memcpy(bytes.data(),&state,sizeof(state));return bytes;
}
LowState_ State(){
 LowState_ state;state.mode_machine(5);state.imu_state().quaternion()[0]=1;
 state.wireless_remote()[2]=1;
 for(size_t i=0;i<29;++i)state.motor_state()[i].q(offline_twist2::kDefault[i]);
 state.motor_state()[12].q(.1F); // Measured capture differs from model default.
 return state;
}
int main(){
 try {
  std::string packet;std::getline(std::cin,packet);
  auto p=nlohmann::json::parse(packet);auto state=State();
  std::array<double,29> measured{};
  for(size_t i=0;i<29;++i)measured[i]=state.motor_state()[i].q();
  p["all_joint_q_rad"]=measured;
  p["right_arm"]["joints"]=std::vector<double>(measured.begin()+22,measured.end());
  packet=p.dump();
  NativeCompositionOffline c;
  for(int n=0;n<=101;++n){
   double now=5+n*.01;state.tick(static_cast<std::uint32_t>(n+1));
   auto mode=c.Prepare(Bytes(state),"hg_native_le2092_9754cd15",now,{},now);
   Check(mode!="stopped","settle");Check(!c.Candidate(),"provisional capture");
   Check(c.Finish({},now+.001)!="stopped","settle finish");Check(!c.Candidate(),"no VR alignment");
  }
  state.tick(103);
  Check(c.Prepare(Bytes(state),"hg_native_le2092_9754cd15",6.02,{{packet,6.02}},6.02)!="stopped","align");
  Check(!c.Candidate(),"prepare leaks candidate");
  std::array<float,29> action{};action[0]=.2F;
  Check(c.Finish(action,6.021)!="stopped"&&c.Candidate().has_value(),"compose");
  Check((*c.Candidate())[0]==static_cast<double>(offline_twist2::kDefault[0]+.5F*.2F),"policy leg");
  for(size_t i=12;i<29;++i)Check((*c.Candidate())[i]==measured[i],"measured upper capture");
  Check(c.Prepare(Bytes(state),"hg_native_le2092_9754cd15",6.03,{},6.03)!="stopped","short duplicate allowed");
  Check(c.Finish(action,6.031)!="stopped","duplicate finish");
  Check(c.Prepare(Bytes(state),"hg_native_le2092_9754cd15",6.041,{},6.041)=="stopped","stalled tick");
  Check(!c.Candidate(),"stop candidate");
  state.tick(104);Check(c.Prepare(Bytes(state),"hg_native_le2092_9754cd15",6.05,{},6.05)=="stopped","no resume");
  for(int fault=0;fault<7;++fault){
   NativeCompositionOffline bad;auto s=State();s.tick(10);auto bytes=Bytes(s);
   std::string profile="hg_native_le2092_9754cd15";double received=1,now=1;
   if(fault==0)bytes[80]^=1;
   if(fault==1)profile="DDS_CDR";
   if(fault==2)now=1.03;
   if(fault==3){s.wireless_remote()[2]=0;bytes=Bytes(s);}
   if(fault==4){s.mode_machine(0);bytes=Bytes(s);}
   if(fault==5){s.motor_state()[0].motorstate(1);bytes=Bytes(s);}
   if(fault==6){s.imu_state().rpy()[0]=.2F;bytes=Bytes(s);}
   Check(bad.Prepare(bytes,profile,received,{},now)=="stopped","fault accepted");
   Check(!bad.Candidate(),"fault candidate");
  }
  NativeCompositionOffline rollover;auto s=State();s.tick(0xffffffffU);
  Check(rollover.Prepare(Bytes(s),"hg_native_le2092_9754cd15",1,{},1)!="stopped","rollover first");
  rollover.Finish({},1.001);s.tick(0);
  Check(rollover.Prepare(Bytes(s),"hg_native_le2092_9754cd15",1.01,{},1.01)!="stopped","rollover");
  rollover.Finish({},1.011);s.tick(0xffffffffU);
  Check(rollover.Prepare(Bytes(s),"hg_native_le2092_9754cd15",1.02,{},1.02)=="stopped","backward");
  NativeCompositionOffline late;auto l=State();l.tick(1);
  late.Prepare(Bytes(l),"hg_native_le2092_9754cd15",1,{},1);
  Check(late.Finish({},1.021)=="stopped","expired finish");
  std::cout<<"PASS native bytes -> CRC/health/settle -> VR alignment -> policy legs/measured upper; 7 faults; tick duplicate/backward/rollover; expired Finish\n";
 }catch(const std::exception& e){std::cerr<<e.what();return 1;}
}
