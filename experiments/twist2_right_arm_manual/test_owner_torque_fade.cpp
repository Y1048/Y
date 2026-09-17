#include "offline_owner.hpp"
#include "hg_classes_only.hpp"
#include <iostream>
using unitree_hg::msg::dds_::LowState_;
void Check(bool b,const char* why){if(!b)throw std::runtime_error(why);}
int main(){try{
 for(int scenario=0;scenario<5;++scenario){
  OfflineOwner owner(true,scenario!=4);LowState_ s;
  s.mode_machine(5);s.wireless_remote()[2]=1;s.imu_state().quaternion()[0]=1;
  for(std::size_t i=0;i<29;++i){s.motor_state()[i].q(offline_twist2::kDefault[i]);s.motor_state()[i].tau_est(i%2?-1000.F:1000.F);}
  auto bytes=[&](){std::vector<std::uint8_t>b(sizeof(s));std::memcpy(b.data(),&s,sizeof(s));
   s.crc(OfflineWordCrc({b.begin(),b.end()-4}));std::memcpy(b.data(),&s,sizeof(s));return b;};
  std::array<float,29> previous{};previous.fill(10000);
  for(int n=0;n<=210;++n){const double t=1+n*.01;s.tick(n+1);
   // Later measurements must not replace the captured startup torque.
   if(n==101)for(std::size_t i=0;i<29;++i)s.motor_state()[i].tau_est(i%2?500.F:-500.F);
   auto token=owner.Begin(bytes(),"hg_native_le2092_9754cd15",t,{},t);
   Check(token&&owner.Finish(*token,{},t+.001),"fade policy cycle");
   if(n<100){Check(!owner.Writer(),"fade before settle");continue;}
   Check(owner.Tick(t+.003),"fade writer");
   for(std::size_t i=0;i<29;++i){
    const float ff=owner.Writer()->Diagnostics()[i].feedforward;
    const float fraction=static_cast<float>(std::clamp(1-(t+.003-2.001),0.,1.));
    const float expected=scenario==4?0:(i%2?-1.F:1.F)*offline_twist2::kTorqueLimit[i]*.5F*fraction;
    Check(std::abs(ff-expected)<1e-4F,"fade value or capture changed");
    Check(std::abs(ff)<=previous[i]+1e-5F,"fade increased");previous[i]=std::abs(ff);
    const float position_error=std::abs(owner.Writer()->LastTarget()[i]-s.motor_state()[i].q());
    // Existing leg blend uses float arithmetic; upper targets remain exact.
    Check(i<12?position_error<1e-7F:position_error==0,"fade moved position");
   }
   if((scenario==1||scenario==2)&&n==120){
    const auto held=owner.Writer()->LastTarget();
    if(scenario==1)owner.Stop("test_release");
    else {s.tick(122);auto bad=bytes();bad[80]^=1;Check(!owner.ReceiveState(bad,"hg_native_le2092_9754cd15",t+.004,t+.004),"bad CRC accepted");}
    Check(!owner.Tick(t+.005)&&!owner.Desired(),"stopped fade continued");
    Check(owner.Writer()->LastTarget()==held,"stop moved target");
    for(const auto& motor:owner.Writer()->Diagnostics())Check(motor.feedforward==0,"stop retained fade");
    break;
   }
   if(scenario==3&&n==130){
    const auto commits=owner.HistoryCommits();
    for(int k=1;k<=8&&owner.Reason().empty();++k){const double current=t+k*.01;s.tick(131+k);
     owner.ReceiveState(bytes(),"hg_native_le2092_9754cd15",current,current);owner.Tick(current+.003);}
    Check(owner.Reason()=="command_timeout"&&!owner.Desired(),"fade renewed stale command");
    Check(owner.HistoryCommits()==commits,"fade committed policy");break;
   }
  }
  if(scenario==0||scenario==4)for(const auto& motor:owner.Writer()->Diagnostics())Check(motor.feedforward==0,"fade endpoint nonzero");
 }
 std::cout<<"PASS 5 owner torque fade scenarios: signed clamp, capture, endpoint, stop, CRC, stale policy and opt-out\n";
}catch(const std::exception& e){std::cerr<<e.what();return 1;}}
