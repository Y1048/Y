#include "offline_dispatch.hpp"
#include "hg_classes_only.hpp"
#include <iostream>
using unitree_hg::msg::dds_::LowState_;
void Check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
std::vector<std::uint8_t> Bytes(LowState_& s){
 std::vector<std::uint8_t>b(sizeof(s));std::memcpy(b.data(),&s,sizeof(s));
 s.crc(OfflineWordCrc({b.begin(),b.end()-4}));std::memcpy(b.data(),&s,sizeof(s));return b;
}
int main(){try{
 std::string line;std::getline(std::cin,line);auto original=nlohmann::json::parse(line);
 for(int scenario=0;scenario<6;++scenario){
  OfflineOwner owner;OfflineMemorySink sink;LowState_ s;
  s.mode_machine(5);s.imu_state().quaternion()[0]=1;s.wireless_remote()[2]=1;
  std::array<double,29> q{};
  for(std::size_t i=0;i<29;++i){q[i]=offline_twist2::kDefault[i];s.motor_state()[i].q(static_cast<float>(q[i]));}
  for(int n=0;n<102;++n){const double t=1+n*.01;s.tick(n+1);
   auto token=owner.Begin(Bytes(s),"hg_native_le2092_9754cd15",t,{},t);
   Check(token&&owner.Finish(*token,{},t+.001),"settle");
  }
  auto packet=original;packet["all_joint_q_rad"]=q;
  packet["right_arm"]["joints"]=std::vector<double>(q.begin()+22,q.end());
  s.tick(103);auto token=owner.Begin(Bytes(s),"hg_native_le2092_9754cd15",2.02,{{packet.dump(),2.02}},2.02);
  std::array<float,29> action{};action[0]=.02F;
  Check(token&&owner.Finish(*token,action,2.021),"activation");
  OfflineDispatch dispatch(owner,sink,2.021);
  Check(!dispatch.Pump(2.022)&&sink.Count()==0,"early dispatch");
  Check(dispatch.Pump(2.023)&&sink.Count()==1,"first dispatch");
  Check(sink.Last()->sequence==1&&sink.Last()->state_sequence==owner.LatestStateSequence(),"frame binding");
  for(std::size_t i=12;i<29;++i)Check(sink.Last()->motors[i].q==static_cast<float>(q[i]),"upper changed");
  if(scenario==0){
   Check(dispatch.Pump(2.029)&&sink.Count()==2,"allowed gap");
   Check(!dispatch.Pump(2.029)&&sink.Count()==2,"catch-up duplicate");
   Check(sink.Last()->sequence==2,"sequence");continue;
  }
  if(scenario==1)Check(!dispatch.Pump(2.030),"late dispatched");
  if(scenario==2){packet["input_command_mode"]="pinch_disengaged";
   Check(!owner.ReceiveVR(packet.dump(),2.024),"pinch accepted");}
  if(scenario==3){sink.reject_next=true;Check(!dispatch.Pump(2.025),"sink rejection ignored");}
  if(scenario==4)Check(!dispatch.Pump(2.022),"reversed clock accepted");
  if(scenario==5){s.tick(104);auto corrupt=Bytes(s);corrupt[80]^=1;
   Check(!owner.ReceiveState(corrupt,"hg_native_le2092_9754cd15",2.024,2.024),"CRC accepted");}
  const auto held=owner.Writer()->LastTarget();
  Check(!dispatch.Pump(2.031)&&!dispatch.Pump(2.033),"stop resumed dispatch");
  Check(sink.Count()==1&&sink.Last()->sequence==1,"stopped frame escaped");
  Check(dispatch.HandoffRequired()&&!owner.Desired(),"handoff missing");
  Check(owner.Writer()->LastTarget()==held,"stopped writer advanced");
  if(scenario==1)Check(owner.Reason()=="dispatch_deadline","deadline reason");
  if(scenario==3)Check(owner.Reason()=="dispatch_sink_rejected","sink reason");
  if(scenario==4)Check(owner.Reason()=="dispatch_clock","clock reason");
 }
 std::cout<<"PASS 6 memory dispatch scenarios; no transport or mode handoff executed\n";
}catch(const std::exception& e){std::cerr<<e.what();return 1;}}
