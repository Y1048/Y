#include "offline_owner.hpp"
#include "offline_lag_fixture.hpp"
#include "hg_classes_only.hpp"
#include <iostream>
using unitree_hg::msg::dds_::LowState_;
void Check(bool b,const char* msg){if(!b)throw std::runtime_error(msg);}
int main(){try{
 for(double target:{-.3,.3}){
  double measured=0;
  for(int n=0;n<5000;++n){
   const double step=OfflineLagStep(measured,target,.002);
   Check(std::abs(step)<=.08*.002,"lag rate");
   const double next=measured+step;
   Check(next>=std::min(measured,target)&&next<=std::max(measured,target),"lag overshoot");
   measured=next;
  }
  Check(std::abs(measured-target)<1e-6,"lag convergence");
 }
 for(double dt:{0.,-.01,.021}){
  bool rejected=false;try{OfflineLagStep(0,1,dt);}catch(const std::invalid_argument&){rejected=true;}
  Check(rejected,"invalid lag dt");
 }
 std::string line;std::getline(std::cin,line);auto original=nlohmann::json::parse(line);
 for(int scenario=0;scenario<8;++scenario){
  OfflineOwner owner(true);LowState_ s;s.mode_machine(5);s.wireless_remote()[2]=1;s.imu_state().quaternion()[0]=1;
  std::array<double,29> q{};for(std::size_t i=0;i<29;++i){q[i]=offline_twist2::kDefault[i];s.motor_state()[i].q(static_cast<float>(q[i]));}
  auto packet=original;packet["all_joint_q_rad"]=q;packet["right_arm"]["joints"]=std::vector<double>(q.begin()+22,q.end());
  auto bytes=[&](){std::vector<std::uint8_t>b(sizeof(s));std::memcpy(b.data(),&s,sizeof(s));
   s.crc(OfflineWordCrc({b.begin(),b.end()-4}));std::memcpy(b.data(),&s,sizeof(s));return b;};
  std::array<float,29> action{};action[0]=.02F;
  if(scenario==4)action[0]=.2F;
  const float delta=action[0]*.5F;
  float previous=static_cast<float>(q[0]);
  for(int n=0;n<=601;++n){double t=1+n*.01;s.tick(n+1);
   if(scenario==5)s.motor_state()[0].dq(n==550?.11F:0.F);
   auto token=owner.Begin(bytes(),"hg_native_le2092_9754cd15",t,{},t);
   Check(token.has_value(),"startup prepare");Check(owner.Finish(*token,action,t+.001),"startup finish");
   if(n<100)Check(!owner.Writer(),"writer before settle");
   if(n>=100){
    Check(owner.Writer().has_value(),"missing pre-VR writer");
    if(n==100)Check(owner.Desired()->q[0]==static_cast<float>(q[0]),"blend initial jump");
    Check(owner.Desired()->q[0]>=previous&&owner.Desired()->q[0]<=static_cast<float>(q[0])+delta+.000001F,"blend overshoot");
    previous=owner.Desired()->q[0];
    for(std::size_t i=12;i<29;++i)Check(owner.Desired()->q[i]==static_cast<float>(q[i]),"upper moved before VR");
    Check(owner.Tick(t+.003),"startup writer tick");
    if(n==501)Check(owner.Phase()=="verifying_tracking","elapsed blend alone granted ready");
   }
   if(scenario==0&&n==101){
    Check(owner.Phase()=="blending","blend phase");
    Check(!owner.ReceiveVR(packet.dump(),t+.004),"early engage accepted");break;
   }
   if(scenario==3&&n==101){
    const auto held=owner.Writer()->LastTarget();
    Check(!owner.Tick(t+.025),"blend silence accepted");
    Check(owner.Reason()=="state_timeout"&&!owner.Desired(),"blend stop missing");
    Check(owner.Writer()->LastTarget()==held,"blend stop moved target");break;
   }
  }
  if(scenario==0){Check(owner.Reason()=="engage_before_ready","early engage reason");continue;}
  if(scenario==3)continue;
  if(scenario==4||scenario==5){
   Check(owner.Phase()=="verifying_tracking","untracked or interrupted dwell granted ready");
   Check(!owner.ReceiveVR(packet.dump(),7.014)&&owner.Reason()=="engage_before_ready","unready engage accepted");
   continue;
  }
  Check(owner.Phase()=="awaiting_alignment","not ready");
  Check(std::abs(owner.Desired()->q[0]-(static_cast<float>(q[0])+.01F))<1e-6F,"blend endpoint");
  if(scenario==2){packet["right_arm"]["joints"][0]=q[22]+.1;packet["all_joint_q_rad"][22]=q[22]+.1;}
  if(scenario==6){
   s.tick(603);s.motor_state()[0].dq(.11F);
   Check(owner.ReceiveState(bytes(),"hg_native_le2092_9754cd15",7.02,7.02),"regression receive");
   Check(owner.Phase()=="verifying_tracking","ready not revoked");
   Check(!owner.ReceiveVR(packet.dump(),7.021)&&owner.Reason()=="engage_before_ready","revoked engage accepted");continue;
  }
  if(scenario==7){
   const auto held=owner.Writer()->LastTarget();
   Check(!owner.ReceiveVR(packet.dump(),7.04)&&owner.Reason()=="state_timeout","stale ready accepted");
   Check(!owner.Desired()&&owner.Writer()->LastTarget()==held,"stale ready target changed");continue;
  }
  s.tick(603);auto token=owner.Begin(bytes(),"hg_native_le2092_9754cd15",7.02,{{packet.dump(),7.02}},7.02);
  if(scenario==2){Check(!token&&owner.Reason()=="initial_arm_mismatch","mismatch accepted");continue;}
  Check(token&&owner.Finish(*token,action,7.021),"ready engage");Check(owner.Phase()=="active","not active");
 }
 // A first-order lag fixture exercises feedback; it is not G1 dynamics.
 for(int scenario=0;scenario<4;++scenario){
  OfflineOwner owner(true);LowState_ s;s.mode_machine(5);s.wireless_remote()[2]=1;s.imu_state().quaternion()[0]=1;
  std::array<double,29> initial{};
  for(std::size_t i=0;i<29;++i){initial[i]=offline_twist2::kDefault[i];s.motor_state()[i].q(static_cast<float>(initial[i]));}
  auto bytes=[&](){std::vector<std::uint8_t>b(sizeof(s));std::memcpy(b.data(),&s,sizeof(s));
   s.crc(OfflineWordCrc({b.begin(),b.end()-4}));std::memcpy(b.data(),&s,sizeof(s));return b;};
  std::array<float,29> action{};action[0]=scenario==3?.02F:.2F;
  bool engaged=false;
  for(int n=0;n<=1500;++n){
   const double t=1+n*.01;s.tick(n+1);
   if(scenario==0&&owner.Writer()){
    const float before=s.motor_state()[0].q();
    const float velocity=std::clamp((owner.Writer()->LastTarget()[0]-before)/.2F,-.08F,.08F);
    s.motor_state()[0].q(before+velocity*.01F);s.motor_state()[0].dq(velocity);
   }
   if(scenario==2)s.motor_state()[0].dq(.11F); // Never settles.
   const auto held=owner.Writer()?owner.Writer()->LastTarget():std::array<float,29>{};
   const auto commits=owner.HistoryCommits();
   auto token=owner.Begin(bytes(),"hg_native_le2092_9754cd15",t,{},t);
   if(n==1500){
    Check(!token&&owner.Reason()=="startup_ready_timeout","startup deadline missing");
    Check(!owner.Desired()&&!owner.Observation(),"timeout retained pending outputs");
    Check(!owner.Finish(1,action,t+.001)&&!owner.Tick(t+.003),"timeout not latched");
    Check(owner.HistoryCommits()==commits,"timeout committed history");
    if(owner.Writer())Check(owner.Writer()->LastTarget()==held,"timeout advanced writer");
    break;
   }
   Check(token&&owner.Finish(*token,action,t+.001),"feedback cycle failed");
   if(owner.Writer())Check(owner.Tick(t+.003),"feedback writer failed");
   for(std::size_t i=12;i<29;++i)if(owner.Desired())
    Check(owner.Desired()->q[i]==static_cast<float>(initial[i]),"feedback moved upper");
   if(scenario==0&&owner.Phase()=="awaiting_alignment"){
    Check(s.motor_state()[0].q()>initial[0]+.07,"ready without following large target");
    auto packet=original;packet["all_joint_q_rad"]=initial;
    packet["right_arm"]["joints"]=std::vector<double>(initial.begin()+22,initial.end());
    s.tick(n+2);auto active=owner.Begin(bytes(),"hg_native_le2092_9754cd15",t+.01,{{packet.dump(),t+.01}},t+.01);
    Check(active&&owner.Finish(*active,action,t+.011)&&owner.Phase()=="active","feedback engage failed");
    engaged=true;break;
   }
  }
  if(scenario==0)Check(engaged,"lag fixture never ready");
  else Check(owner.Reason()=="startup_ready_timeout","unbounded startup wait");
 }
 std::cout<<"PASS 12 startup scenarios including lag feedback and bounded settle/tracking/engage wait\n";
}catch(const std::exception& e){std::cerr<<e.what();return 1;}}
